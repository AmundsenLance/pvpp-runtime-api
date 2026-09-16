import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'examples'/'tiny_dual_corridor_world'))
from run_dual import build_runtime, calendar
from pvpp_runtime import WorldState, ProductivePowerState


def state():
    return WorldState(0, {"knowledge":ProductivePowerState("knowledge", 1)})


def test_assess_reports_joint_infeasibility_and_withholds_selection():
    rt=build_runtime()
    a=rt.assess(state(), capacity_calendar=calendar(5))
    assert a.recovery_adequacy.status == "active_jointly_infeasible"
    assert a.recovery_adequacy.jointly_feasible is False
    assert a.recovery_adequacy.infeasible_corridor_sets == (("corridor_A","corridor_B"),)
    assert a.selected_action is None
    assert set(a.recovery_adequacy.bottleneck_resources[("corridor_A","corridor_B")]) == {"teacher","learner"}
    assert any("selection withheld" in n.lower() for n in a.notes)


def test_assess_reports_joint_feasibility_and_slack():
    rt=build_runtime()
    a=rt.assess(state(), capacity_calendar=calendar(6))
    assert a.recovery_adequacy.status == "active_jointly_feasible"
    assert a.recovery_adequacy.jointly_feasible is True
    assert len(a.recovery_adequacy.schedule) == 6
    assert set(a.recovery_adequacy.deadline_slack) == {"corridor_A","corridor_B"}
    assert min(a.recovery_adequacy.deadline_slack.values()) >= 0
    first_period=min(s.period_offset for s in a.recovery_adequacy.schedule)
    scheduled_now={s.action_id for s in a.recovery_adequacy.schedule if s.period_offset==first_period}
    assert a.selected_action in scheduled_now
    assert a.selected_action in {"teach_A1","teach_B1"}


def test_active_corridors_without_calendar_do_not_claim_joint_adequacy():
    rt=build_runtime()
    a=rt.assess(state())
    assert a.recovery_adequacy.status == "capacity_not_supplied"
    assert a.recovery_adequacy.jointly_feasible is None
