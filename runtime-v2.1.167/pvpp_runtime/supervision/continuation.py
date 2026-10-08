"""Runtime 2.2 canonical continuation/checkpoint orchestration.

v0.156 makes assessments durable and serializes material-snapshot validation,
canonical advancement, and assessment commit at the supervisory transaction boundary.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Iterable
from collections.abc import Mapping
from pvpp_runtime.models import ExecutionObservation, GovernanceInvalidationSignal
from pvpp_runtime.reentry import assess_governance_reentry, plan_governance_reentry
from .models import SemanticId
from .store import SQLiteSupervisoryStore, ConcurrencyConflict
from .dependency import DependencyService, GovernanceSnapshotToken
from .bridge import CanonicalRuntimeBridge, CanonicalResolutionError
from .observation_value import ObservationValidationError, canonical_execution_observation_payload, snapshot_execution_observation

@dataclass(frozen=True, slots=True)
class ContinuationAssessment:
    assessment_id:str; active_execution_id:str; execution_id:str; attempt:int; canonical_handle_id:str
    input_snapshot_id:str; trigger_ids:tuple[str,...]; continuation_posture:str; epsilon_status:str|None
    adaptation_ref:str|None; reentry_plan_ref:str|None; authority_fence_required:bool
    reason_refs:tuple[str,...]; evidence_refs:tuple[str,...]; committed_snapshot_id:str; assessed_at:str; canonical_step:int|None=None

class ContinuationReconciliationRequired(ConcurrencyConflict): pass
class ObservationIdentityConflict(ConcurrencyConflict): pass

class ContinuationService:
    def __init__(self,store:SQLiteSupervisoryStore,dependencies:DependencyService,bridge:CanonicalRuntimeBridge):
        self.store=store; self.dependencies=dependencies; self.bridge=bridge; self._c=store._conn; self._lock=store._lock; self._assessments={}
        # Local liveness only: lets the creating service distinguish its own stale
        # prepared intent from a checkpoint that may still be running elsewhere.
        self._owned_intent_ids:set[str]=set(); self._inflight_intent_ids:set[str]=set()
        with self._lock:
            self._c.execute('CREATE TABLE IF NOT EXISTS continuation_assessments(assessment_id TEXT PRIMARY KEY,active_execution_id TEXT NOT NULL,payload TEXT NOT NULL)')
            self._c.execute('CREATE TABLE IF NOT EXISTS continuation_reconciliations(reconciliation_id TEXT PRIMARY KEY,active_execution_id TEXT NOT NULL,intent_id TEXT NOT NULL,outcome TEXT NOT NULL,payload TEXT NOT NULL)')
            self._c.execute('CREATE TABLE IF NOT EXISTS continuation_events(sequence INTEGER PRIMARY KEY AUTOINCREMENT,active_execution_id TEXT NOT NULL,event_kind TEXT NOT NULL,ref_id TEXT NOT NULL UNIQUE)')
            self._c.execute('CREATE TABLE IF NOT EXISTS continuation_observation_commits(active_execution_id TEXT NOT NULL,event_id TEXT NOT NULL,observation_digest TEXT,assessment_id TEXT NOT NULL,PRIMARY KEY(active_execution_id,event_id))')
            # Forward-compatible schema migration from v0.164 and earlier.
            commit_cols={r['name'] for r in self._c.execute('PRAGMA table_info(continuation_observation_commits)').fetchall()}
            if 'observation_digest' not in commit_cols:
                self._c.execute('ALTER TABLE continuation_observation_commits ADD COLUMN observation_digest TEXT')
            intent_cols={r['name'] for r in self._c.execute('PRAGMA table_info(continuation_intents)').fetchall()}
            if 'event_id' not in intent_cols:
                self._c.execute('ALTER TABLE continuation_intents ADD COLUMN event_id TEXT')
            if 'observation_digest' not in intent_cols:
                self._c.execute('ALTER TABLE continuation_intents ADD COLUMN observation_digest TEXT')

    @staticmethod
    def _parse_consequential_time(value):
        if not value:
            return None
        try:
            dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
            if dt.tzinfo is None:
                dt=dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    @classmethod
    def _observation_digest_payload(cls, payload: dict) -> str:
        raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8','strict')
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def _observation_digest(cls, observation: ExecutionObservation) -> str:
        # Compatibility helper for tests/internal callers. Normal checkpoint flow
        # snapshots once and digests the returned canonical payload directly.
        payload=canonical_execution_observation_payload(observation)
        return cls._observation_digest_payload(payload)

    def _existing_observation_assessment(self,active_execution_id,event_id,observation_digest=None):
        row=self._c.execute(
            'SELECT assessment_id,observation_digest FROM continuation_observation_commits WHERE active_execution_id=? AND event_id=?',
            (active_execution_id,event_id),
        ).fetchone()
        if not row:
            return None
        if observation_digest is not None:
            stored=row['observation_digest']
            if stored is None:
                raise ObservationIdentityConflict('identity_conflict: committed execution observation predates content digest; replay cannot be verified')
            if stored!=observation_digest:
                raise ObservationIdentityConflict('identity_conflict: execution observation event_id reused with changed content')
        return self.get_assessment(row['assessment_id'])

    def _current(self,active_execution_id):
        rec=self.store.get_active_execution(active_execution_id)
        if rec is None or rec.status not in ('registered','active'):raise CanonicalResolutionError('stale_lineage: active execution is not current')
        handle=self.bridge.current_handle(rec.canonical_handle_id)
        if handle.authorization_id!=rec.authorization_id or handle.episode_id!=rec.episode_id:raise CanonicalResolutionError('stale_lineage: supervisory/canonical lineage mismatch')
        return rec,handle,self.bridge.current_episode(handle.episode_id)
    def _persist(self,a):
        self._c.execute('INSERT INTO continuation_assessments VALUES(?,?,?)',(a.assessment_id,a.active_execution_id,json.dumps(asdict(a),sort_keys=True,separators=(',',':'))))
        self._c.execute('INSERT INTO continuation_events(active_execution_id,event_kind,ref_id) VALUES(?,?,?)',(a.active_execution_id,'assessment',a.assessment_id))
        self._assessments[a.assessment_id]=a
    def _intent_row(self, active_execution_id, *, include_abandoned=False):
        statuses = "'prepared','reconciliation_required','terminally_fenced','abandoned'" if include_abandoned else "'prepared','reconciliation_required','terminally_fenced'"
        return self._c.execute(f"SELECT rowid AS intent_rowid,* FROM continuation_intents WHERE active_execution_id=? AND status IN ({statuses}) ORDER BY rowid DESC LIMIT 1",(active_execution_id,)).fetchone()

    def _intent_superseded(self, row) -> bool:
        """Return true only for non-divergent historical intent state.

        Supersession is based solely on durable insertion order. Caller-supplied
        timestamps never participate. A reconciliation_required or terminally_fenced
        intent represents possible/established divergence and can never be erased by a
        later assessment or intent.
        """
        if row is None or row['status'] not in ('abandoned','prepared'):
            return False
        # v0.161 records a single durable order across intent creation and
        # assessment persistence. This permits a later persisted assessment (including
        # an assessment that does not create a continuation intent) to supersede only
        # non-divergent historical intent state without consulting caller time.
        ev=self._c.execute('SELECT sequence FROM continuation_events WHERE event_kind=? AND ref_id=?',('intent',row['intent_id'])).fetchone()
        if ev is not None:
            later=self._c.execute(
                """SELECT 1
                     FROM continuation_events e
                     LEFT JOIN continuation_intents i ON e.event_kind='intent' AND e.ref_id=i.intent_id
                    WHERE e.active_execution_id=? AND e.sequence>?
                      AND (e.event_kind='assessment' OR (e.event_kind='intent' AND i.status='closed'))
                    LIMIT 1""",
                (row['active_execution_id'],int(ev['sequence']))
            ).fetchone()
            return bool(later)
        # Conservative migration fallback for pre-v0.161 historical rows that have no
        # cross-table sequence: only a later closed intent row may supersede them.
        newer_closed=self._c.execute(
            "SELECT 1 FROM continuation_intents WHERE active_execution_id=? AND rowid>? AND status='closed' LIMIT 1",
            (row['active_execution_id'],row['intent_rowid'])
        ).fetchone()
        return bool(newer_closed)

    def _classify_failed_intent(self, intent_id: str) -> str:
        """CAS-classify only a still-prepared intent after a failed continuation.

        A concurrent successful commit may already have closed the intent.  That
        later durable state wins; this method must never overwrite it.
        """
        with self._lock:
            self._c.execute('BEGIN IMMEDIATE')
            try:
                row=self._c.execute('SELECT * FROM continuation_intents WHERE intent_id=?',(intent_id,)).fetchone()
                if row is None:
                    self._c.execute('COMMIT'); return 'reconciliation_required'
                if row['status']!='prepared':
                    self._c.execute('COMMIT'); return row['status']
                status='reconciliation_required'
                try:
                    if self.bridge.episode_is_indeterminate(row['episode_id']):
                        status='reconciliation_required'
                    else:
                        episode=self.bridge.episode_state(row['episode_id'])
                        if episode.episode_id==row['episode_id'] and episode.step_count==int(row['expected_step']):
                            status='abandoned'
                except Exception:
                    status='reconciliation_required'
                cur=self._c.execute(
                    "UPDATE continuation_intents SET status=? WHERE intent_id=? AND status='prepared'",
                    (status,intent_id),
                )
                if cur.rowcount!=1:
                    current=self._c.execute('SELECT status FROM continuation_intents WHERE intent_id=?',(intent_id,)).fetchone()
                    self._c.execute('COMMIT')
                    return current['status'] if current is not None else 'reconciliation_required'
                self._c.execute('COMMIT')
                return status
            except Exception:
                if self._c.in_transaction:self._c.execute('ROLLBACK')
                raise

    def _check_pending_intent(self, active_execution_id, *, observed_step: int | None = None):
        """Serialize pending-intent inspection across SQLite connections.

        Status beats historical assessment evidence: a reconciliation-required or
        terminally-fenced execution never emits retry guidance.  A prepared intent may
        still belong to a live checkpoint.  The creating service tracks that liveness
        in memory; another service cannot know it and therefore receives a retryable
        conflict that explicitly points to authorized reconciliation if no checkpoint
        is actually in flight.
        """
        with self._lock:
            old_timeout=int(self._c.execute('PRAGMA busy_timeout').fetchone()[0])
            self._c.execute('PRAGMA busy_timeout=0')
            try:
                try:
                    self._c.execute('BEGIN IMMEDIATE')
                except sqlite3.OperationalError as exc:
                    if 'locked' in str(exc).lower() or 'busy' in str(exc).lower():
                        raise ConcurrencyConflict('concurrency_conflict: checkpoint transaction in progress') from exc
                    raise
            finally:
                self._c.execute(f'PRAGMA busy_timeout={old_timeout}')
            try:
                row=self._c.execute(
                    "SELECT rowid AS intent_rowid,* FROM continuation_intents "
                    "WHERE active_execution_id=? AND status IN ('prepared','reconciliation_required','terminally_fenced') "
                    "ORDER BY rowid DESC LIMIT 1",(active_execution_id,),
                ).fetchone()
                if row is None:
                    if observed_step is not None:
                        rec=self.store.get_active_execution(active_execution_id)
                        if rec is not None:
                            current_step=self.bridge.episode_step(rec.episode_id)
                            if current_step!=observed_step:
                                self._c.execute('COMMIT')
                                raise ConcurrencyConflict(
                                    f'snapshot_conflict: canonical step changed concurrently from {observed_step} to {current_step}'
                                )
                    self._c.execute('COMMIT'); return

                status=row['status']; intent_id=row['intent_id']
                # Safety/fence state is authoritative for guidance and is checked before
                # any "later assessment" retry hint.
                if status in ('reconciliation_required','terminally_fenced'):
                    self._c.execute('COMMIT')
                    if status=='terminally_fenced':
                        raise ContinuationReconciliationRequired(
                            'continuation_reconciliation_required: terminally_fenced execution; retry cannot succeed'
                        )
                    raise ContinuationReconciliationRequired(
                        'continuation_reconciliation_required: unresolved continuation intent; authorized reconciliation required'
                    )

                # Only prepared intents can legitimately use the "assessment committed"
                # retry branch.
                ev=self._c.execute(
                    "SELECT sequence FROM continuation_events WHERE event_kind='intent' AND ref_id=?",
                    (intent_id,),
                ).fetchone()
                if ev is not None:
                    assessment=self._c.execute(
                        "SELECT 1 FROM continuation_events WHERE active_execution_id=? "
                        "AND event_kind='assessment' AND sequence>? LIMIT 1",
                        (active_execution_id,int(ev['sequence'])),
                    ).fetchone()
                    if assessment is not None:
                        self._c.execute('COMMIT')
                        raise ConcurrencyConflict('concurrency_conflict: continuation assessment already committed; retry')

                self._c.execute('COMMIT')
                if intent_id in self._owned_intent_ids and intent_id not in self._inflight_intent_ids:
                    raise ContinuationReconciliationRequired(
                        'continuation_reconciliation_required: prepared intent not in flight in this supervisor; authorized reconciliation required'
                    )
                raise ConcurrencyConflict(
                    'concurrency_conflict: continuation checkpoint may be in flight in another supervisor; retry; '
                    'if no checkpoint is in flight, authorized reconciliation required'
                )
            except Exception:
                if self._c.in_transaction:self._c.execute('ROLLBACK')
                raise

    def _prepare_intent(self, active_execution_id, episode, snapshot, assessed_at, *, event_id=None, observation_digest=None, observation_payload=None, return_existing=False):
        intent_id=SemanticId.new('cintent').value
        payload={'intent_id':intent_id,'active_execution_id':active_execution_id,'episode_id':episode.episode_id,'expected_step':episode.step_count,'snapshot_id':snapshot.governance_snapshot_id,'prepared_at':assessed_at,'event_id':event_id,'observation_digest':observation_digest}
        if observation_payload is not None:
            payload['observation_payload']=observation_payload
        try:
            self._c.execute('BEGIN IMMEDIATE')
        except sqlite3.OperationalError as exc:
            if 'locked' in str(exc).lower() or 'busy' in str(exc).lower():
                raise ConcurrencyConflict('concurrency_conflict: checkpoint transaction in progress') from exc
            raise
        try:
            self.dependencies.validate_snapshot(snapshot)
            # Idempotency/identity check is serialized with intent creation.  A
            # concurrent commit that won before this transaction is therefore observed
            # before any new intent or canonical call can occur.
            if event_id is not None:
                existing_assessment=self._existing_observation_assessment(active_execution_id,event_id,observation_digest)
                if existing_assessment is not None:
                    self._c.execute('COMMIT')
                    return (None,existing_assessment) if return_existing else None
            existing=self._c.execute(
                "SELECT event_id,observation_digest FROM continuation_intents WHERE active_execution_id=? "
                "AND status IN ('prepared','reconciliation_required','terminally_fenced') ORDER BY rowid DESC LIMIT 1",
                (active_execution_id,),
            ).fetchone()
            if existing is not None:
                raise ConcurrencyConflict(
                    'concurrency_conflict: continuation intent already in progress; retry; if no checkpoint is in flight, authorized reconciliation required'
                )
            current=self.bridge.episode_state(episode.episode_id)
            if current.step_count!=episode.step_count:
                raise ConcurrencyConflict(
                    f'snapshot_conflict: canonical step changed concurrently from {episode.step_count} to {current.step_count}'
                )
            self._c.execute(
                'INSERT INTO continuation_intents(intent_id,active_execution_id,episode_id,expected_step,snapshot_id,status,payload_json,event_id,observation_digest) VALUES(?,?,?,?,?,?,?,?,?)',
                (intent_id,active_execution_id,episode.episode_id,episode.step_count,snapshot.governance_snapshot_id,'prepared',json.dumps(payload,sort_keys=True,separators=(',',':')),event_id,observation_digest),
            )
            self._c.execute('INSERT INTO continuation_events(active_execution_id,event_kind,ref_id) VALUES(?,?,?)',(active_execution_id,'intent',intent_id))
            self._c.execute('COMMIT')
        except Exception:
            if self._c.in_transaction:self._c.execute('ROLLBACK')
            raise
        return (intent_id,None) if return_existing else intent_id

    def reconcile_continuation_divergence(self, *, active_execution_id: str, authority_id: str, authority_proof, reconciled_at: str):
        rec=self.store.get_active_execution(active_execution_id)
        if rec is None: raise CanonicalResolutionError('stale_lineage: active execution missing')
        self.store.require_registration_authority(authority_id=authority_id,role='continuation_reconciliation',configuration_id=rec.configuration_id,authority_proof=authority_proof)
        not_required=False; payload=None; rid=None; outcome=None; row=None
        with self._lock:
            # The entire decision and status mutation is one serialized write
            # transaction.  If a checkpoint currently owns the write boundary, this
            # waits for it and then re-reads the committed durable state.
            try:
                self._c.execute('BEGIN IMMEDIATE')
            except sqlite3.OperationalError as exc:
                if 'locked' in str(exc).lower() or 'busy' in str(exc).lower():
                    raise ConcurrencyConflict('concurrency_conflict: reconciliation transaction in progress; retry') from exc
                raise
            try:
                row=self._c.execute(
                    "SELECT rowid AS intent_rowid,* FROM continuation_intents WHERE active_execution_id=? "
                    "AND status IN ('prepared','reconciliation_required','terminally_fenced','abandoned') "
                    "ORDER BY rowid DESC LIMIT 1",
                    (active_execution_id,),
                ).fetchone()
                if row is None:
                    self._c.execute('COMMIT')
                    raise ValueError('continuation_reconciliation_not_required')

                read_status=row['status']
                # Re-read every durable input under the same transaction used for the
                # status transition.
                superseded=self._intent_superseded(row) if read_status in ('abandoned','prepared') else False
                expected=int(row['expected_step']); snapshot_id=row['snapshot_id']
                try:
                    indeterminate=self.bridge.episode_is_indeterminate(rec.episode_id)
                    episode=self.bridge.episode_state(rec.episode_id)
                    observed_step=episode.step_count
                except Exception:
                    indeterminate=False; episode=None; observed_step=None
                assessment_row=self._c.execute(
                    'SELECT payload FROM continuation_assessments WHERE active_execution_id=? ORDER BY rowid DESC LIMIT 1',
                    (active_execution_id,),
                ).fetchone()
                assessment=json.loads(assessment_row['payload']) if assessment_row else None

                if read_status=='abandoned' or superseded:
                    outcome='not_required_abandoned_closed' if read_status=='abandoned' else 'not_required_superseded_closed'
                    target_status='closed'; not_required=True
                else:
                    same_episode=bool(episode is not None and row['episode_id']==rec.episode_id==episode.episode_id)
                    if indeterminate or episode is None:
                        outcome='terminally_fenced'
                    elif same_episode and episode.step_count==expected:
                        outcome='reconciled_closed'
                    elif assessment and assessment.get('canonical_step')==episode.step_count and assessment.get('committed_snapshot_id')==snapshot_id:
                        outcome='reconciled_closed'
                    else:
                        outcome='terminally_fenced'
                    target_status='closed' if outcome=='reconciled_closed' else 'terminally_fenced'

                # Compare-and-swap on the state that was actually read.  A zero rowcount
                # means some newer durable state won; roll back this decision and
                # re-evaluate on a new call rather than overwriting it.
                cur=self._c.execute(
                    'UPDATE continuation_intents SET status=? WHERE intent_id=? AND status=?',
                    (target_status,row['intent_id'],read_status),
                )
                if cur.rowcount!=1:
                    self._c.execute('ROLLBACK')
                    raise ConcurrencyConflict('concurrency_conflict: continuation intent changed during reconciliation; retry')

                rid=SemanticId.new('crecon').value
                payload={'reconciliation_id':rid,'active_execution_id':active_execution_id,'intent_id':row['intent_id'],
                         'expected_step':expected,'observed_step':observed_step,'outcome':outcome,
                         'authority_id':authority_id,'reconciled_at':reconciled_at,'canonical_state_indeterminate':indeterminate}
                self._c.execute('INSERT INTO continuation_reconciliations VALUES(?,?,?,?,?)',
                                (rid,active_execution_id,row['intent_id'],outcome,json.dumps(payload,sort_keys=True,separators=(',',':'))))
                # Audit is part of the same SQLite transaction as the status and
                # reconciliation record.
                self.store.record_supervisory_operation(
                    'continuation_divergence_reconciled',occurred_at=reconciled_at,
                    configuration_id=rec.configuration_id,subject_id=active_execution_id,
                    payload={'initiating_event_id':row['intent_id'],'operation':'reconcile_continuation_divergence',
                             'authority_source':authority_id,'result_ref':rid,'outcome':outcome,
                             'invariant_status':outcome,'error':None},
                )
                self._c.execute('COMMIT')
            except Exception:
                if self._c.in_transaction:self._c.execute('ROLLBACK')
                raise
        if not_required:
            raise ValueError('continuation_reconciliation_not_required')
        return payload

    def evaluate_continuation(self,*,active_execution_id,snapshot:GovernanceSnapshotToken,observation:ExecutionObservation|None=None,invalidation_signals:Iterable[GovernanceInvalidationSignal]=(),trigger_ids:Iterable[str]=(),assessed_at:str,requested_posture:str|None=None):
        if requested_posture is not None:raise ValueError('caller/monitor continuation posture is not authoritative')
        if self._parse_consequential_time(assessed_at) is None:raise ValueError('invalid consequential operation timestamp')
        if snapshot.active_execution_id!=active_execution_id:raise ConcurrencyConflict('snapshot_conflict: execution scope mismatch')
        signals=tuple(invalidation_signals); trigger_ids=tuple(trigger_ids)
        with self._lock:
            starting_rec=self.store.get_active_execution(active_execution_id)
            starting_step=self.bridge.episode_step(starting_rec.episode_id) if starting_rec is not None else None
            # Fence/reconciliation state takes precedence over idempotent replay. A
            # historical 'continue' result must never mask a current fence.
            self._check_pending_intent(active_execution_id,observed_step=starting_step)
            rec,handle,episode=self._current(active_execution_id)
            intent_id=None; observation_digest=None
            if not signals:
                if observation is None:raise ValueError('observation or canonical invalidation signal required')
                # Freeze caller-owned observation content exactly once. From this point
                # forward digesting, intent identity, bridge validation and canonical
                # execution all use the same plain-data ExecutionObservation snapshot.
                observation, observation_payload = snapshot_execution_observation(observation)
                self.bridge.validate_advance_preconditions(episode, observation)
                observation_digest=self._observation_digest_payload(observation_payload)
                # Fast replay path after fence checking. _prepare_intent repeats this
                # lookup under BEGIN IMMEDIATE to close the concurrent-duplicate race.
                existing=self._existing_observation_assessment(active_execution_id,observation.event_id,observation_digest)
                if existing is not None:return existing
                intent_id,existing=self._prepare_intent(
                    active_execution_id,episode,snapshot,assessed_at,event_id=observation.event_id,
                    observation_digest=observation_digest,observation_payload=observation_payload,return_existing=True
                )
                if existing is not None:return existing
                self._owned_intent_ids.add(intent_id); self._inflight_intent_ids.add(intent_id)
            try:
                self._c.execute('BEGIN IMMEDIATE')
                self.dependencies.validate_snapshot(snapshot)
                rec,handle,episode=self._current(active_execution_id)
                if snapshot.configuration_id!=rec.configuration_id:raise ConcurrencyConflict('snapshot_conflict: configuration mismatch')
                posture='indeterminate'; eps_status=None; reentry_ref=None; fence=False; reasons=[]; evidence=[]
                if signals:
                    assessment=assess_governance_reentry(signals); plan=plan_governance_reentry(assessment,signals)
                    if not plan.valid:raise ValueError('invalid canonical re-entry plan: '+'; '.join(plan.violations))
                    if plan.recompute_from_stage is not None:
                        posture='reauthorization_required'; fence=True; reentry_ref=f"reentry:{plan.recompute_from_stage}:{','.join(plan.signal_ids)}"; reasons.append(f'canonical re-entry from {plan.recompute_from_stage}'); evidence.extend(e for sig in signals for e in sig.evidence_ids)
                    else:posture='continue'; reasons.append('canonical re-entry assessment established no invalidated stage')
                else:
                    try:
                        self.bridge.authorize_supervised_advance(self.store,active_execution_id=active_execution_id,intent_id=intent_id)
                    except CanonicalResolutionError as exc:
                        if 'continuation_intent_required' in str(exc):
                            raise ConcurrencyConflict('concurrency_conflict: continuation intent reconciled before canonical advance; retry') from exc
                        raise
                    result=self.bridge.advance_execution(episode,observation); eps_status=result.status
                    episode=result.episode
                    if result.status=='active':posture='continue'
                    elif result.status=='emergency_return':posture='emergency_return'; fence=True
                    elif result.return_upstream:posture='abort_return'; fence=True
                    elif result.terminal:posture='continue'
                    else:posture='indeterminate'
                    reasons.extend(result.notes)
                aid=SemanticId.new('assess').value
                out=ContinuationAssessment(aid,active_execution_id,rec.execution_id,rec.attempt,rec.canonical_handle_id,snapshot.governance_snapshot_id,trigger_ids,posture,eps_status,None,reentry_ref,fence,tuple(reasons),tuple(dict.fromkeys(evidence)),snapshot.governance_snapshot_id,assessed_at,episode.step_count)
                self._persist(out)
                if observation is not None:
                    try:
                        self._c.execute(
                            'INSERT INTO continuation_observation_commits(active_execution_id,event_id,observation_digest,assessment_id) VALUES(?,?,?,?)',
                            (active_execution_id,observation.event_id,observation_digest,aid),
                        )
                    except sqlite3.IntegrityError as exc:
                        raise ConcurrencyConflict('concurrency_conflict: observation already committed') from exc
                if intent_id:
                    cur=self._c.execute("UPDATE continuation_intents SET status='closed' WHERE intent_id=? AND status='prepared'",(intent_id,))
                    if cur.rowcount!=1:
                        raise ConcurrencyConflict('concurrency_conflict: continuation intent changed before commit')
                # The checkpoint assessment audit is part of the same SQLite transaction
                # as assessment persistence and intent close. A failed audit therefore
                # rolls the supervisor transaction back and enters the existing
                # post-canonical-movement reconciliation path rather than reporting a
                # failure after durable success.
                self.store.record_supervisory_operation(
                    'continuation_assessed',occurred_at=assessed_at,configuration_id=rec.configuration_id,
                    subject_id=active_execution_id,
                    payload={'initiating_event_id':next(iter(trigger_ids),observation.event_id if observation is not None else snapshot.governance_snapshot_id),
                             'operation':'evaluate_continuation','state_version_before':snapshot.descriptor_version,
                             'canonical_operation':'epsilon/re-entry','canonical_result':posture,'result_ref':aid,
                             'invariant_status':'snapshot_valid','error':None},
                )
                self._c.execute('COMMIT')
                if intent_id:self._inflight_intent_ids.discard(intent_id)
            except Exception:
                if self._c.in_transaction:self._c.execute('ROLLBACK')
                if intent_id:
                    try:self._classify_failed_intent(intent_id)
                    except Exception:pass
                    self._inflight_intent_ids.discard(intent_id)
                raise
        return out

    def checkpoint(self,*,active_execution_id,observation=None,invalidation_signals=(),trigger_ids=(),checkpoint_at):
        if self._parse_consequential_time(checkpoint_at) is None:raise ValueError('invalid consequential operation timestamp')
        snap=self.dependencies.capture_governance_snapshot(active_execution_id,created_at=checkpoint_at)
        return self.evaluate_continuation(active_execution_id=active_execution_id,snapshot=snap,observation=observation,invalidation_signals=invalidation_signals,trigger_ids=trigger_ids,assessed_at=checkpoint_at)
    def get_assessment(self,assessment_id):
        a=self._assessments.get(assessment_id)
        if a:return a
        row=self._c.execute('SELECT payload FROM continuation_assessments WHERE assessment_id=?',(assessment_id,)).fetchone()
        if not row:return None
        d=json.loads(row['payload'])
        for k in ('trigger_ids','reason_refs','evidence_refs'):d[k]=tuple(d[k])
        a=ContinuationAssessment(**d); self._assessments[assessment_id]=a; return a
