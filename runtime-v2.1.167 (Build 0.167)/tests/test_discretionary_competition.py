import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'examples'/'tiny_dual_corridor_world'))
from run_dual import build_runtime
from pvpp_runtime import WorldState, ProductivePowerState, CapacityCalendar

def test_unresolved_discretionary_conflict_is_visible_in_assessment():
    s=WorldState(0,{"knowledge":ProductivePowerState("knowledge",1)})
    cal=CapacityCalendar({p:{"teacher":3,"learner":3} for p in range(3)})
    a=build_runtime().assess(s,capacity_calendar=cal)
    assert a.recovery_adequacy.jointly_feasible is True
    assert a.discretionary_selection.status == "competing_maximal_sets_unresolved"
    assert a.selected_policy.required_action_ids == ("teach_A1","teach_B1")
    assert a.selected_policy.supplemental_action_ids == ()
    assert any("intentionally unused" in n for n in a.selected_policy.notes)
