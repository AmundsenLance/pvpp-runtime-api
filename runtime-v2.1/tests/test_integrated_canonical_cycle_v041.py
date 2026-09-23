
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def __init__(self,terminal=False):
        self.terminal=terminal
        self.map_calls=0
    def represented_state_from_actual(self,s):
        self.map_calls+=1
        return WorldState(s.time,{'G':10.0},{'state_id':s.state_id})
    def perceive(self,s): return s
    def domain_value(self,s,d): return float(s.powers.get(d,10.0))
    def project(self,s,a):
        if a.id=='steady':
            return ActionProjection(a.id,WorldState(s.time+1,{**s.powers,'G':self.domain_value(s,'G')-1},dict(s.metadata)),True)
        return ActionProjection(a.id,s,True)
    def pressure_factors(self,state,did,baseline_drift):
        return PressureFactors(did,self.domain_value(state,did)-5.0,baseline_drift)
    def pressure_value(self,did,factors): return 1.0/max(factors.margin,0.1)
    def expected_deterioration(self,state,did,baseline_drift,pressure_value,pressure_factors): return baseline_drift
    def constraint_profile(self,state,pid,action_ids,regime,governing):
        if self.terminal: return PolicyConstraintProfile(pid,(ConstraintObservation('hard',True),))
        return PolicyConstraintProfile(pid,(ConstraintObservation('soft',False),))
    def compare_constraint_violation_severity(self,a,pa,b,pb,cls): return 0
    def project_policy_record(self,state,pid,action_ids):
        h=20.0 if pid=='graph:cont' else 21.0
        corridor=RecoveryCorridorProjection('G','continuity',True,True,True,2.0,h)
        return PolicyProjectionRecord(pid,True,state,{'G':h},(corridor,),projection_horizon=30.0)

class T:
    def __init__(self): self.calls=0
    def transition(self,current,handoff):
        self.calls+=1
        nxt=ActualPersistentStateEnvelope(current.actor_id,current.state_id+'-next',current.time+1,
                                          current.pp,current.spv,current.avs,current.context)
        return Layer1TransitionResult(handoff.episode_id,handoff.selected_policy_id,current.state_id,
                                      nxt,True,{'exclusive_transition':True})

def build(*,terminal=False,transition=True):
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',5.0))
    for a in ('steady','continue','adjust'): r.register_action(ActionDefinition(a,a,('G',)))
    r.register_governing_configuration(GoverningConfiguration(0.0))
    r.register_regime_configuration(RegimeConfiguration(1,2,4,100,50,10))
    r.register_constraint_rule(ConstraintRuleDefinition('soft','soft'))
    r.register_constraint_rule(ConstraintRuleDefinition('hard','hard'))
    r.register_graph_instance(GraphInstanceDefinition('i','system',('G',),'active'))
    r.register_graph_transformation(GraphTransformationDefinition('cont','i','i','continuation',('G',),'reachable','continue',('continuation',)))
    r.register_graph_transformation(GraphTransformationDefinition('adj','i','i','maintenance_local_adjustment',('G',),'reachable','adjust',('local',)))
    r.register_sigma_order(SigmaOrderDefinition('graph:cont',20))
    r.register_sigma_order(SigmaOrderDefinition('graph:adj',10))
    w=W(terminal=terminal); t=T() if transition else None
    return PVPPRuntime(r,w,layer1_transition_service=t),w,t

def req():
    return CanonicalDecisionCycleRequest(
        PreliminaryPreservationObject('p','preserve governing continuity'),
        DomainFrame((DomainFrameTarget('G','continuity'),)),
        ('continuation','maintenance_local_adjustment'),(),('continuation','local')
    )

def actual():
    return ActualPersistentStateEnvelope('actor','s0',0.0,{'opaque':'pp'},{'opaque':'spv'},{'opaque':'avs'},{'opaque':'x'})

def test_integrated_cycle_default_stops_at_sigma_without_epsilon_or_transition():
    rt,w,t=build()
    out=rt.evaluate_integrated_canonical_cycle(actual(),req())
    assert out.status=='integrated_cycle_selected_not_executed'
    assert out.decision.stopped_at=='Sigma'
    assert out.execution_license is None and out.epsilon_result is None
    assert t.calls==0 and w.map_calls==1
    assert out.final_actual_state.state_id=='s0'

def test_explicit_execution_can_complete_and_apply_one_layer1_transition():
    rt,w,t=build()
    obs=(ExecutionObservation('ev',completed=True,realized_pv_bundle={'pv':1}),)
    out=rt.evaluate_integrated_canonical_cycle(actual(),req(),execute=True,episode_id='ep',
                                                max_execution_steps=2,execution_observations=obs)
    assert out.status=='integrated_cycle_transition_applied'
    assert out.epsilon_result.status=='completed'
    assert out.handoff.episode_id=='ep'
    assert out.transition_validation.valid
    assert out.final_actual_state.state_id=='s0-next'
    assert t.calls==1 and w.map_calls==1

def test_execution_without_observation_remains_active_and_does_not_transition():
    rt,w,t=build()
    out=rt.evaluate_integrated_canonical_cycle(actual(),req(),execute=True,max_execution_steps=2)
    assert out.status=='integrated_cycle_execution_active'
    assert out.epsilon_result is None
    assert t.calls==0

def test_terminal_sigma_is_selected_but_execution_remains_blocked():
    rt,w,t=build(terminal=True)
    out=rt.evaluate_integrated_canonical_cycle(actual(),req(),execute=True)
    assert out.decision.selection.terminal_sigma is not None
    assert out.status=='integrated_cycle_execution_blocked'
    assert out.epsilon_result.status=='aborted_return'
    assert out.handoff is None
    assert t.calls==0

def test_represented_state_time_must_align_with_actual_state():
    rt,w,t=build()
    def bad(s): return WorldState(s.time+1,{'G':10.0},{'state_id':s.state_id})
    w.represented_state_from_actual=bad
    try:
        rt.prepare_canonical_cycle_snapshot(actual()); assert False
    except ValueError as e:
        assert 'time must align' in str(e)

def test_represented_state_identity_must_align_when_declared():
    rt,w,t=build()
    def bad(s): return WorldState(s.time,{'G':10.0},{'state_id':'wrong'})
    w.represented_state_from_actual=bad
    try:
        rt.prepare_canonical_cycle_snapshot(actual()); assert False
    except ValueError as e:
        assert 'state_id does not match' in str(e)

def test_integrated_cycle_never_re_evaluates_after_transition_automatically():
    rt,w,t=build()
    obs=(ExecutionObservation('ev',completed=True),)
    out=rt.evaluate_integrated_canonical_cycle(actual(),req(),execute=True,execution_observations=obs)
    assert out.final_actual_state.state_id=='s0-next'
    # Exactly one actual->represented mapping proves no hidden second decision cycle.
    assert w.map_calls==1
    assert t.calls==1

def test_missing_layer1_transition_service_is_visible_not_silently_mutated():
    rt,w,t=build(transition=False)
    obs=(ExecutionObservation('ev',completed=True),)
    try:
        rt.evaluate_integrated_canonical_cycle(actual(),req(),execute=True,execution_observations=obs)
        assert False
    except ValueError as e:
        assert 'no Layer1TransitionService' in str(e)
