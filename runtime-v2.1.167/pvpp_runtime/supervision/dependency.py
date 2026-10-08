"""Runtime 2.2 authoritative dependency sets and durable material snapshots."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
from .models import SemanticId
from .store import SQLiteSupervisoryStore, ConcurrencyConflict
from .observation import AdmittedFactChange


def canonical_fact_kind(v: str) -> str:
    x = ' '.join(v.strip().lower().split())
    if not x:
        raise ValueError('fact_kind required')
    return x


def canonical_fact_id(v: str) -> str:
    x = v.strip()
    if not x:
        raise ValueError('fact_id required')
    return x


@dataclass(frozen=True, slots=True)
class ExecutionDependencyBinding:
    binding_id: str
    active_execution_id: str
    configuration_id: str
    subject_id: str
    fact_kind: str
    fact_id: str
    registration_authority: str
    registered_at: str
    status: str = 'current'


@dataclass(frozen=True, slots=True)
class DependencySetDescriptor:
    dependency_set_id: str
    active_execution_id: str
    configuration_id: str
    binding_refs: tuple[str, ...]
    canonical_fact_identities: tuple[tuple[str, str, str], ...]  # subject, kind, id
    descriptor_version: int
    status: str
    derived_at: str


@dataclass(frozen=True, slots=True)
class GovernanceSnapshotToken:
    governance_snapshot_id: str
    active_execution_id: str
    configuration_id: str
    dependency_set_id: str
    descriptor_version: int
    current_view_version: int
    material_fact_versions: tuple[tuple[str, str, str, int], ...]  # subject, kind, id, version
    created_at: str


class DependencyService:
    def __init__(self, store: SQLiteSupervisoryStore):
        self.store = store
        self._c = store._conn
        self._lock = store._lock
        self._snapshots: dict[str, GovernanceSnapshotToken] = {}
        with self._lock:
            self._ensure_schema()

    def _ensure_schema(self) -> None:
        cols = [r['name'] for r in self._c.execute("PRAGMA table_info(execution_dependencies)").fetchall()]
        legacy = bool(cols and 'subject_id' not in cols)
        if legacy:
            self._c.execute('DROP INDEX IF EXISTS idx_dep_reverse')
            self._c.execute('ALTER TABLE execution_dependencies RENAME TO execution_dependencies_v0155')
        self._c.executescript('''
        CREATE TABLE IF NOT EXISTS execution_dependencies(
            binding_id TEXT PRIMARY KEY,
            active_execution_id TEXT NOT NULL,
            configuration_id TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            fact_kind TEXT NOT NULL,
            fact_id TEXT NOT NULL,
            registration_authority TEXT NOT NULL,
            registered_at TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(active_execution_id,subject_id,fact_kind,fact_id));
        CREATE INDEX IF NOT EXISTS idx_dep_reverse
            ON execution_dependencies(configuration_id,subject_id,fact_kind,fact_id,status);
        CREATE TABLE IF NOT EXISTS dependency_descriptors(
            active_execution_id TEXT PRIMARY KEY,dependency_set_id TEXT NOT NULL,version INTEGER NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS governance_snapshots(
            governance_snapshot_id TEXT PRIMARY KEY,active_execution_id TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_governance_snapshot_active ON governance_snapshots(active_execution_id);
        ''')
        if legacy:
            rows = self._c.execute('SELECT * FROM execution_dependencies_v0155').fetchall()
            for row in rows:
                subject = self._infer_subject(row['configuration_id'], row['fact_kind'], row['fact_id'])
                if subject is None:
                    # Preserve the record for audit but fail closed by not migrating it as current authority.
                    continue
                self._c.execute(
                    'INSERT OR IGNORE INTO execution_dependencies VALUES(?,?,?,?,?,?,?,?,?)',
                    (row['binding_id'], row['active_execution_id'], row['configuration_id'], subject,
                     row['fact_kind'], row['fact_id'], row['registration_authority'], row['registered_at'], row['status']))
            self._c.execute('DROP TABLE execution_dependencies_v0155')

    def _active(self, aid):
        r = self.store.get_active_execution(aid)
        if r is None:
            raise ValueError('unknown active execution')
        return r

    def _candidate_subjects(self, config: str, fk: str, fi: str) -> tuple[str, ...]:
        out = []
        for row in self._c.execute('SELECT payload FROM governed_fact_views').fetchall():
            d = json.loads(row['payload'])
            if (d.get('configuration_id') == config and canonical_fact_kind(d.get('fact_kind', '')) == fk
                    and canonical_fact_id(d.get('fact_id', '')) == fi):
                out.append(d.get('subject_id'))
        return tuple(dict.fromkeys(x for x in out if x))

    def _infer_subject(self, config: str, fk: str, fi: str) -> str | None:
        subjects = self._candidate_subjects(config, canonical_fact_kind(fk), canonical_fact_id(fi))
        return subjects[0] if len(subjects) == 1 else None

    def register_dependency_binding(self, *, active_execution_id, configuration_id, fact_kind, fact_id,
                                    registration_authority, registered_at, subject_id=None, authority_proof=None):
        a = self._active(active_execution_id)
        if a.configuration_id != configuration_id:
            raise ValueError('configuration_conflict')
        if not registration_authority:
            raise ValueError('authorized registration context required')
        self.store.require_registration_authority(authority_id=registration_authority, role='dependency_registration', configuration_id=configuration_id, authority_proof=authority_proof)
        fk, fi = canonical_fact_kind(fact_kind), canonical_fact_id(fact_id)
        subject = (subject_id or '').strip() or self._infer_subject(configuration_id, fk, fi)
        if not subject:
            raise ValueError('subject_id required for exact dependency identity')
        bid = SemanticId.new('dep').value
        with self._lock:
            try:
                self._c.execute('BEGIN IMMEDIATE')
                self._c.execute('INSERT INTO execution_dependencies VALUES(?,?,?,?,?,?,?,?,?)',
                                (bid, active_execution_id, configuration_id, subject, fk, fi,
                                 registration_authority, registered_at, 'current'))
                row = self._c.execute('SELECT version,dependency_set_id FROM dependency_descriptors WHERE active_execution_id=?',
                                      (active_execution_id,)).fetchone()
                if row:
                    self._c.execute('UPDATE dependency_descriptors SET version=version+1,updated_at=? WHERE active_execution_id=?',
                                    (registered_at, active_execution_id))
                else:
                    self._c.execute('INSERT INTO dependency_descriptors VALUES(?,?,?,?)',
                                    (active_execution_id, SemanticId.new('depset').value, 1, registered_at))
                self._c.execute('COMMIT')
            except Exception:
                if self._c.in_transaction:
                    self._c.execute('ROLLBACK')
                raise
        return ExecutionDependencyBinding(bid, active_execution_id, configuration_id, subject, fk, fi,
                                          registration_authority, registered_at)

    def retire_dependency_binding(self, binding_id, *, registration_authority, retired_at, authority_proof=None):
        with self._lock:
            try:
                self._c.execute('BEGIN IMMEDIATE')
                row = self._c.execute('SELECT * FROM execution_dependencies WHERE binding_id=?', (binding_id,)).fetchone()
                if not row or row['status'] != 'current':
                    raise ValueError('binding not current')
                self.store.require_registration_authority(authority_id=registration_authority, role='dependency_registration', configuration_id=row['configuration_id'], authority_proof=authority_proof)
                if row['registration_authority'] != registration_authority:
                    raise PermissionError('unauthorized dependency retirement')
                self._c.execute("UPDATE execution_dependencies SET status='retired' WHERE binding_id=?", (binding_id,))
                self._c.execute('UPDATE dependency_descriptors SET version=version+1,updated_at=? WHERE active_execution_id=?',
                                (retired_at, row['active_execution_id']))
                self._c.execute('COMMIT')
            except Exception:
                if self._c.in_transaction:
                    self._c.execute('ROLLBACK')
                raise

    def derive_dependency_set(self, active_execution_id, *, derived_at):
        a = self._active(active_execution_id)
        row = self._c.execute('SELECT * FROM dependency_descriptors WHERE active_execution_id=?',
                              (active_execution_id,)).fetchone()
        if not row:
            raise ValueError('no registered dependency set')
        rs = self._c.execute(
            "SELECT * FROM execution_dependencies WHERE active_execution_id=? AND status='current' ORDER BY subject_id,fact_kind,fact_id",
            (active_execution_id,)).fetchall()
        return DependencySetDescriptor(
            row['dependency_set_id'], active_execution_id, a.configuration_id,
            tuple(x['binding_id'] for x in rs),
            tuple((x['subject_id'], x['fact_kind'], x['fact_id']) for x in rs),
            row['version'], 'current', derived_at)

    def _fact_view(self, config, subject, fk, fi):
        key = f'{config}|{subject}|{fk}|{fi}'
        return self._c.execute('SELECT version,payload FROM governed_fact_views WHERE fact_key=?', (key,)).fetchone()

    def _persist_snapshot(self, snap: GovernanceSnapshotToken) -> None:
        payload = json.dumps(asdict(snap), sort_keys=True, separators=(',', ':'))
        self._c.execute('INSERT INTO governance_snapshots VALUES(?,?,?)',
                        (snap.governance_snapshot_id, snap.active_execution_id, payload))
        self._snapshots[snap.governance_snapshot_id] = snap

    def capture_governance_snapshot(self, active_execution_id, *, created_at):
        with self._lock:
            d = self.derive_dependency_set(active_execution_id, derived_at=created_at)
            facts = []
            maxv = 0
            for subject, fk, fi in d.canonical_fact_identities:
                row = self._fact_view(d.configuration_id, subject, fk, fi)
                if not row:
                    raise ValueError(f'missing current governed fact: {subject}/{fk}/{fi}')
                facts.append((subject, fk, fi, row['version']))
                maxv = max(maxv, row['version'])
            snap = GovernanceSnapshotToken(
                SemanticId.new('snap').value, active_execution_id, d.configuration_id,
                d.dependency_set_id, d.descriptor_version, maxv, tuple(facts), created_at)
            self._persist_snapshot(snap)
            return snap

    def get_snapshot(self, snapshot_id):
        snap = self._snapshots.get(snapshot_id)
        if snap is not None:
            return snap
        row = self._c.execute('SELECT payload FROM governance_snapshots WHERE governance_snapshot_id=?',
                              (snapshot_id,)).fetchone()
        if not row:
            return None
        d = json.loads(row['payload'])
        d['material_fact_versions'] = tuple(tuple(x) for x in d['material_fact_versions'])
        snap = GovernanceSnapshotToken(**d)
        self._snapshots[snapshot_id] = snap
        return snap

    def validate_snapshot(self, s):
        d = self.derive_dependency_set(s.active_execution_id, derived_at=s.created_at)
        if (d.dependency_set_id, d.descriptor_version, d.configuration_id) != (
                s.dependency_set_id, s.descriptor_version, s.configuration_id):
            raise ConcurrencyConflict('snapshot_conflict: dependency descriptor changed')
        expected = {(subject, fk, fi): v for subject, fk, fi, v in s.material_fact_versions}
        if set(expected) != set(d.canonical_fact_identities):
            raise ConcurrencyConflict('snapshot_conflict: material set mismatch')
        for subject, fk, fi in d.canonical_fact_identities:
            row = self._fact_view(d.configuration_id, subject, fk, fi)
            if not row or row['version'] != expected[(subject, fk, fi)]:
                raise ConcurrencyConflict('snapshot_conflict: material fact changed')
        return True

    def resolve_affected_executions(self, change: AdmittedFactChange, *, configuration_id):
        out = set()
        for fi in change.changed_fact_ids:
            rows = self._c.execute(
                "SELECT active_execution_id FROM execution_dependencies WHERE configuration_id=? AND subject_id=? AND fact_kind=? AND fact_id=? AND status='current'",
                (configuration_id, change.subject_id, canonical_fact_kind(change.fact_kind), canonical_fact_id(fi))).fetchall()
            out.update(r['active_execution_id'] for r in rows)
        result = tuple(sorted(out))
        self.store.record_supervisory_operation(
            'dependency_fanout_resolved', occurred_at=change.committed_at,
            configuration_id=configuration_id, subject_id=change.subject_id,
            payload={'initiating_event_id': change.change_id, 'operation': 'resolve_affected_executions',
                     'state_version_before': change.prior_view_version, 'state_version_after': change.new_view_version,
                     'result_ref': list(result), 'invariant_status': 'resolved', 'error': None})
        return result
