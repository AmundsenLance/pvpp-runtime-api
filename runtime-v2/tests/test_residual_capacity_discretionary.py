import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'examples'/'tiny_dual_corridor_world'))
from run_dual import build_runtime
from pvpp_runtime import WorldState, ProductivePowerState, CapacityCalendar

def state(): return WorldState(0,{"knowledge":ProductivePowerState("knowledge",1)})
def cal(capacity): return CapacityCalendar({p:{"teacher":capacity,"learner":capacity} for p in range(3)})

def test_optional_work_cannot_displace_mandatory_recovery_when_no_residual_capacity():
    a=build_runtime().assess(state(),capacity_calendar=cal(2))
    assert a.selected_policy.required_action_ids == ("teach_A1","teach_B1")
    assert a.selected_policy.supplemental_action_ids == ()
    assert a.selected_policy.action_ids == ("teach_A1","teach_B1")
    assert a.selected_policy.residual_capacity["teacher"] == 0
    assert a.discretionary_selection.status == "no_eligible_discretionary_actions"

def test_competing_optional_actions_leave_residual_choice_unresolved_instead_of_using_name_tiebreak():
    a=build_runtime().assess(state(),capacity_calendar=cal(3))
    ds=a.discretionary_selection
    assert set(ds.eligible_action_ids) == {"document_knowledge","catalog_archive"}
    assert set(ds.maximal_feasible_sets) == {("catalog_archive",),("document_knowledge",)}
    assert ds.status == "competing_maximal_sets_unresolved"
    assert ds.selected_action_ids == ()
    assert a.selected_policy.supplemental_action_ids == ()
    assert a.selected_policy.residual_capacity["teacher"] == 1

def test_all_optional_work_is_added_when_all_candidates_fit_residual_capacity():
    a=build_runtime().assess(state(),capacity_calendar=cal(4))
    ds=a.discretionary_selection
    assert ds.status == "all_eligible_fit"
    assert ds.selected_action_ids == ("catalog_archive","document_knowledge")
    assert a.selected_policy.supplemental_action_ids == ("catalog_archive","document_knowledge")
    assert a.selected_policy.residual_capacity["teacher"] == 0
    assert a.selected_policy.residual_capacity["learner"] == 2

def test_optional_actions_are_evaluated_but_cannot_replace_recovery():
    a=build_runtime().assess(state(),capacity_calendar=cal(2))
    for aid in ("document_knowledge","catalog_archive"):
        ev=next(e for e in a.action_evaluations if e.action_id==aid)
        assert ev.feasible and ev.adequate
        assert aid not in a.selected_policy.action_ids
