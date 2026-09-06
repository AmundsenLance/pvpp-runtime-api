
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def __init__(self, inadequate=False, terminal=False):
        self.inadequate=inadequate
        self.terminal=terminal
    def perceive(self,s): return s
    def domain_value(self,s,d): return float(s.powers.get(d,10.0))
    def project(self,s,a):
        if a.id=='steady':
            return ActionProjection(a.id,WorldState(s.time+1,{**s.powers,'G':self.domain_value(s,'G')-1}),True)
        return ActionProjection(a.id,s,True)
    def pressure_factors(self,state,did,baseline_drift):
        return PressureFactors(did,self.domain_value(state,did)-5.0,baseline_drift)
    def pressure_value(self,did,factors): return 1.0/max(factors.margin,0.1)
    def expected_deterioration(self,state,did,baseline_drift,pressure_value,pressure_factors):
        return baseline_drift
    def constraint_profile(self,state,pid,action_ids,regime,governing):
        if self.terminal:
            return PolicyConstraintProfile(pid,(ConstraintObservation('hard',True),))
        return PolicyConstraintProfile(pid,(ConstraintObservation('soft',False),))
    def compare_constraint_violation_severity(self,a,pa,b,pb,cls): return 0
    def project_policy_record(self,state,pid,action_ids):
        h=20.0 if pid=='graph:cont' else 21.0
        corridor=RecoveryCorridorProjection(
            'G','continuity',
            not self.inadequate,not self.inadequate,not self.inadequate,2.0,h
        )
        return PolicyProjectionRecord(pid,True,state,{'G':h},(corridor,),projection_horizon=30.0)

def build(*, inadequate=False, terminal=False):
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',5.0))
    for a in ('steady','continue','adjust'):
        r.register_action(ActionDefinition(a,a,('G',)))
    r.register_governing_configuration(GoverningConfiguration(0.0))
    r.register_regime_configuration(RegimeConfiguration(1,2,4,100,50,10))
    r.register_constraint_rule(ConstraintRuleDefinition('soft','soft'))
    r.register_constraint_rule(ConstraintRuleDefinition('hard','hard'))
    r.register_graph_instance(GraphInstanceDefinition('i','system',('G',),'active'))
    r.register_graph_transformation(GraphTransformationDefinition('cont','i','i','continuation',('G',),'reachable','continue',('continuation',)))
    r.register_graph_transformation(GraphTransformationDefinition('adj','i','i','maintenance_local_adjustment',('G',),'reachable','adjust',('local',)))
    r.register_sigma_order(SigmaOrderDefinition('graph:cont',20))
    r.register_sigma_order(SigmaOrderDefinition('graph:adj',10))
    return PVPPRuntime(r,W(inadequate=inadequate,terminal=terminal))

def req():
    return CanonicalDecisionCycleRequest(
        preservation_object=PreliminaryPreservationObject('p','preserve governing continuity'),
        domain_frame=DomainFrame((DomainFrameTarget('G','continuity'),)),
        required_graph_family_ids=('continuation','maintenance_local_adjustment'),
        materially_required_policy_class_ids=('continuation','local'),
    )

def st(): return WorldState(0,{'G':10.0})

def test_standard_cycle_builds_ordinary_authorized_license():
    rt=build()
    cycle=rt.evaluate_canonical_decision_cycle(st(),req())
    lic=rt.build_execution_license_from_cycle(cycle,req().domain_frame)
    assert lic.selection_mode=='standard'
    assert lic.entry_authorized
    assert lic.constraints_feasible and lic.framing_valid and lic.adequacy_sufficient
    result=rt.instantiate_execution('e-standard',lic,entry_sufficient=True,max_steps=2)
    assert result.status=='active' and not result.terminal

def test_recovery_unavailable_fallback_preserves_inadequacy_but_authorizes_entry():
    rt=build(inadequate=True)
    cycle=rt.evaluate_canonical_decision_cycle(st(),req())
    assert cycle.selection.fallback_sigma is not None
    lic=rt.build_execution_license_from_cycle(cycle,req().domain_frame)
    assert lic.selection_mode=='recovery_unavailable_fallback'
    assert lic.entry_authorized
    assert lic.constraints_feasible and lic.framing_valid
    assert not lic.adequacy_sufficient
    result=rt.instantiate_execution('e-fallback',lic,entry_sufficient=True,max_steps=2)
    assert result.status=='active' and not result.terminal

def test_terminal_sigma_selection_produces_blocked_not_laundered_license():
    rt=build(terminal=True)
    cycle=rt.evaluate_canonical_decision_cycle(st(),req())
    assert cycle.selection.terminal_sigma is not None
    lic=rt.build_execution_license_from_cycle(cycle,req().domain_frame)
    assert lic.selection_mode=='terminal_infeasibility'
    assert not lic.entry_authorized
    assert not lic.constraints_feasible
    assert not lic.framing_valid
    assert not lic.adequacy_sufficient
    result=rt.instantiate_execution('e-terminal',lic,entry_sufficient=True,max_steps=2)
    assert result.status=='aborted_return'
    assert result.terminal and result.return_upstream

def test_mode_flags_cannot_launder_invalid_fallback_posture():
    rt=build()
    lic=ExecutionLicenseEnvelope(
        'p',('a',),('G',),('continuity',),
        True,False,True,False,(),
        selection_mode='recovery_unavailable_fallback',entry_authorized=True
    )
    result=rt.instantiate_execution('e-bad',lic,entry_sufficient=True,max_steps=2)
    assert result.status=='aborted_return'

def test_unknown_selection_mode_fails_closed():
    rt=build()
    lic=ExecutionLicenseEnvelope(
        'p',('a',),('G',),('continuity',),
        True,True,True,True,(),
        selection_mode='mystery',entry_authorized=True
    )
    try:
        rt.instantiate_execution('e-x',lic,entry_sufficient=True,max_steps=2)
        assert False
    except ValueError as e:
        assert 'unknown epsilon selection mode' in str(e)
