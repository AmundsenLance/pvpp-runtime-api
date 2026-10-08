"""Runtime 2.2 Phase-10 operational adapter pilot.

Thin host-boundary adapters only.  They normalize/relay external evidence and exact
control operations through the production supervisory services.  They do not own
PV-PP governance, choose remedies, establish world effect by controller status, or
create Layer-1 truth without explicit host authority.
"""
from __future__ import annotations
from .observation import ObservationService, ExternalObservation
from .control import ControlService
from .effect import EffectService

class OperationalObservationAdapter:
    def __init__(self, service: ObservationService): self.service=service
    def admit(self, observation: ExternalObservation, *, assessed_at: str, committed_at: str, permitted_use: str='governance'):
        self.service.submit_observation(observation)
        assessment=self.service.assess_observation(observation,assessed_at=assessed_at,permitted_use=permitted_use)
        change=self.service.commit_admission_change(observation,assessment,committed_at=committed_at)
        return assessment,change

class OperationalEnforcementAdapter:
    def __init__(self, service: ControlService): self.service=service
    def dispatch_exact(self, **kwargs): return self.service.dispatch_control_request(**kwargs)
    def report_outcome(self, **kwargs): return self.service.record_enforcement_outcome(**kwargs)

class OperationalEffectAdapter:
    def __init__(self, service: EffectService): self.service=service
    def admit_and_reconcile(self, *, updated_at: str, control_enforcement_refs=(), compensation_refs=(), **kwargs):
        evidence=self.service.submit_effect_evidence(**kwargs)
        state=self.service.reconcile_effect(active_execution_id=kwargs['active_execution_id'],effect_evidence_id=evidence.effect_evidence_id,updated_at=updated_at,control_enforcement_refs=control_enforcement_refs,compensation_refs=compensation_refs)
        return evidence,state

class HostLayer1Authority:
    """Explicit host/world authority boundary; Runtime does not infer this transition."""
    def __init__(self, effects: EffectService): self.effects=effects
    def commit(self, **kwargs):
        return self.effects.record_layer1_transition(host_authoritative=True,**kwargs)
