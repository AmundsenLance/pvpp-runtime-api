import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'examples'/'tiny_crossing_policy_world'))

from pvpp_runtime import *
from run_crossing_choice import build_runtime, state

def space(two=True):
    cs=[CandidatePolicySet('food_policy',('favor_food',),policy_class_ids=('local',))]
    req=['local']
    if two:
        cs.append(CandidatePolicySet('material_policy',('favor_material',),policy_class_ids=('shift',)))
        req.append('shift')
    return CandidatePolicySpace(tuple(cs),tuple(req))

def frame():
    return DomainFrame((
        DomainFrameTarget('F','food_continuity'),
        DomainFrameTarget('M','material_continuity'),
    ))

def install_q(rt, *, fail_policy=None, missing_region_policy=None,
              joint_fail_policy=None, wrong_function_policy=None):
    calls={'n':0}
    original=rt.world.project_policy
    def q(st,pid,ids):
        calls['n']+=1
        pr=original(st,ids)
        feasible=(pid != fail_policy)
        if pid=='food_policy':
            hs={'F':4.5,'M':4.0,'K':float('inf')}
        else:
            hs={'F':4.0,'M':4.5,'K':float('inf')}
        corridors=[]
        for d,fid in [('F','food_continuity'),('M','material_continuity')]:
            function_id=fid
            if pid==wrong_function_policy and d=='F':
                function_id='wrong_mechanism'
            reached=not (pid==missing_region_policy and d=='F')
            joint=not (pid==joint_fail_policy and d=='M')
            corridors.append(RecoveryCorridorProjection(
                d,function_id,True,reached,joint,2.0,20.0
            ))
        return PolicyProjectionRecord(
            pid,feasible,pr.next_state if feasible else None,hs,
            tuple(corridors),reasons=(() if feasible else ('host infeasible',))
        )
    rt.world.project_policy_record=q
    if 'food_policy' not in rt.registry.sigma_order:
        rt.registry.register_sigma_order(SigmaOrderDefinition('food_policy',10))
    if 'material_policy' not in rt.registry.sigma_order:
        rt.registry.register_sigma_order(SigmaOrderDefinition('material_policy',20))
    return calls

def test_full_recovery_corridors_feed_sigma_without_ranking_inside_adequacy():
    rt=build_runtime(); install_q(rt)
    a=rt.evaluate_recovery_policy_space(state(),space(),frame())
    assert a.adequacy.status=='adequacy_passed_some_policies'
    assert set(a.adequacy.adequate_policy_ids)=={'food_policy','material_policy'}
    assert a.status=='sigma_standard_policy_selected'
    assert a.selected_policy_id=='food_policy'

def test_horizon_extension_alone_does_not_establish_adequacy():
    rt=build_runtime(); install_q(rt,missing_region_policy='food_policy')
    a=rt.evaluate_recovery_policy_space(state(),space(two=False),frame())
    ev=a.evaluations[0]
    assert ev.projected_horizons['F']==4.5
    assert ev.adequate is False
    assert a.status=='no_adequate_policy_set'
    dr=a.adequacy.policy_results[0].domain_results[0]
    assert dr.recovery_capable_region_reached is False

def test_joint_sustainment_failure_in_one_governing_domain_rejects_whole_policy():
    rt=build_runtime(); install_q(rt,joint_fail_policy='food_policy')
    a=rt.evaluate_recovery_policy_space(state(),space(two=False),frame())
    assert a.adequacy.policy_results[0].adequate is False
    assert a.adequacy.policy_results[0].domain_results[1].joint_sustainment_supported is False

def test_exact_framed_function_must_be_present_in_q_record():
    rt=build_runtime(); install_q(rt,wrong_function_policy='food_policy')
    a=rt.evaluate_recovery_policy_space(state(),space(two=False),frame())
    assert a.adequacy.policy_results[0].adequate is False
    assert 'lacks a recovery-corridor fact' in a.adequacy.policy_results[0].domain_results[0].reasons[0]

def test_constraint_infeasibility_from_q_prevents_adequacy_for_that_policy():
    rt=build_runtime(); install_q(rt,fail_policy='material_policy')
    a=rt.evaluate_recovery_policy_space(state(),space(),frame())
    assert a.constraints.infeasible_policy_ids==('material_policy',)
    assert a.adequacy.adequate_policy_ids==('food_policy',)
    assert a.selected_policy_id=='food_policy'

def test_strict_recovery_path_requires_authoritative_q_service():
    rt=build_runtime()
    try:
        rt.evaluate_recovery_policy_space(state(),space(two=False),frame())
        assert False
    except ValueError as e:
        assert 'authoritative Q_t(pi)' in str(e)

def test_q_projection_is_called_once_per_candidate_and_project_policy_is_not_repeated():
    rt=build_runtime(); calls=install_q(rt)
    original_q=rt.world.project_policy_record
    # q itself uses the old project_policy only to synthesize a test terminal state.
    # Count Q service calls: strict runtime must consume each Q exactly once.
    a=rt.evaluate_recovery_policy_space(state(),space(),frame())
    assert calls['n']==2
    assert len(a.evaluations)==2

def test_candidate_order_does_not_change_adequacy_or_crossing_result():
    rt1=build_runtime(); install_q(rt1)
    normal=space()
    a=rt1.evaluate_recovery_policy_space(state(),normal,frame())
    rt2=build_runtime(); install_q(rt2)
    rev=CandidatePolicySpace(tuple(reversed(normal.candidates)),tuple(reversed(normal.materially_required_class_ids)))
    b=rt2.evaluate_recovery_policy_space(state(),rev,frame())
    assert set(a.adequacy.adequate_policy_ids)==set(b.adequacy.adequate_policy_ids)
    assert a.status==b.status=='sigma_standard_policy_selected'
    assert a.selected_policy_id==b.selected_policy_id=='food_policy'

def test_epsilon_license_refuses_compatibility_horizon_adequacy():
    rt=build_runtime()
    compat=rt.evaluate_framed_policy_space(state(),space(two=False),frame())
    assert compat.selected_policy_id=='food_policy'
    assert compat.adequacy is None
    try:
        rt.build_execution_license(compat,frame())
        assert False
    except ValueError as e:
        assert 'authoritative Restoration Adequacy' in str(e)
