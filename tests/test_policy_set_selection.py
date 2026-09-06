import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'examples'/'tiny_policy_set_world'))
from run_policy_choice import build_runtime, state, calendar


def test_policy_sets_are_first_class_and_governing_consequence_can_resolve_choice():
    a=build_runtime(equal=False).assess(state(),capacity_calendar=calendar())
    assert a.policy_selection is not None
    assert len(a.policy_selection.candidates)==2
    assert a.policy_selection.status == 'unique_governing_consequence_dominance'
    assert len(a.policy_selection.undominated_policy_ids)==1
    assert a.discretionary_selection.status == 'resolved_by_governing_consequences'
    assert a.selected_policy.required_action_ids == ('teach_A1','teach_B1')
    assert a.selected_policy.supplemental_action_ids == ('gather_large',)
    evals={tuple(e.action_ids):e for e in a.policy_selection.evaluations}
    assert evals[('teach_A1','teach_B1','gather_large')].projected_horizons['F'] > evals[('teach_A1','teach_B1','gather_small')].projected_horizons['F']


def test_equal_governing_consequences_remain_unresolved():
    a=build_runtime(equal=True).assess(state(),capacity_calendar=calendar())
    assert a.policy_selection.status == 'equivalent_governing_consequences_unresolved'
    assert len(a.policy_selection.undominated_policy_ids)==2
    assert a.discretionary_selection.status == 'competing_maximal_sets_unresolved'
    assert a.selected_policy.supplemental_action_ids == ()


def test_policy_selection_uses_host_policy_projection():
    a=build_runtime(equal=False).assess(state(),capacity_calendar=calendar())
    assert all('compatibility sequential projection' not in note for note in a.policy_selection.notes)
