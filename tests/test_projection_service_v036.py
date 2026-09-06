import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def __init__(self): self.legacy_q_calls=0
    def perceive(self,s): return s
    def domain_value(self,s,d): return float(s.powers[d])
    def project(self,s,a):
        if a.id=='steady':
            return ActionProjection(a.id,WorldState(s.time+1,{**s.powers,'G':s.powers['G']-1},s.metadata),True)
        return ActionProjection(a.id,s,True)
    def pressure_factors(self,state,did,baseline_drift): return PressureFactors(did,self.domain_value(state,did)-5.0,baseline_drift)
    def pressure_value(self,did,factors): return 1.0/max(factors.margin,0.1)
    def expected_deterioration(self,state,did,baseline_drift,pressure_value,pressure_factors): return baseline_drift
    def constraint_profile(self,state,pid,action_ids,regime,governing): return PolicyConstraintProfile(pid,(ConstraintObservation('soft',False),))
    def project_policy_record(self,*args):
        self.legacy_q_calls += 1
        raise AssertionError('legacy projection hook must not be used when canonical service is attached')

class Service:
    def __init__(self, mutate=None): self.calls=[]; self.mutate=mutate
    def project(self,req):
        self.calls.append(req)
        h=20.0 if req.policy_id=='graph:cont' else 21.0
        rec=PolicyProjectionRecord(
            req.policy_id,False,req.represented_state,{'G':h},
            (RecoveryCorridorProjection('G','continuity',True,True,True,2.0,h),),
            projection_horizon=req.projection_horizon,
            state_id=req.state_id,state_time=req.represented_state.time,
            candidate_mode=req.candidate_mode,
            projected_domain_trajectories={'G':(10.0,9.0)},
            reachable_viable={'G':('i',)},
            information_quality_trace={'basis':'test'},
            model_version='test-model-v1',
            projection_input_trace={'state_time':req.represented_state.time,'policy_id':req.policy_id},
        )
        return self.mutate(rec) if self.mutate else rec

def build(service):
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',5.0))
    for a in ('steady','continue','adjust'): r.register_action(ActionDefinition(a,a,('G',)))
    r.register_governing_configuration(GoverningConfiguration(0.0))
    r.register_regime_configuration(RegimeConfiguration(1,2,4,100,50,10))
    r.register_constraint_rule(ConstraintRuleDefinition('soft','soft'))
    r.register_graph_instance(GraphInstanceDefinition('i','system',('G',),'active'))
    r.register_graph_transformation(GraphTransformationDefinition('cont','i','i','continuation',('G',),'reachable','continue',('continuation',)))
    r.register_graph_transformation(GraphTransformationDefinition('adj','i','i','maintenance_local_adjustment',('G',),'reachable','adjust',('local',)))
    r.register_sigma_order(SigmaOrderDefinition('graph:cont',20)); r.register_sigma_order(SigmaOrderDefinition('graph:adj',10))
    w=W(); return PVPPRuntime(r,w,service),w

def req(lp=30.0):
    return CanonicalDecisionCycleRequest(
        PreliminaryPreservationObject('p','preserve governing continuity'),
        DomainFrame((DomainFrameTarget('G','continuity'),)),
        required_graph_family_ids=('continuation','maintenance_local_adjustment'),
        materially_required_policy_class_ids=('continuation','local'),
        projection_horizon=lp,
        projection_input_trace={'snapshot':'represented-t0'},
    )

def state(): return WorldState(0,{'G':10.0},{'state_id':'s0'})

def test_canonical_service_is_preferred_and_q_feasible_does_not_override_constraints():
    svc=Service(); rt,w=build(svc)
    out=rt.evaluate_canonical_decision_cycle(state(),req())
    assert out.status=='sigma_standard_policy_selected'
    assert out.selection.selected_policy_id=='graph:adj'
    assert len(svc.calls)==2 and w.legacy_q_calls==0
    assert {c.candidate_mode for c in svc.calls}=={'ordinary_adequacy'}
    assert {c.projection_horizon for c in svc.calls}=={30.0}
    # Service deliberately returned legacy feasible=False; canonical Constraints owns feasibility.
    assert out.constraints.feasible_policy_ids==('graph:cont','graph:adj')


def test_service_requires_explicit_finite_projection_horizon():
    svc=Service(); rt,_=build(svc)
    try: rt.evaluate_canonical_decision_cycle(state(),req(None)); assert False
    except (ValueError,TypeError) as e: assert 'L_P' in str(e) or 'projection' in str(e)


def test_record_rejects_candidate_mode_mismatch():
    from dataclasses import replace
    svc=Service(lambda r: replace(r,candidate_mode='fallback'))
    rt,_=build(svc)
    try: rt.evaluate_canonical_decision_cycle(state(),req()); assert False
    except ValueError as e: assert 'candidate_mode' in str(e)


def test_record_rejects_missing_model_or_input_trace():
    from dataclasses import replace
    for mut,word in ((lambda r:replace(r,model_version=''),'model_version'),(lambda r:replace(r,projection_input_trace={}),'projection_input_trace')):
        rt,_=build(Service(mut))
        try: rt.evaluate_canonical_decision_cycle(state(),req()); assert False
        except ValueError as e: assert word in str(e)


def test_record_rejects_exact_horizon_beyond_LP():
    from dataclasses import replace
    rt,_=build(Service(lambda r:replace(r,projected_horizons={'G':31.0})))
    try: rt.evaluate_canonical_decision_cycle(state(),req()); assert False
    except ValueError as e: assert '[0, L_P]' in str(e)


def test_right_censoring_requires_bound_and_is_valid_when_consistent():
    from dataclasses import replace
    good=lambda r:replace(r,projected_horizons={'G':30.0},right_censored_domain_ids=('G',),recovery_corridors=(RecoveryCorridorProjection('G','continuity',True,True,True,2.0,None),))
    rt,_=build(Service(good)); out=rt.evaluate_canonical_decision_cycle(state(),req())
    assert all(rec.right_censored_domain_ids==('G',) for rec in out.projection_records)
    bad=lambda r:replace(r,projected_horizons={'G':29.0},right_censored_domain_ids=('G',))
    rt,_=build(Service(bad))
    try: rt.evaluate_canonical_decision_cycle(state(),req()); assert False
    except ValueError as e: assert 'censoring bound' in str(e)


def test_duplicate_corridor_fact_fails_closed():
    from dataclasses import replace
    def dup(r): return replace(r,recovery_corridors=r.recovery_corridors+r.recovery_corridors)
    rt,_=build(Service(dup))
    try: rt.evaluate_canonical_decision_cycle(state(),req()); assert False
    except ValueError as e: assert 'at most one recovery-corridor fact' in str(e)
