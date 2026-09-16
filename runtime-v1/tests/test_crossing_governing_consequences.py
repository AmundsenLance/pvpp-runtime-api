import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'examples'/'tiny_crossing_policy_world'))
from run_crossing_choice import build_runtime, state, calendar


def test_crossing_governing_consequences_remain_unresolved():
    a=build_runtime().assess(state(),capacity_calendar=calendar())
    assert set(a.governing_domains)=={'F','M'}
    assert a.policy_selection is not None
    assert a.policy_selection.status == 'crossing_governing_consequences_unresolved'
    assert set(a.policy_selection.conflicting_domains)=={'F','M'}
    assert len(a.policy_selection.undominated_policy_ids)==2
    assert a.discretionary_selection.status == 'competing_maximal_sets_unresolved'
    assert a.selected_policy.required_action_ids == ('teach_A1','teach_B1')
    assert a.selected_policy.supplemental_action_ids == ()


def test_crossing_vectors_are_opposed_without_scalarization():
    a=build_runtime().assess(state(),capacity_calendar=calendar())
    evals={tuple(e.action_ids):e for e in a.policy_selection.evaluations}
    food=evals[('teach_A1','teach_B1','favor_food')].projected_horizons
    material=evals[('teach_A1','teach_B1','favor_material')].projected_horizons
    assert food['F'] > material['F']
    assert food['M'] < material['M']
    assert a.policy_selection.selected_policy_id is None
