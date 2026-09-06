import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'examples'/'tiny_crossing_policy_world'))
from pvpp_runtime import *
from run_crossing_choice import build_runtime, state

def space():
    return CandidatePolicySpace((
      CandidatePolicySet('food_policy',('favor_food',),policy_class_ids=('local',)),
      CandidatePolicySet('material_policy',('favor_material',),policy_class_ids=('shift',)),
    ),('local','shift'))
def frame():
    return DomainFrame((DomainFrameTarget('F','F_function'),DomainFrameTarget('M','M_function')))

def test_constraints_are_explicit_in_strict_pipeline():
    a=build_runtime().evaluate_framed_policy_space(state(),space(),frame())
    assert a.constraints is not None
    assert a.constraints.status == 'constraints_passed_all_candidates'
    assert set(a.constraints.feasible_policy_ids)=={'food_policy','material_policy'}
    assert a.domain_framing.valid is True

def test_host_infeasibility_is_constraint_failure_not_adequacy_failure():
    rt=build_runtime()
    original=rt.world.project_policy
    def reject_material(st,ids):
        pr=original(st,ids)
        if 'favor_material' in ids:
            return ActionProjection(pr.action_id,pr.next_state,False,('host capacity constraint',))
        return pr
    rt.world.project_policy=reject_material
    a=rt.evaluate_framed_policy_space(state(),space(),frame())
    assert a.constraints.status == 'constraints_filtered_candidates'
    assert a.constraints.infeasible_policy_ids == ('material_policy',)
    ev={e.policy_id:e for e in a.evaluations}
    assert ev['material_policy'].feasible is False
    assert ev['material_policy'].adequate is False
    assert 'host capacity constraint' in ev['material_policy'].reasons

def test_no_feasible_candidates_blocks_domain_framing_and_adequacy():
    rt=build_runtime()
    original=rt.world.project_policy
    def reject(st,ids):
        pr=original(st,ids)
        return ActionProjection(pr.action_id,pr.next_state,False,('host rejects all',))
    rt.world.project_policy=reject
    a=rt.evaluate_framed_policy_space(state(),space(),frame())
    assert a.status == 'constraints_no_feasible_candidates'
    assert a.domain_framing is None
    assert a.evaluations == ()

def test_constraint_projection_is_not_repeated_during_downstream_evaluation():
    rt=build_runtime()
    original=rt.world.project_policy
    calls={'n':0}
    def counted(st,ids):
        calls['n']+=1
        return original(st,ids)
    rt.world.project_policy=counted
    rt.evaluate_framed_policy_space(state(),space(),frame())
    assert calls['n'] == 2
