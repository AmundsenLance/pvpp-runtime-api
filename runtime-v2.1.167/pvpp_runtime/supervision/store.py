"""SQLite durable state substrate for Runtime 2.2 supervisory records.

Phase 1 deliberately contains no observation admission, continuation decision,
execution control, or effect-realization semantics.  It supplies durable state,
version/CAS behavior, and append-only audit required by later work packages.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any, Mapping

from .models import ActiveExecutionRecord, AuditEvent, CanonicalExecutionHandle, ConfigurationState, SemanticId
from .trust import HostTrustProvider


class ConcurrencyConflict(RuntimeError):
    """Raised when a compare-and-swap mutation is based on a stale version."""


class SQLiteSupervisoryStore:
    """Small durable transaction boundary for the successor supervisory layer."""

    def __init__(self, path: str | Path, *, trust_provider: HostTrustProvider | None = None) -> None:
        self.path = str(path)
        self.trust = trust_provider or HostTrustProvider()
        self._canonical_bridges: dict[str, Any] = {}
        self._lock = RLock()
        self._conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = FULL")
        self._initialize()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    def __del__(self):
        # Python 3.13 warns when sqlite3 connections are garbage-collected while
        # still open. Tests and short-lived in-process deployments may legitimately
        # let the supervisory store fall out of scope, so close defensively here as
        # a final resource-safety backstop. Explicit close/context-manager use remains
        # preferred and this destructor carries no semantic commit behavior.
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self) -> "SQLiteSupervisoryStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _initialize(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS configurations (
                    configuration_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL CHECK(version >= 1),
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_kind TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    configuration_id TEXT,
                    subject_id TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_configuration
                    ON audit_events(configuration_id, sequence);
                CREATE INDEX IF NOT EXISTS idx_audit_subject
                    ON audit_events(subject_id, sequence);
                CREATE TABLE IF NOT EXISTS canonical_handles (
                    canonical_handle_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS active_executions (
                    active_execution_id TEXT PRIMARY KEY,
                    canonical_handle_id TEXT NOT NULL UNIQUE,
                    episode_id TEXT NOT NULL,
                    authorization_id TEXT NOT NULL UNIQUE,
                    execution_id TEXT NOT NULL UNIQUE,
                    action_id TEXT NOT NULL,
                    decision_cycle_id TEXT NOT NULL,
                    configuration_id TEXT,
                    attempt INTEGER NOT NULL CHECK(attempt >= 1),
                    binding_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK(version >= 1),
                    registered_at TEXT NOT NULL,
                    FOREIGN KEY(canonical_handle_id) REFERENCES canonical_handles(canonical_handle_id)
                );
                CREATE INDEX IF NOT EXISTS idx_active_episode ON active_executions(episode_id, status);
                CREATE TABLE IF NOT EXISTS supervised_native_invocations (
                    invocation_id TEXT PRIMARY KEY, active_execution_id TEXT NOT NULL, execution_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL, started_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS continuation_intents (
                    intent_id TEXT PRIMARY KEY, active_execution_id TEXT NOT NULL, episode_id TEXT NOT NULL,
                    expected_step INTEGER NOT NULL, snapshot_id TEXT NOT NULL, status TEXT NOT NULL, payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_continuation_intent_active ON continuation_intents(active_execution_id,status);
                """
            )

    def require_registration_authority(self, *, authority_id: str, role: str, configuration_id: str | None, authority_proof) -> None:
        if not self.trust.authorize_registration(authority_id, role=role, configuration_id=configuration_id, proof=authority_proof):
            raise PermissionError(f"trusted registration authority required for {role}")

    def now(self):
        return self.trust.now()

    def bind_canonical_bridge(self, active_execution_id: str, bridge) -> None:
        """Public rebinding is forbidden.

        Live canonical bindings are established only as part of trusted
        CanonicalRuntimeBridge.register_active_execution. Code with arbitrary private
        object mutation remains inside the in-process trusted computing base.
        """
        raise PermissionError('private trusted bridge registration required')

    def _bind_canonical_bridge(self, active_execution_id: str, bridge, handle: CanonicalExecutionHandle) -> None:
        """Private live binding used only by CanonicalRuntimeBridge registration."""
        # Local import avoids a module cycle at import time.
        from .bridge import CanonicalRuntimeBridge
        if not isinstance(bridge, CanonicalRuntimeBridge):
            raise PermissionError('trusted CanonicalRuntimeBridge required')
        rec = self.get_active_execution(active_execution_id)
        if rec is None:
            raise KeyError('active execution not found')
        if handle.canonical_handle_id != rec.canonical_handle_id or handle.episode_id != rec.episode_id or handle.authorization_id != rec.authorization_id:
            raise PermissionError('canonical bridge/active execution lineage mismatch')
        exact = bridge._handles.get(rec.canonical_handle_id)
        if exact is None or exact.canonical_handle_id != rec.canonical_handle_id or exact.episode_id != rec.episode_id or exact.authorization_id != rec.authorization_id:
            raise PermissionError('canonical bridge does not hold registered canonical handle')
        existing = self._canonical_bridges.get(active_execution_id)
        if existing is not None and existing is not bridge:
            raise PermissionError('active execution canonical bridge is already bound')
        self._canonical_bridges[active_execution_id] = bridge

    def canonical_authorization_status(self, active_execution_id: str) -> str | None:
        rec = self.get_active_execution(active_execution_id)
        bridge = self._canonical_bridges.get(active_execution_id)
        if rec is None or bridge is None:
            return None
        try:
            return bridge.authorization_status(rec.authorization_id)
        except Exception:
            return None

    def record_supervised_native_invocation(self, *, active_execution_id: str, started_at: str) -> str:
        rec=self.get_active_execution(active_execution_id)
        if rec is None: raise KeyError('active execution not found')
        iid=SemanticId.new('invoke').value
        with self._lock:
            self._conn.execute('INSERT INTO supervised_native_invocations VALUES(?,?,?,?,?)',(iid,active_execution_id,rec.execution_id,rec.attempt,started_at))
        return iid

    def has_supervised_native_invocation(self, active_execution_id: str) -> bool:
        with self._lock:
            row=self._conn.execute('SELECT 1 FROM supervised_native_invocations WHERE active_execution_id=? LIMIT 1',(active_execution_id,)).fetchone()
        return bool(row)

    def continuation_reconciliation_required(self, active_execution_id: str) -> bool:
        with self._lock:
            row=self._conn.execute("SELECT 1 FROM continuation_intents WHERE active_execution_id=? AND status IN ('prepared','reconciliation_required','terminally_fenced') LIMIT 1",(active_execution_id,)).fetchone()
        return bool(row)

    def continuation_intent_is_prepared(self, *, active_execution_id: str, intent_id: str, expected_step: int) -> bool:
        with self._lock:
            row=self._conn.execute("SELECT 1 FROM continuation_intents WHERE intent_id=? AND active_execution_id=? AND expected_step=? AND status='prepared'",(intent_id,active_execution_id,expected_step)).fetchone()
        return bool(row)

    def create_configuration(
        self,
        configuration_id: str,
        payload: Mapping[str, Any] | None = None,
        *,
        updated_at: str,
    ) -> ConfigurationState:
        if not configuration_id:
            raise ValueError("configuration_id is required")
        encoded = json.dumps(dict(payload or {}), sort_keys=True, separators=(",", ":"))
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    "INSERT INTO configurations(configuration_id, version, payload_json, updated_at) VALUES (?, 1, ?, ?)",
                    (configuration_id, encoded, updated_at),
                )
                self._conn.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                self._conn.execute("ROLLBACK")
                raise ConcurrencyConflict(f"configuration already exists: {configuration_id}") from exc
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return ConfigurationState(configuration_id, 1, dict(payload or {}), updated_at)

    def get_configuration(self, configuration_id: str) -> ConfigurationState | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT configuration_id, version, payload_json, updated_at FROM configurations WHERE configuration_id = ?",
                (configuration_id,),
            ).fetchone()
        if row is None:
            return None
        return ConfigurationState(
            row["configuration_id"], row["version"], json.loads(row["payload_json"]), row["updated_at"]
        )

    def compare_and_swap_configuration(
        self,
        configuration_id: str,
        *,
        expected_version: int,
        payload: Mapping[str, Any],
        updated_at: str,
    ) -> ConfigurationState:
        if expected_version < 1:
            raise ValueError("expected_version must be >= 1")
        encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                cur = self._conn.execute(
                    """UPDATE configurations
                       SET version = version + 1, payload_json = ?, updated_at = ?
                       WHERE configuration_id = ? AND version = ?""",
                    (encoded, updated_at, configuration_id, expected_version),
                )
                if cur.rowcount != 1:
                    raise ConcurrencyConflict(
                        f"stale or missing configuration: {configuration_id}@{expected_version}"
                    )
                row = self._conn.execute(
                    "SELECT configuration_id, version, payload_json, updated_at FROM configurations WHERE configuration_id = ?",
                    (configuration_id,),
                ).fetchone()
                self._conn.execute("COMMIT")
            except Exception:
                if self._conn.in_transaction:
                    self._conn.execute("ROLLBACK")
                raise
        return ConfigurationState(
            row["configuration_id"], row["version"], json.loads(row["payload_json"]), row["updated_at"]
        )

    def record_supervisory_operation(self, event_kind: str, *, occurred_at: str, configuration_id: str | None = None, subject_id: str | None = None, payload: Mapping[str, Any] | None = None) -> int:
        """Append one normalized causal-audit event. Evidence only; never grants authority."""
        event = AuditEvent(
            event_id=SemanticId.new("evt").value,
            event_kind=event_kind,
            occurred_at=occurred_at,
            configuration_id=configuration_id,
            subject_id=subject_id,
            payload=dict(payload or {}),
        )
        return self.append_audit_event(event)

    def append_audit_event(self, event: AuditEvent) -> int:
        encoded = json.dumps(dict(event.payload), sort_keys=True, separators=(",", ":"))
        with self._lock:
            try:
                cur = self._conn.execute(
                    """INSERT INTO audit_events(
                        event_id, event_kind, occurred_at, configuration_id, subject_id, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        event.event_id,
                        event.event_kind,
                        event.occurred_at,
                        event.configuration_id,
                        event.subject_id,
                        encoded,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConcurrencyConflict(f"duplicate audit event: {event.event_id}") from exc
        return int(cur.lastrowid)

    def audit_events(self, *, configuration_id: str | None = None) -> list[AuditEvent]:
        sql = "SELECT * FROM audit_events"
        args: tuple[Any, ...] = ()
        if configuration_id is not None:
            sql += " WHERE configuration_id = ?"
            args = (configuration_id,)
        sql += " ORDER BY sequence"
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [
            AuditEvent(
                event_id=row["event_id"],
                event_kind=row["event_kind"],
                occurred_at=row["occurred_at"],
                configuration_id=row["configuration_id"],
                subject_id=row["subject_id"],
                payload=json.loads(row["payload_json"]),
            )
            for row in rows
        ]

    def register_active_execution(self, handle: CanonicalExecutionHandle, *, execution_id: str, registered_at: str) -> ActiveExecutionRecord:
        """Reject direct caller registration; authoritative registration must cross the trusted canonical bridge."""
        raise PermissionError("canonical_resolution_failed: trusted bridge registration required")

    def _register_resolved_active_execution(self, handle: CanonicalExecutionHandle, *, execution_id: str, registered_at: str) -> ActiveExecutionRecord:
        if handle.status != "current":
            raise ValueError("current CanonicalExecutionHandle required")
        if not execution_id:
            raise ValueError("execution_id is required")
        payload = json.dumps({
            "episode_id": handle.episode_id, "license_object_id": handle.license_object_id,
            "selected_policy_id": handle.selected_policy_id, "action_id": handle.action_id,
            "decision_cycle_id": handle.decision_cycle_id, "configuration_id": handle.configuration_id,
            "attempt": handle.attempt, "binding_id": handle.binding_id,
            "binding_implementation_version": handle.binding_implementation_version,
            "authorization_id": handle.authorization_id, "status": handle.status,
            "resolved_at": handle.resolved_at
        }, sort_keys=True, separators=(",", ":"))
        active_id = SemanticId.new("aexec").value
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute("INSERT INTO canonical_handles(canonical_handle_id,payload_json,created_at) VALUES (?,?,?)", (handle.canonical_handle_id,payload,handle.resolved_at))
                self._conn.execute("""INSERT INTO active_executions(active_execution_id,canonical_handle_id,episode_id,authorization_id,execution_id,action_id,decision_cycle_id,configuration_id,attempt,binding_id,status,version,registered_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (active_id,handle.canonical_handle_id,handle.episode_id,handle.authorization_id,execution_id,handle.action_id,handle.decision_cycle_id,handle.configuration_id,handle.attempt,handle.binding_id,"registered",1,registered_at))
                self._conn.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                if self._conn.in_transaction: self._conn.execute("ROLLBACK")
                raise ConcurrencyConflict("active execution already registered or lineage reused") from exc
            except Exception:
                if self._conn.in_transaction: self._conn.execute("ROLLBACK")
                raise
        return ActiveExecutionRecord(active_id,handle.canonical_handle_id,handle.episode_id,handle.authorization_id,execution_id,handle.action_id,handle.decision_cycle_id,handle.configuration_id,handle.attempt,handle.binding_id,"registered",1,registered_at)

    def get_active_execution(self, active_execution_id: str) -> ActiveExecutionRecord | None:
        with self._lock:
            row=self._conn.execute("SELECT * FROM active_executions WHERE active_execution_id=?",(active_execution_id,)).fetchone()
        if row is None: return None
        return ActiveExecutionRecord(row["active_execution_id"],row["canonical_handle_id"],row["episode_id"],row["authorization_id"],row["execution_id"],row["action_id"],row["decision_cycle_id"],row["configuration_id"],row["attempt"],row["binding_id"],row["status"],row["version"],row["registered_at"])

    def _ensure_phase6_tables(self) -> None:
        with self._lock:
            self._conn.executescript('''
            CREATE TABLE IF NOT EXISTS supervisory_ownership (
              active_execution_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, owner_fence INTEGER NOT NULL, store_version INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS supervisory_owner_authorities (
              owner_id TEXT NOT NULL, configuration_id TEXT NOT NULL, status TEXT NOT NULL, registration_authority TEXT NOT NULL, registered_at TEXT NOT NULL,
              PRIMARY KEY(owner_id, configuration_id));
            CREATE TABLE IF NOT EXISTS supervisory_owner_authorities (
              owner_id TEXT NOT NULL, configuration_id TEXT NOT NULL, status TEXT NOT NULL, registration_authority TEXT NOT NULL, registered_at TEXT NOT NULL,
              PRIMARY KEY(owner_id, configuration_id));
            CREATE TABLE IF NOT EXISTS adapter_registrations (
              adapter_registration_id TEXT PRIMARY KEY, adapter_id TEXT NOT NULL, configuration_id TEXT, status TEXT NOT NULL, version INTEGER NOT NULL, payload_json TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_adapter_current ON adapter_registrations(adapter_id,configuration_id,status);
            CREATE TABLE IF NOT EXISTS control_requests (
              control_request_id TEXT PRIMARY KEY, active_execution_id TEXT NOT NULL, payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS control_attempts (
              control_attempt_id TEXT PRIMARY KEY, control_request_id TEXT NOT NULL, payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS enforcement_records (
              enforcement_record_id TEXT PRIMARY KEY, control_attempt_id TEXT NOT NULL, payload_json TEXT NOT NULL);
            ''')

    def phase6_put(self, table: str, key_column: str, key: str, payload: Mapping[str, Any], extra: Mapping[str, Any] | None = None) -> None:
        allowed={
          'adapter_registrations':('adapter_registration_id',('adapter_id','configuration_id','status','version')),
          'control_requests':('control_request_id',('active_execution_id',)),
          'control_attempts':('control_attempt_id',('control_request_id',)),
          'enforcement_records':('enforcement_record_id',('control_attempt_id',)),
        }
        if table not in allowed or allowed[table][0] != key_column: raise ValueError('unsupported phase6 table')
        self._ensure_phase6_tables(); ex=dict(extra or {}); cols=[key_column,*allowed[table][1],'payload_json']; vals=[key,*[ex[c] for c in allowed[table][1]],json.dumps(dict(payload),sort_keys=True,separators=(',',':'))]
        with self._lock:
            try: self._conn.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",vals)
            except sqlite3.IntegrityError as exc: raise ConcurrencyConflict(f'duplicate semantic record: {key}') from exc

    def phase6_get(self, table: str, key_column: str, key: str) -> dict[str, Any] | None:
        self._ensure_phase6_tables()
        with self._lock: row=self._conn.execute(f'SELECT payload_json FROM {table} WHERE {key_column}=?',(key,)).fetchone()
        return None if row is None else json.loads(row['payload_json'])

    def register_supervisory_owner_authority(self, *, owner_id: str, configuration_id: str, registration_authority: str, registered_at: str, authority_proof=None) -> None:
        self._ensure_phase6_tables()
        if not owner_id or not configuration_id or not registration_authority:
            raise ValueError('owner authority registration fields required')
        self.require_registration_authority(authority_id=registration_authority, role='owner_registration', configuration_id=configuration_id, authority_proof=authority_proof)
        with self._lock:
            self._conn.execute('INSERT INTO supervisory_owner_authorities(owner_id,configuration_id,status,registration_authority,registered_at) VALUES(?,?,?,?,?) ON CONFLICT(owner_id,configuration_id) DO UPDATE SET status=excluded.status,registration_authority=excluded.registration_authority,registered_at=excluded.registered_at',(owner_id,configuration_id,'current',registration_authority,registered_at))

    def supervisory_owner_authorized(self, *, owner_id: str, configuration_id: str) -> bool:
        self._ensure_phase6_tables()
        with self._lock:
            row=self._conn.execute('SELECT status FROM supervisory_owner_authorities WHERE owner_id=? AND configuration_id=?',(owner_id,configuration_id)).fetchone()
        return bool(row and row['status']=='current')

    def acquire_supervisory_ownership(self, *, active_execution_id: str, owner_id: str, acquired_at: str, expires_at: str | None = None) -> dict[str, Any]:
        self._ensure_phase6_tables(); rec=self.get_active_execution(active_execution_id)
        if rec is None: raise KeyError('active execution not found')
        if not self.supervisory_owner_authorized(owner_id=owner_id, configuration_id=rec.configuration_id):
            raise PermissionError('owner_unregistered')
        with self._lock:
            self._conn.execute('BEGIN IMMEDIATE')
            try:
                row=self._conn.execute('SELECT owner_fence,store_version FROM supervisory_ownership WHERE active_execution_id=?',(active_execution_id,)).fetchone()
                fence=1 if row is None else int(row['owner_fence'])+1; ver=1 if row is None else int(row['store_version'])+1
                payload={'ownership_id':SemanticId.new('own').value,'active_execution_id':active_execution_id,'execution_id':rec.execution_id,'attempt':rec.attempt,'owner_id':owner_id,'owner_fence':fence,'acquired_at':acquired_at,'expires_at':expires_at,'store_version':ver,'status':'current'}
                enc=json.dumps(payload,sort_keys=True,separators=(',',':'))
                self._conn.execute('INSERT INTO supervisory_ownership(active_execution_id,payload_json,owner_fence,store_version) VALUES (?,?,?,?) ON CONFLICT(active_execution_id) DO UPDATE SET payload_json=excluded.payload_json,owner_fence=excluded.owner_fence,store_version=excluded.store_version',(active_execution_id,enc,fence,ver)); self._conn.execute('COMMIT'); return payload
            except Exception:
                if self._conn.in_transaction:self._conn.execute('ROLLBACK')
                raise

    def current_supervisory_ownership(self, active_execution_id: str) -> dict[str, Any] | None:
        self._ensure_phase6_tables()
        with self._lock: row=self._conn.execute('SELECT payload_json FROM supervisory_ownership WHERE active_execution_id=?',(active_execution_id,)).fetchone()
        return None if row is None else json.loads(row['payload_json'])
