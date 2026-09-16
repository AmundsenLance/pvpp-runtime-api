import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'examples'/'tiny_crossing_policy_world'))

from pvpp_runtime import CandidatePolicySet, CandidatePolicySpace
from run_crossing_choice import build_runtime, state


def candidate(pid, action, class_id):
    return CandidatePolicySet(pid,(action,),(),(action,),{},(class_id,))


def test_pi_completeness_passes_when_all_declared_material_classes_are_represented():
    rt=build_runtime()
    space=CandidatePolicySpace(
        (candidate('food_policy','favor_food','local_adjustment'),
         candidate('material_policy','favor_material','structural_shift')),
        ('local_adjustment','structural_shift'),
    )
    a=rt.evaluate_policy_space(state(),space)
    assert a.pi_completeness.complete is True
    assert a.pi_completeness.status == 'pi_completeness_passed'
    assert a.pi_completeness.missing_class_ids == ()
    # Completeness does not settle the downstream crossing.
    assert a.status == 'crossing_governing_consequences_unresolved'
    assert a.selected_policy_id is None


def test_pi_completeness_failure_blocks_all_downstream_policy_evaluation():
    rt=build_runtime()
    space=CandidatePolicySpace(
        (candidate('food_policy','favor_food','local_adjustment'),),
        ('local_adjustment','exit_transfer'),
    )
    a=rt.evaluate_policy_space(state(),space)
    assert a.status == 'pi_completeness_failed_missing_material_policy_classes'
    assert a.pi_completeness.complete is False
    assert a.pi_completeness.missing_class_ids == ('exit_transfer',)
    assert a.evaluations == ()
    assert a.structural_assessment is None
    assert a.undominated_policy_ids == ()
    assert a.selected_policy_id is None


def test_pi_completeness_is_coverage_not_preference():
    rt=build_runtime()
    food=candidate('food_policy','favor_food','substitute_A')
    material=candidate('material_policy','favor_material','substitute_B')
    space=CandidatePolicySpace((food,material),('substitute_A','substitute_B'))
    a=rt.evaluate_policy_space(state(),space)
    assert a.pi_completeness.complete is True
    assert a.status == 'crossing_governing_consequences_unresolved'
    assert a.selected_policy_id is None


def test_policy_and_required_class_order_do_not_change_completeness_or_selection():
    rt1=build_runtime(); rt2=build_runtime()
    food=candidate('food_policy','favor_food','local_adjustment')
    material=candidate('material_policy','favor_material','structural_shift')
    a=rt1.evaluate_policy_space(state(),CandidatePolicySpace(
        (food,material),('local_adjustment','structural_shift')))
    b=rt2.evaluate_policy_space(state(),CandidatePolicySpace(
        (material,food),('structural_shift','local_adjustment')))
    assert a.pi_completeness.complete == b.pi_completeness.complete == True
    assert set(a.pi_completeness.represented_class_ids) == set(b.pi_completeness.represented_class_ids)
    assert a.status == b.status == 'crossing_governing_consequences_unresolved'
    assert a.selected_policy_id == b.selected_policy_id is None


def test_one_candidate_can_cover_multiple_material_policy_classes():
    rt=build_runtime()
    hybrid=CandidatePolicySet('hybrid',('favor_food',),(),('favor_food',),{},
                              ('local_adjustment','bridge_support'))
    c=rt.validate_pi_completeness(CandidatePolicySpace(
        (hybrid,),('bridge_support','local_adjustment')))
    assert c.complete is True
    assert c.missing_class_ids == ()


def test_legacy_evaluate_policy_sets_is_explicitly_not_completeness_validated():
    rt=build_runtime()
    a=rt.evaluate_policy_sets(state(),(
        CandidatePolicySet('food_policy',('favor_food',)),
        CandidatePolicySet('material_policy',('favor_material',)),
    ))
    assert a.pi_completeness.status == 'pi_completeness_basis_not_supplied'
    assert a.pi_completeness.complete is False
    # Compatibility behavior still evaluates rather than pretending validation occurred.
    assert len(a.evaluations) == 2
