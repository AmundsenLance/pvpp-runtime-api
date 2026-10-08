import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'examples'/'tiny_dual_corridor_world'))
from run_dual import build_runtime
from pvpp_runtime import WorldState, ProductivePowerState, CapacityCalendar


def state():
    return WorldState(0,{"knowledge":ProductivePowerState("knowledge",1)})


def parallel_calendar(periods=3, capacity=2):
    return CapacityCalendar({p:{"teacher":capacity,"learner":capacity} for p in range(periods)})


def test_selected_policy_can_contain_multiple_same_period_recovery_actions():
    rt=build_runtime()
    a=rt.assess(state(),capacity_calendar=parallel_calendar(3,2))
    assert a.recovery_adequacy.jointly_feasible is True
    assert a.selected_policy is not None
    assert a.selected_policy.recovery_constrained is True
    assert a.selected_policy.period_offset == 0
    assert a.selected_policy.action_ids == ("teach_A1","teach_B1")
    # selected_action is intentionally only a singleton compatibility surface.
    assert a.selected_action is None


def test_residual_capacity_is_reported_after_mandatory_recovery_schedule():
    rt=build_runtime()
    a=rt.assess(state(),capacity_calendar=parallel_calendar(3,3))
    residual=a.recovery_adequacy.residual_capacity
    assert residual[0]["teacher"] == 1
    assert residual[0]["learner"] == 1
    assert residual[1]["teacher"] == 1
    assert residual[2]["learner"] == 1


def test_singleton_decision_keeps_selected_action_and_policy():
    rt=build_runtime()
    cal=CapacityCalendar({p:{"teacher":1,"learner":1} for p in range(6)})
    a=rt.assess(state(),capacity_calendar=cal)
    assert a.selected_action in {"teach_A1","teach_B1"}
    assert a.selected_policy is not None
    assert a.selected_policy.action_ids == (a.selected_action,)
