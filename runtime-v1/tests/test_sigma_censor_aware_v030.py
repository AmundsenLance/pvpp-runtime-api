import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def rt(*orders):
    r=PVPPRegistry()
    for d in ('G1','G2','N'):
        r.register_domain(DomainDefinition(d,d,0))
    r.register_action(ActionDefinition('steady','steady',()))
    for pid,idx in orders:
        r.register_sigma_order(SigmaOrderDefinition(pid,idx))
    return PVPPRuntime(r,W())

def ev(pid,g1,g2,n,*,lp=None,censored=()):
    return PolicySetEvaluation(pid,(),True,True,{'G1':g1,'G2':g2,'N':n},(),lp,tuple(censored))

def test_exact_exact_retains_numeric_comparison():
    s=rt().evaluate_sigma_standard((ev('A',10,10,1),ev('B',9,9,100)),('G1','G2'))
    assert s.stage1.survivor_policy_ids==('A',)
    assert s.selected_policy_id=='A'

def test_right_censored_strictly_beats_exact_inside_common_window():
    # A means G1 > 20; B has exact G1=20. Both are exact/equal on G2.
    a=ev('A',20,10,0,lp=20,censored=('G1',))
    b=ev('B',20,10,5,lp=20)
    s=rt().evaluate_sigma_standard((a,b),('G1','G2'))
    assert s.stage1.survivor_policy_ids==('A',)
    assert s.selected_policy_id=='A'

def test_exact_cannot_dominate_right_censored_at_same_window():
    a=ev('A',20,10,0,lp=20,censored=('G1',))
    b=ev('B',19,10,5,lp=20)
    s=rt().evaluate_sigma_standard((a,b),('G1','G2'))
    assert s.stage1.survivor_policy_ids==('A',)

def test_two_right_censored_observations_are_comparison_equivalent():
    a=ev('A',20,20,5,lp=20,censored=('G1','G2'))
    b=ev('B',20,20,5,lp=20,censored=('G1','G2'))
    s=rt(('A',20),('B',10)).evaluate_sigma_standard((a,b),('G1','G2'))
    assert set(s.stage1.survivor_policy_ids)=={'A','B'}
    assert set(s.stage2.survivor_policy_ids)=={'A','B'}
    assert s.selected_policy_id=='B'
    assert 'infers no order beyond L_P' in s.notes[-1]

def test_censoring_requires_one_common_projection_horizon():
    a=ev('A',20,20,5,lp=20,censored=('G1',))
    b=ev('B',30,20,5,lp=30,censored=('G1',))
    try:
        rt(('A',1),('B',2)).evaluate_sigma_standard((a,b),('G1','G2'))
        assert False
    except ValueError as e:
        assert 'common licensed projection horizon' in str(e)

def test_censored_numeric_slot_must_store_projection_bound_not_fake_future_value():
    a=ev('A',25,20,5,lp=20,censored=('G1',))
    b=ev('B',19,20,5,lp=20)
    try:
        rt().evaluate_sigma_standard((a,b),('G1','G2'))
        assert False
    except ValueError as e:
        assert 'must store L_P bound' in str(e)

def test_exact_horizon_cannot_exceed_common_projection_window():
    a=ev('A',21,20,5,lp=20)
    b=ev('B',20,20,5,lp=20,censored=('G1',))
    try:
        rt().evaluate_sigma_standard((a,b),('G1','G2'))
        assert False
    except ValueError as e:
        assert 'exact Sigma horizon cannot exceed common L_P' in str(e)

def test_stage2_uses_same_censor_relation_on_non_governing_domains():
    # Governing observations are comparison-equivalent; A survives Stage 2 because
    # its N observation is censored while B collapses exactly at the bound.
    a=ev('A',10,10,20,lp=20,censored=('N',))
    b=ev('B',10,10,20,lp=20)
    s=rt().evaluate_sigma_standard((a,b),('G1','G2'))
    assert set(s.stage1.survivor_policy_ids)=={'A','B'}
    assert s.stage2.survivor_policy_ids==('A',)
    assert s.selected_policy_id=='A'

def test_authoritative_q_censor_flags_reach_sigma_without_extrapolation():
    sys.path.insert(0,str(ROOT/'examples'/'tiny_crossing_policy_world'))
    from run_crossing_choice import build_runtime, state
    runtime=build_runtime()
    runtime.registry.register_sigma_order(SigmaOrderDefinition('food_policy',20))
    runtime.registry.register_sigma_order(SigmaOrderDefinition('material_policy',10))
    space=CandidatePolicySpace((
        CandidatePolicySet('food_policy',('favor_food',),policy_class_ids=('local',)),
        CandidatePolicySet('material_policy',('favor_material',),policy_class_ids=('shift',)),
    ),('local','shift'))
    frame=DomainFrame((DomainFrameTarget('F','food_continuity'),DomainFrameTarget('M','material_continuity')))
    original=runtime.world.project_policy
    def q(st,pid,ids):
        pr=original(st,ids)
        corridors=(
            RecoveryCorridorProjection('F','food_continuity',True,True,True,2.0,20.0),
            RecoveryCorridorProjection('M','material_continuity',True,True,True,2.0,20.0),
        )
        # Both policies survive through L_P in both governing domains. They are
        # comparison-equivalent to Sigma even though no exact post-L_P horizons exist.
        return PolicyProjectionRecord(pid,True,pr.next_state,{'F':20.0,'M':20.0,'K':20.0},corridors,
                                      projection_horizon=20.0,
                                      right_censored_domain_ids=('F','M','K'))
    runtime.world.project_policy_record=q
    out=runtime.evaluate_recovery_policy_space(state(),space,frame)
    assert out.sigma is not None
    assert set(out.sigma.stage1.survivor_policy_ids)=={'food_policy','material_policy'}
    assert out.selected_policy_id=='material_policy'
