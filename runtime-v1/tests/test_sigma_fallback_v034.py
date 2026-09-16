import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def rt(alpha=.05):
    reg=PVPPRegistry()
    for d in ('G1','G2'):
        reg.register_domain(DomainDefinition(d,d,0))
    reg.register_action(ActionDefinition('steady','steady',()))
    reg.register_fallback_configuration(FallbackConfiguration(alpha))
    return PVPPRuntime(reg,W())

def ev(pid,g1,g2,*,lp=None,censored=()):
    return PolicySetEvaluation(pid,(),True,False,{'G1':g1,'G2':g2},(),lp,censored)

def fp(pid,damage=(),maneuver=(),irr=0,nm=0,spill=0):
    return FallbackStructuralProfile(pid,damage,maneuver,irr,nm,spill)

def test_singleton_fallback_maximal_set_selects_without_structural_profile():
    s=rt().evaluate_sigma_fallback((ev('A',10,10),ev('B',9,9)),('G1','G2'))
    assert s.selected_policy_id=='A'
    assert s.status=='fallback_singleton_maximal_selected'

def test_pairwise_marginal_advantage_can_be_overridden_by_categorical_critical_damage():
    # A wins ordered collapse vector [10, 20] over B [9.6, 20]; 0.4 <= .05*9.6.
    r=rt(.05)
    s=r.evaluate_sigma_fallback(
        (ev('A',10,20),ev('B',9.6,21)),('G1','G2'),
        (fp('A',damage=('critical_support',)),fp('B'))
    )
    assert s.selected_policy_id=='B'
    assert s.stage2_override_policy_id=='B'
    assert s.status=='fallback_stage2_override_selected'

def test_nonmarginal_advantage_cannot_be_overridden():
    r=rt(.05)
    s=r.evaluate_sigma_fallback(
        (ev('A',12,20),ev('B',9.6,21)),('G1','G2'),
        (fp('A',damage=('critical_support',)),fp('B'))
    )
    assert s.selected_policy_id=='A'
    assert s.stage2_override_policy_id is None

def test_right_censoring_is_preserved_in_fallback_comparison_without_extrapolation():
    r=rt(.50)
    s=r.evaluate_sigma_fallback(
        (ev('A',10,20,lp=20,censored=('G2',)),ev('B',11,19,lp=20)),('G1','G2'),
        (fp('A'),fp('B'))
    )
    # Both are Pareto-nondominated. B wins Stage 1 on the earlier-collapse coordinate;
    # the censored A coordinate is only treated as >L_P, never extrapolated beyond 20.
    assert set(s.maximal_policy_ids)=={'A','B'}
    assert s.selected_policy_id=='B'

def test_stage1_tie_uses_stage3_lexicographic_structure_without_weighting():
    r=rt()
    s=r.evaluate_sigma_fallback(
        (ev('A',10,20),ev('B',20,10)),('G1','G2'),
        (fp('A',irr=1,nm=100,spill=0),fp('B',irr=0,nm=0,spill=100))
    )
    # lower irreversibility is first Stage-3 axis, so B wins despite worse lower axes.
    assert s.selected_policy_id=='B'
    assert s.status=='fallback_stage3_selected'

def test_stage4_requires_explicit_deterministic_order_after_structural_tie():
    r=rt(); r.registry.register_sigma_order(SigmaOrderDefinition('A',5)); r.registry.register_sigma_order(SigmaOrderDefinition('B',2))
    s=r.evaluate_sigma_fallback(
        (ev('A',10,20),ev('B',20,10)),('G1','G2'),(fp('A'),fp('B'))
    )
    assert s.selected_policy_id=='B'
    assert s.status=='fallback_stage4_tie_selected'
    assert s.selected_order_index==2

def test_multiway_stage2_composition_fails_closed_instead_of_inventing_tournament_rule():
    r=rt()
    vals=(ev('A',12,5),ev('B',11,6),ev('C',10,7))
    # all are Pareto crossing; A has unique lexicographic ordered-vector winner.
    s=r.evaluate_sigma_fallback(vals,('G1','G2'),(fp('A'),fp('B'),fp('C')))
    assert s.selected_policy_id is None
    assert s.status=='fallback_multiway_override_not_formalized'

def test_canonical_cycle_enters_recovery_unavailable_fallback_without_reprojection():
    from tests.test_canonical_decision_cycle_v032 import build, state, req
    runtime,w=build()
    runtime.registry.register_fallback_configuration(FallbackConfiguration(.05))
    def q(st,pid,action_ids):
        w.q_calls.append(pid)
        h={'graph:cont':10.0,'graph:adj':20.0}[pid]
        return PolicyProjectionRecord(
            pid,True,st,{'G':h},
            (RecoveryCorridorProjection('G','continuity',False,False,False,None,h),),
            projection_horizon=30.0
        )
    w.project_policy_record=q
    w.fallback_structure_profile=lambda st,pid,action_ids,governing: FallbackStructuralProfile(pid)
    a=runtime.evaluate_canonical_decision_cycle(state(),req())
    assert a.stopped_at=='Sigma'
    assert a.adequacy.adequate_policy_ids==()
    assert a.selection.selected_policy_id=='graph:adj'
    assert a.selection.fallback_sigma is not None
    assert set(w.q_calls)=={'graph:cont','graph:adj'} and len(w.q_calls)==2
