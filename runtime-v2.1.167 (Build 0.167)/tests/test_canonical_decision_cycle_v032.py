import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def __init__(self):
        self.perceive_calls=0; self.baseline_calls=0; self.q_calls=[]
    def perceive(self,s):
        self.perceive_calls += 1; return s
    def domain_value(self,s,d):
        return float(s.powers.get(d,10.0))
    def project(self,s,a):
        if a.id=='steady': self.baseline_calls += 1
        if a.id=='steady':
            return ActionProjection(a.id,WorldState(s.time+1,{**s.powers,'G':self.domain_value(s,'G')-1}),True)
        return ActionProjection(a.id,s,True)
    def pressure_factors(self,state,did,baseline_drift):
        return PressureFactors(did,self.domain_value(state,did)-5.0,baseline_drift)
    def pressure_value(self,did,factors):
        return 1.0/max(factors.margin,0.1)
    def expected_deterioration(self,state,did,baseline_drift,pressure_value,pressure_factors):
        return baseline_drift
    def constraint_profile(self,state,pid,action_ids,regime,governing):
        return PolicyConstraintProfile(pid,(ConstraintObservation('soft',False),))
    def project_policy_record(self,state,pid,action_ids):
        self.q_calls.append(pid)
        h=20.0 if pid=='graph:cont' else 21.0
        return PolicyProjectionRecord(
            pid,True,state,{'G':h},
            (RecoveryCorridorProjection('G','continuity',True,True,True,2.0,h),),
            projection_horizon=30.0
        )

def build():
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',5.0))
    for a in ('steady','continue','adjust'):
        r.register_action(ActionDefinition(a,a,('G',)))
    r.register_governing_configuration(GoverningConfiguration(0.0))
    r.register_regime_configuration(RegimeConfiguration(1,2,4,100,50,10))
    r.register_constraint_rule(ConstraintRuleDefinition('soft','soft'))
    r.register_graph_instance(GraphInstanceDefinition('i','system',('G',),'active'))
    r.register_graph_transformation(GraphTransformationDefinition('cont','i','i','continuation',('G',),'reachable','continue',('continuation',)))
    r.register_graph_transformation(GraphTransformationDefinition('adj','i','i','maintenance_local_adjustment',('G',),'reachable','adjust',('local',)))
    r.register_sigma_order(SigmaOrderDefinition('graph:cont',20))
    r.register_sigma_order(SigmaOrderDefinition('graph:adj',10))
    w=W(); return PVPPRuntime(r,w),w

def req(**kw):
    base=dict(
        preservation_object=PreliminaryPreservationObject('p','preserve governing continuity'),
        domain_frame=DomainFrame((DomainFrameTarget('G','continuity'),)),
        required_graph_family_ids=('continuation','maintenance_local_adjustment'),
        materially_required_policy_class_ids=('continuation','local'),
    ); base.update(kw); return CanonicalDecisionCycleRequest(**base)

def state(): return WorldState(0,{'G':10.0})

def test_full_cycle_runs_exact_order_and_stops_before_epsilon():
    rt,w=build(); a=rt.evaluate_canonical_decision_cycle(state(),req())
    assert a.status=='sigma_standard_policy_selected'
    assert a.selection.selected_policy_id=='graph:adj'
    assert a.pipeline_trace==('PPP','Phi','H','G','R','Graph/Seed','Pi','Pi Completeness','Constraints','Domain Framing','Adequacy','Sigma')
    assert 'epsilon' not in a.pipeline_trace
    assert w.perceive_calls==1
    assert w.baseline_calls==1
    assert set(w.q_calls)=={'graph:cont','graph:adj'} and len(w.q_calls)==2

def test_graph_failure_stops_before_pi_and_q():
    rt,w=build(); bad=req(required_graph_family_ids=('continuation','substitution'))
    a=rt.evaluate_canonical_decision_cycle(state(),bad)
    assert a.stopped_at=='Graph/Seed'; assert a.pi_construction is None; assert w.q_calls==[]

def test_pi_completeness_failure_stops_before_constraints_and_q():
    rt,w=build(); bad=req(materially_required_policy_class_ids=('continuation','local','missing'))
    a=rt.evaluate_canonical_decision_cycle(state(),bad)
    assert a.stopped_at=='Pi Completeness'; assert a.constraints is None; assert w.q_calls==[]

def test_domain_framing_failure_stops_before_q_and_adequacy():
    rt,w=build(); bad=req(domain_frame=DomainFrame((DomainFrameTarget('G','',locked=True),)))
    a=rt.evaluate_canonical_decision_cycle(state(),bad)
    assert a.stopped_at=='Domain Framing'; assert a.adequacy is None; assert w.q_calls==[]

def test_constraints_filter_before_q():
    rt,w=build()
    rt.registry.register_constraint_rule(ConstraintRuleDefinition('hard','hard'))
    def profiler(st,pid,action_ids,regime,governing):
        obs=(ConstraintObservation('hard',pid=='graph:cont'),ConstraintObservation('soft',False))
        return PolicyConstraintProfile(pid,obs)
    w.constraint_profile=profiler
    a=rt.evaluate_canonical_decision_cycle(state(),req())
    assert a.constraints.infeasible_policy_ids==('graph:cont',)
    assert w.q_calls==['graph:adj']
    assert a.selection.selected_policy_id=='graph:adj'

def test_total_constraint_failure_enters_terminal_sigma_without_domain_framing_or_q():
    rt,w=build(); rt.registry.register_constraint_rule(ConstraintRuleDefinition('hard','hard'))
    w.constraint_profile=lambda st,pid,action_ids,regime,governing: PolicyConstraintProfile(pid,(ConstraintObservation('hard',True),))
    w.compare_constraint_violation_severity=lambda a,pa,b,pb,cls: 0
    a=rt.evaluate_canonical_decision_cycle(state(),req())
    assert a.stopped_at=='Sigma'; assert a.status=='sigma_terminal_policy_selected'
    assert a.selection.selected_policy_id=='graph:adj'
    assert a.domain_framing is None; assert a.adequacy is None; assert w.q_calls==[]

def test_q_contradiction_with_constraint_feasibility_fails_closed():
    rt,w=build()
    def badq(st,pid,action_ids): return PolicyProjectionRecord(pid,False,None,{},(),reasons=('no',))
    w.project_policy_record=badq
    try: rt.evaluate_canonical_decision_cycle(state(),req()); assert False
    except ValueError as e: assert 'contradicts canonical Constraints' in str(e)
