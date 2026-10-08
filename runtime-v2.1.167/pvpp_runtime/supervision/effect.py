"""Runtime 2.2 effect reconciliation, canonical finality, retry safety, and Layer-1 records."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
from .models import SemanticId
from .observation import ObservationService
from .store import SQLiteSupervisoryStore, ConcurrencyConflict

EFFECT_STATES={'open','no_material_effect_evidenced','partial_effect','completed_effect','invalid_effect','effect_unknown','resolved'}
TERMINAL_EPSILON_STATUSES={'completed','completed_staged','partial_realization','aborted_return','failed','emergency_return'}


@dataclass(frozen=True, slots=True)
class EffectEvidence:
    effect_evidence_id:str; execution_id:str; attempt:int; source_id:str; configuration_id:str
    state:str; realized_bundle_ref:str|None; observed_at:str; effective_at:str; received_at:str
    evidence_ref:str; provenance:str


@dataclass(frozen=True, slots=True)
class CanonicalEpisodeFinality:
    canonical_finality_id:str; active_execution_id:str; execution_id:str; attempt:int; episode_id:str
    epsilon_terminal_status:str; execution_path_ref:str|None; realized_bundle_ref:str|None
    terminal_evidence_ref:str|None; terminalized_at:str; governance_snapshot_id:str|None
    layer1_handoff_ref:str|None; immutable:bool


@dataclass(frozen=True, slots=True)
class WorldEffectReconciliationState:
    effect_record_id:str; execution_id:str; attempt:int; version:int; state:str
    realized_bundle_ref:str|None; authoritative_source_refs:tuple[str,...]
    control_enforcement_refs:tuple[str,...]; observed_at:str|None; effective_at:str|None
    received_at:str|None; unresolved:bool; canonical_finality_ref:str|None
    compensation_refs:tuple[str,...]; updated_at:str


@dataclass(frozen=True, slots=True)
class Layer1TransitionRecord:
    layer1_transition_id:str; execution_id:str; attempt:int; canonical_finality_ref:str|None
    effect_reconciliation_ref:str; prior_actual_state_ref:str; next_actual_state_ref:str
    transition_time:str; evidence_ref:str; provenance:str; configuration_id:str


class EffectService:
    def __init__(self, store:SQLiteSupervisoryStore, observations:ObservationService):
        self.store=store; self.observations=observations; self._c=store._conn; self._lock=store._lock
        with self._lock:
            self._c.executescript('''
            CREATE TABLE IF NOT EXISTS effect_evidence(effect_evidence_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS canonical_finality(active_execution_id TEXT PRIMARY KEY,canonical_finality_id TEXT UNIQUE NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS world_effect_state(execution_key TEXT PRIMARY KEY,version INTEGER NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS layer1_transitions(layer1_transition_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS retry_contracts(execution_key TEXT PRIMARY KEY,idempotent INTEGER NOT NULL,reconciliation_required INTEGER NOT NULL,registered_at TEXT NOT NULL);
            ''')

    def _active(self,active_execution_id):
        r=self.store.get_active_execution(active_execution_id)
        if r is None: raise KeyError('active execution not found')
        return r

    def _effect_source(self,source_id,configuration_id):
        r=self.observations.current_registration(source_id)
        if not r or r.status!='current' or 'effect' not in r.evidence_roles:
            raise ValueError('evidence_unverified: source lacks current effect role')
        if r.configuration_scope and configuration_id not in r.configuration_scope:
            raise ValueError('source_scope_violation')
        if 'effect_reconciliation' not in r.permitted_uses:
            raise ValueError('source_scope_violation')
        return r

    def submit_effect_evidence(self,*,active_execution_id,source_id,configuration_id,state,realized_bundle_ref,evidence_ref,provenance,observed_at,effective_at,received_at):
        rec=self._active(active_execution_id); reg=self._effect_source(source_id,configuration_id)
        if rec.configuration_id!=configuration_id: raise ValueError('configuration_conflict')
        if state not in EFFECT_STATES-{'open','resolved'}: raise ValueError('invalid effect evidence state')
        e=EffectEvidence(SemanticId.new('effev').value,rec.execution_id,rec.attempt,source_id,configuration_id,state,realized_bundle_ref,observed_at,effective_at,received_at,evidence_ref,provenance)
        with self._lock:self._c.execute('INSERT INTO effect_evidence VALUES(?,?)',(e.effect_evidence_id,json.dumps(asdict(e),sort_keys=True,separators=(',',':'))))
        self.store.record_supervisory_operation('effect_evidence_admitted',occurred_at=received_at,configuration_id=configuration_id,subject_id=active_execution_id,payload={'initiating_event_id':evidence_ref,'operation':'submit_effect_evidence','authority_source':reg.source_registration_id,'result_ref':e.effect_evidence_id,'invariant_status':'verified','error':None})
        return e

    def _assessment(self,assessment_id:str):
        row=self._c.execute('SELECT payload FROM continuation_assessments WHERE assessment_id=?',(assessment_id,)).fetchone()
        if not row: raise ValueError('canonical finality requires durable continuation assessment')
        return json.loads(row['payload'])

    def accept_canonical_finality(self,*,active_execution_id,terminalized_at,continuation_assessment_id=None,
                                  epsilon_terminal_status=None,execution_path_ref=None,realized_bundle_ref=None,
                                  terminal_evidence_ref=None,governance_snapshot_id=None,layer1_handoff_ref=None):
        rec=self._active(active_execution_id)
        if not continuation_assessment_id:
            raise ValueError('canonical finality requires trusted terminal continuation assessment')
        a=self._assessment(continuation_assessment_id)
        if a['active_execution_id']!=active_execution_id:
            raise ValueError('canonical finality assessment/execution mismatch')
        derived=a.get('epsilon_status')
        if derived not in TERMINAL_EPSILON_STATUSES:
            raise ValueError('canonical finality requires terminal canonical epsilon result')
        if epsilon_terminal_status is not None and epsilon_terminal_status!=derived:
            raise ValueError('caller epsilon terminal status does not match canonical result')
        snap_ref=governance_snapshot_id or a.get('committed_snapshot_id')
        f=CanonicalEpisodeFinality(SemanticId.new('fin').value,active_execution_id,rec.execution_id,rec.attempt,rec.episode_id,derived,execution_path_ref,realized_bundle_ref,terminal_evidence_ref or continuation_assessment_id,terminalized_at,snap_ref,layer1_handoff_ref,True)
        try:
            with self._lock:self._c.execute('INSERT INTO canonical_finality VALUES(?,?,?)',(active_execution_id,f.canonical_finality_id,json.dumps(asdict(f),sort_keys=True,separators=(',',':'))))
        except Exception as exc:
            raise ConcurrencyConflict('canonical_finality_conflict') from exc
        self.store.record_supervisory_operation('canonical_finality_accepted',occurred_at=terminalized_at,configuration_id=rec.configuration_id,subject_id=active_execution_id,payload={'initiating_event_id':continuation_assessment_id,'operation':'accept_canonical_finality','canonical_operation':'epsilon terminalization','canonical_result':derived,'result_ref':f.canonical_finality_id,'invariant_status':'trusted_first_finality','error':None})
        return f

    def get_canonical_finality(self,active_execution_id):
        row=self._c.execute('SELECT payload FROM canonical_finality WHERE active_execution_id=?',(active_execution_id,)).fetchone()
        return None if not row else CanonicalEpisodeFinality(**json.loads(row['payload']))

    def reconcile_effect(self,*,active_execution_id,effect_evidence_id,updated_at,control_enforcement_refs=(),compensation_refs=()):
        rec=self._active(active_execution_id); row=self._c.execute('SELECT payload FROM effect_evidence WHERE effect_evidence_id=?',(effect_evidence_id,)).fetchone()
        if not row: raise ValueError('evidence_unverified')
        e=EffectEvidence(**json.loads(row['payload'])); key=f'{rec.execution_id}|{rec.attempt}'
        old=self._c.execute('SELECT version,payload FROM world_effect_state WHERE execution_key=?',(key,)).fetchone(); ver=1 if not old else int(old['version'])+1
        old_sources=() if not old else tuple(json.loads(old['payload'])['authoritative_source_refs'])
        fin=self.get_canonical_finality(active_execution_id)
        unresolved=e.state in {'effect_unknown','partial_effect'}
        st=WorldEffectReconciliationState(SemanticId.new('effect').value,rec.execution_id,rec.attempt,ver,e.state,e.realized_bundle_ref,tuple(dict.fromkeys(old_sources+(e.source_id,))),tuple(control_enforcement_refs),e.observed_at,e.effective_at,e.received_at,unresolved,fin.canonical_finality_id if fin else None,tuple(compensation_refs),updated_at)
        with self._lock:self._c.execute('INSERT INTO world_effect_state VALUES(?,?,?) ON CONFLICT(execution_key) DO UPDATE SET version=excluded.version,payload=excluded.payload',(key,ver,json.dumps(asdict(st),sort_keys=True,separators=(',',':'))))
        self.store.record_supervisory_operation('effect_reconciled',occurred_at=updated_at,configuration_id=rec.configuration_id,subject_id=active_execution_id,payload={'initiating_event_id':effect_evidence_id,'operation':'reconcile_effect','state_version_before':ver-1,'state_version_after':ver,'result_ref':st.effect_record_id,'invariant_status':'unresolved' if unresolved else 'resolved','terminal_effect_separation':True,'error':None})
        return st

    def current_effect_state(self,active_execution_id):
        rec=self._active(active_execution_id); key=f'{rec.execution_id}|{rec.attempt}'; row=self._c.execute('SELECT payload FROM world_effect_state WHERE execution_key=?',(key,)).fetchone()
        if not row:return WorldEffectReconciliationState(SemanticId.new('effect').value,rec.execution_id,rec.attempt,0,'open',None,(),(),None,None,None,True,None,(), '')
        d=json.loads(row['payload']); d['authoritative_source_refs']=tuple(d['authoritative_source_refs']); d['control_enforcement_refs']=tuple(d['control_enforcement_refs']); d['compensation_refs']=tuple(d['compensation_refs']); return WorldEffectReconciliationState(**d)

    def _has_effect_evidence(self,rec)->bool:
        for row in self._c.execute('SELECT payload FROM effect_evidence').fetchall():
            d=json.loads(row['payload'])
            if d.get('execution_id')==rec.execution_id and d.get('attempt')==rec.attempt:
                return True
        return False

    def _has_control_dispatch(self, active_execution_id):
        rows=self._c.execute('SELECT payload_json FROM control_requests WHERE active_execution_id=?',(active_execution_id,)).fetchall() if self._c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='control_requests'").fetchone() else ()
        request_ids=[]
        for row in rows:
            d=json.loads(row['payload_json']); request_ids.append(d.get('control_request_id'))
        if not request_ids:return False
        for rid in request_ids:
            if self._c.execute('SELECT 1 FROM control_attempts WHERE control_request_id=? LIMIT 1',(rid,)).fetchone():return True
        return False

    def register_retry_contract(self,*,active_execution_id,idempotent,reconciliation_required,registered_at):
        rec=self._active(active_execution_id); key=f'{rec.execution_id}|{rec.attempt}'
        canonical_status=self.store.canonical_authorization_status(active_execution_id)
        if canonical_status!='issued' or self.store.has_supervised_native_invocation(active_execution_id) or self._has_control_dispatch(active_execution_id) or self._has_effect_evidence(rec):
            raise ValueError('retry contract must be pre-execution/pre-dispatch; canonical authorization status unavailable or outcome may already be uncertain')
        with self._lock:self._c.execute('INSERT INTO retry_contracts VALUES(?,?,?,?)',(key,int(idempotent),int(reconciliation_required),registered_at))

    def assert_retry_safe(self,*,active_execution_id):
        rec=self._active(active_execution_id); key=f'{rec.execution_id}|{rec.attempt}'; row=self._c.execute('SELECT * FROM retry_contracts WHERE execution_key=?',(key,)).fetchone(); st=self.current_effect_state(active_execution_id)
        if row and bool(row['idempotent']): return True
        if st.unresolved: raise ValueError('effect_unresolved')
        if st.state=='no_material_effect_evidenced': return True
        raise ValueError('retry_not_established_safe')

    def record_layer1_transition(self,*,active_execution_id,effect_reconciliation_ref,prior_actual_state_ref,next_actual_state_ref,transition_time,evidence_ref,provenance,configuration_id,authority_evidence=None,host_authoritative=None):
        rec=self._active(active_execution_id)
        if rec.configuration_id!=configuration_id: raise ValueError('configuration_conflict')
        st=self.current_effect_state(active_execution_id)
        if st.effect_record_id!=effect_reconciliation_ref or st.version<1: raise ValueError('layer1_conflict: current effect reconciliation required')
        if not self.store.trust.verify_layer1_authority(active_execution=rec,effect_state=st,transition_time=transition_time,evidence_ref=evidence_ref,authority_evidence=authority_evidence): raise ValueError('layer1_conflict: verified host-authoritative transition required')
        fin=self.get_canonical_finality(active_execution_id)
        t=Layer1TransitionRecord(SemanticId.new('l1').value,rec.execution_id,rec.attempt,fin.canonical_finality_id if fin else None,effect_reconciliation_ref,prior_actual_state_ref,next_actual_state_ref,transition_time,evidence_ref,provenance,configuration_id)
        with self._lock:self._c.execute('INSERT INTO layer1_transitions VALUES(?,?)',(t.layer1_transition_id,json.dumps(asdict(t),sort_keys=True,separators=(',',':'))))
        self.store.record_supervisory_operation('layer1_transition_committed',occurred_at=transition_time,configuration_id=configuration_id,subject_id=active_execution_id,payload={'initiating_event_id':effect_reconciliation_ref,'operation':'record_layer1_transition','authority_source':'host-trust-provider','result_ref':t.layer1_transition_id,'invariant_status':'host_authoritative','terminal_effect_separation':True,'error':None})
        return t
