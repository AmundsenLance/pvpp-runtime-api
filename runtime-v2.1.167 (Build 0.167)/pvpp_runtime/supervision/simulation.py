"""Runtime 2.2 Phase-9 deterministic simulation adapters.

Simulation controls timing and injected external outcomes only.  All semantic state
changes are delegated to the production supervisory services.
"""
from __future__ import annotations
from dataclasses import dataclass
from heapq import heappush, heappop
from typing import Callable, Any
from .observation import ObservationService, ExternalObservation
from .control import ControlService
from .effect import EffectService
from .recovery import RecoveryService

@dataclass(frozen=True, slots=True)
class SimulationEvent:
    at:int; sequence:int; label:str

class DeterministicScheduler:
    def __init__(self): self._q=[]; self._seq=0; self.trace=[]
    def schedule(self,at:int,label:str,fn:Callable[[],Any]):
        self._seq+=1; heappush(self._q,(at,self._seq,label,fn))
    def run(self):
        out=[]
        while self._q:
            at,seq,label,fn=heappop(self._q); value=fn(); self.trace.append(SimulationEvent(at,seq,label)); out.append((label,value))
        return tuple(out)

class SimulationObservationSource:
    def __init__(self,service:ObservationService): self.service=service
    def inject(self,o:ExternalObservation,*,assessed_at:str,committed_at:str,permitted_use='governance'):
        self.service.submit_observation(o)
        a=self.service.assess_observation(o,assessed_at=assessed_at,permitted_use=permitted_use)
        return a,self.service.commit_admission_change(o,a,committed_at=committed_at)

class SimulationEnforcementAdapter:
    def __init__(self,service:ControlService): self.service=service
    def dispatch(self,**kwargs): return self.service.dispatch_control_request(**kwargs)
    def outcome(self,**kwargs): return self.service.record_enforcement_outcome(**kwargs)

class SimulationEffectSource:
    def __init__(self,service:EffectService): self.service=service
    def inject_and_reconcile(self,*,updated_at,control_enforcement_refs=(),compensation_refs=(),**kwargs):
        e=self.service.submit_effect_evidence(**kwargs)
        return e,self.service.reconcile_effect(active_execution_id=kwargs['active_execution_id'],effect_evidence_id=e.effect_evidence_id,updated_at=updated_at,control_enforcement_refs=control_enforcement_refs,compensation_refs=compensation_refs)

class CrashFailoverInjector:
    def __init__(self,recovery:RecoveryService): self.recovery=recovery
    def failover(self,*,active_execution_id,new_owner_id,started_at,provenance='simulation-crash'):
        return self.recovery.begin_recovery(active_execution_id=active_execution_id,new_owner_id=new_owner_id,started_at=started_at,provenance=provenance)

class SimulationAuditOracle:
    """Read-only assertions over durable production records; never mutates state."""
    def __init__(self,store): self.store=store
    def table_count(self,table):
        allowed={'observations','observation_admissions','admitted_fact_changes','control_requests','control_attempts','enforcement_records','effect_evidence','world_effect_state','recovery_records'}
        if table not in allowed: raise ValueError('unsupported audit table')
        return self.store._conn.execute(f'SELECT count(*) n FROM {table}').fetchone()['n']
    def current_owner(self,active_execution_id): return self.store.current_supervisory_ownership(active_execution_id)
