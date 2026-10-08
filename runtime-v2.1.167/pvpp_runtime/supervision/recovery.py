"""Runtime 2.2 durable recovery profiles and evidence-backed restart reconciliation."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
from .models import SemanticId
from .store import SQLiteSupervisoryStore, ConcurrencyConflict
from .dependency import DependencyService
from .effect import EffectService


@dataclass(frozen=True, slots=True)
class RecoveryRequirementProfile:
    recovery_profile_id:str; action_id:str; binding_id:str; configuration_id:str
    required_control_reconciliation:bool; required_effect_evidence:bool; required_world_layer1_checks:bool
    retry_idempotency_prerequisites:bool; compensation_prerequisites:bool; freshness_dependency_requirements:bool
    unresolved_policy:str; registration_authority:str; version:int; status:str; registered_at:str


@dataclass(frozen=True, slots=True)
class RecoveryReconciliationRecord:
    recovery_id:str; active_execution_id:str; execution_id:str; attempt:int; new_owner_id:str; owner_fence:int
    recovery_profile_ref:str; durable_state_version:int; canonical_finality_status:str; canonical_finality_ref:str|None
    external_control_status:str; effect_status:str; effect_ref:str|None; layer1_world_state_status:str
    requirement_results:tuple[tuple[str,bool],...]; recovery_state:str; control_resumption_allowed:bool
    governance_snapshot_id:str|None; evidence_refs:tuple[str,...]; provenance:str; started_at:str; completed_at:str|None


class RecoveryService:
    def __init__(self,store:SQLiteSupervisoryStore,dependencies:DependencyService,effects:EffectService):
        self.store=store; self.dependencies=dependencies; self.effects=effects; self._c=store._conn; self._lock=store._lock
        with self._lock:self._c.executescript('''
        CREATE TABLE IF NOT EXISTS recovery_profiles(profile_key TEXT PRIMARY KEY,recovery_profile_id TEXT UNIQUE NOT NULL,version INTEGER NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS recovery_records(active_execution_id TEXT PRIMARY KEY,recovery_id TEXT UNIQUE NOT NULL,payload TEXT NOT NULL);
        ''')

    def _active(self,aid):
        r=self.store.get_active_execution(aid)
        if not r: raise KeyError('active execution not found')
        return r

    def _key(self,r): return f'{r.action_id}|{r.binding_id}|{r.configuration_id}'

    def register_recovery_profile(self,*,active_execution_id,required_control_reconciliation,required_effect_evidence,required_world_layer1_checks,retry_idempotency_prerequisites=False,compensation_prerequisites=False,freshness_dependency_requirements=True,unresolved_policy='remain_fenced',registration_authority,registered_at,authority_proof=None):
        r=self._active(active_execution_id)
        if not registration_authority: raise PermissionError('recovery profile registration authority required')
        self.store.require_registration_authority(authority_id=registration_authority, role='recovery_registration', configuration_id=r.configuration_id, authority_proof=authority_proof)
        key=self._key(r); old=self._c.execute('SELECT payload FROM recovery_profiles WHERE profile_key=?',(key,)).fetchone()
        if old: raise ConcurrencyConflict('recovery profile already established; changes are prospective/versioned')
        p=RecoveryRequirementProfile(SemanticId.new('rprof').value,r.action_id,r.binding_id,r.configuration_id,bool(required_control_reconciliation),bool(required_effect_evidence),bool(required_world_layer1_checks),bool(retry_idempotency_prerequisites),bool(compensation_prerequisites),bool(freshness_dependency_requirements),unresolved_policy,registration_authority,1,'current',registered_at)
        with self._lock:self._c.execute('INSERT INTO recovery_profiles VALUES(?,?,?,?,?)',(key,p.recovery_profile_id,p.version,p.status,json.dumps(asdict(p),sort_keys=True,separators=(',',':'))))
        return p

    def current_profile(self,active_execution_id):
        r=self._active(active_execution_id); row=self._c.execute('SELECT payload FROM recovery_profiles WHERE profile_key=?',(self._key(r),)).fetchone()
        return None if not row else RecoveryRequirementProfile(**json.loads(row['payload']))

    def begin_recovery(self,*,active_execution_id,new_owner_id,started_at,provenance='durable-restart'):
        r=self._active(active_execution_id); p=self.current_profile(active_execution_id)
        if not p: raise ValueError('recovery_profile_missing')
        if not self.store.supervisory_owner_authorized(owner_id=new_owner_id, configuration_id=r.configuration_id):
            raise PermissionError('owner_unregistered')
        own=self.store.acquire_supervisory_ownership(active_execution_id=active_execution_id,owner_id=new_owner_id,acquired_at=started_at)
        fin=self.effects.get_canonical_finality(active_execution_id); est=self.effects.current_effect_state(active_execution_id)
        rr=RecoveryReconciliationRecord(SemanticId.new('recovery').value,active_execution_id,r.execution_id,r.attempt,new_owner_id,own['owner_fence'],p.recovery_profile_id,own['store_version'],'terminal' if fin else 'active',fin.canonical_finality_id if fin else None,'unknown',est.state,est.effect_record_id if est.version else None,'unresolved',(), 'recovering',False,None,(),provenance,started_at,None)
        with self._lock:self._c.execute('INSERT INTO recovery_records VALUES(?,?,?) ON CONFLICT(active_execution_id) DO UPDATE SET recovery_id=excluded.recovery_id,payload=excluded.payload',(active_execution_id,rr.recovery_id,json.dumps(asdict(rr),sort_keys=True,separators=(',',':'))))
        return rr

    def get_recovery(self,active_execution_id):
        row=self._c.execute('SELECT payload FROM recovery_records WHERE active_execution_id=?',(active_execution_id,)).fetchone()
        if not row:return None
        d=json.loads(row['payload']); d['requirement_results']=tuple(tuple(x) for x in d['requirement_results']); d['evidence_refs']=tuple(d['evidence_refs']); return RecoveryReconciliationRecord(**d)

    def _verified_control_reconciled(self, active_execution_id: str) -> bool:
        request_ids=[]
        for row in self._c.execute('SELECT control_request_id,payload_json FROM control_requests').fetchall():
            d=json.loads(row['payload_json'])
            if d.get('active_execution_id')==active_execution_id:
                request_ids.append(row['control_request_id'])
        if not request_ids:
            return False
        attempt_ids=[]
        for rid in request_ids:
            for row in self._c.execute('SELECT control_attempt_id FROM control_attempts WHERE control_request_id=?',(rid,)).fetchall():
                attempt_ids.append(row['control_attempt_id'])
        for aid in attempt_ids:
            for row in self._c.execute('SELECT payload_json FROM enforcement_records WHERE control_attempt_id=?',(aid,)).fetchall():
                d=json.loads(row['payload_json'])
                if d.get('attestation_status')=='verified' and d.get('outcome') in {'completed','rejected','too_late'}:
                    return True
        return False

    def _layer1_reconciled(self, active_execution_id: str) -> bool:
        rec=self._active(active_execution_id)
        for row in self._c.execute('SELECT payload FROM layer1_transitions').fetchall():
            d=json.loads(row['payload'])
            if d.get('execution_id')==rec.execution_id and d.get('attempt')==rec.attempt and d.get('configuration_id')==rec.configuration_id:
                return True
        return False

    def reconcile_recovery(self,*,active_execution_id,owner_id,owner_fence,external_control_status,effect_status,layer1_world_state_status,evidence_refs=(),provenance='live-reconciliation'):
        rr=self.get_recovery(active_execution_id); p=self.current_profile(active_execution_id); own=self.store.current_supervisory_ownership(active_execution_id)
        if not rr or not p: raise ValueError('recovery not begun')
        if not own or own['owner_id']!=owner_id or own['owner_fence']!=owner_fence or rr.owner_fence!=owner_fence: raise PermissionError('stale_owner')
        est=self.effects.current_effect_state(active_execution_id)
        effect_ok=(not p.required_effect_evidence) or (est.version>0 and not est.unresolved and effect_status==est.state)
        control_ok=(not p.required_control_reconciliation) or self._verified_control_reconciled(active_execution_id)
        world_ok=(not p.required_world_layer1_checks) or self._layer1_reconciled(active_execution_id)
        results=(('control',control_ok),('effect',effect_ok),('layer1',world_ok))
        state='reconciled' if all(v for _,v in results) else ('conflict' if 'conflict' in (external_control_status,effect_status,layer1_world_state_status) else 'unresolved')
        n=RecoveryReconciliationRecord(rr.recovery_id,rr.active_execution_id,rr.execution_id,rr.attempt,rr.new_owner_id,rr.owner_fence,rr.recovery_profile_ref,rr.durable_state_version,rr.canonical_finality_status,rr.canonical_finality_ref,'reconciled' if control_ok else 'unresolved',est.state,est.effect_record_id if est.version else None,'reconciled' if world_ok else 'unresolved',results,state,False,None,tuple(evidence_refs),provenance,rr.started_at,None)
        self._save(n); return n

    def capture_recovery_snapshot(self,*,active_execution_id,owner_id,owner_fence,created_at):
        rr=self.get_recovery(active_execution_id); own=self.store.current_supervisory_ownership(active_execution_id)
        if not rr or not own or own['owner_id']!=owner_id or own['owner_fence']!=owner_fence or rr.owner_fence!=owner_fence: raise PermissionError('stale_owner')
        snap=self.dependencies.capture_governance_snapshot(active_execution_id,created_at=created_at)
        n=RecoveryReconciliationRecord(rr.recovery_id,rr.active_execution_id,rr.execution_id,rr.attempt,rr.new_owner_id,rr.owner_fence,rr.recovery_profile_ref,rr.durable_state_version,rr.canonical_finality_status,rr.canonical_finality_ref,rr.external_control_status,rr.effect_status,rr.effect_ref,rr.layer1_world_state_status,rr.requirement_results,rr.recovery_state,False,snap.governance_snapshot_id,rr.evidence_refs,rr.provenance,rr.started_at,rr.completed_at)
        self._save(n); return snap

    def complete_recovery(self,*,active_execution_id,owner_id,owner_fence,completed_at):
        rr=self.get_recovery(active_execution_id); p=self.current_profile(active_execution_id); own=self.store.current_supervisory_ownership(active_execution_id)
        if not rr or not p or not own or own['owner_id']!=owner_id or own['owner_fence']!=owner_fence or rr.owner_fence!=owner_fence: raise PermissionError('stale_owner')
        if rr.recovery_state!='reconciled' or not rr.requirement_results or not all(v for _,v in rr.requirement_results): raise ValueError('recovery_requirement_unsatisfied')
        if p.freshness_dependency_requirements:
            snap=self.dependencies.get_snapshot(rr.governance_snapshot_id) if rr.governance_snapshot_id else None
            if not snap: raise ValueError('recovery_requirement_unsatisfied: fresh snapshot required')
            self.dependencies.validate_snapshot(snap)
        n=RecoveryReconciliationRecord(rr.recovery_id,rr.active_execution_id,rr.execution_id,rr.attempt,rr.new_owner_id,rr.owner_fence,rr.recovery_profile_ref,rr.durable_state_version,rr.canonical_finality_status,rr.canonical_finality_ref,rr.external_control_status,rr.effect_status,rr.effect_ref,rr.layer1_world_state_status,rr.requirement_results,'reconciled',True,rr.governance_snapshot_id,rr.evidence_refs,rr.provenance,rr.started_at,completed_at)
        self._save(n); return n

    def assert_resumption_allowed(self,*,active_execution_id,owner_id,owner_fence):
        rr=self.get_recovery(active_execution_id); own=self.store.current_supervisory_ownership(active_execution_id)
        if not rr or not own or own['owner_id']!=owner_id or own['owner_fence']!=owner_fence: raise PermissionError('stale_owner')
        if not rr.control_resumption_allowed: raise ValueError('recovery_requirement_unsatisfied')
        return True

    def _save(self,r):
        with self._lock:self._c.execute('UPDATE recovery_records SET payload=? WHERE active_execution_id=?',(json.dumps(asdict(r),sort_keys=True,separators=(',',':')),r.active_execution_id))
