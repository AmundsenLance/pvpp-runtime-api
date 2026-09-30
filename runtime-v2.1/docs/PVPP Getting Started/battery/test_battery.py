"""Tests for the tutorial. Run: PVPP_RUNTIME_PATH=<runtime-v2.1> python3 -m pytest -q"""

from step1_registry import DOMAIN, build_registry
from step2_world import World, actual_state
from step3_projection import Projection
from step4_decide import decide, request
from step5_act import act
from pvpp_runtime import PVPPRuntime, ProjectionRequest


def test_registry_has_the_required_baseline_action():
    assert "steady" in build_registry().actions


def test_projection_reports_a_failure_without_censoring():
    seen = World().perceived_decision_state_from_actual(actual_state(5.0))
    q = Projection().project(ProjectionRequest(
        seen.represented_state, "graph:continue_sampling", ("sample",),
        "ordinary_adequacy", 10.0, state_id=seen.state_id))
    assert q.projected_horizons[DOMAIN] == 6.0 and q.right_censored_domain_ids == ()


def test_healthy_sensor_keeps_sampling():
    _, out = decide(9.0)
    assert out.status == "integrated_cycle_selected_not_executed"
    assert out.decision.horizon_assessment.domain_results[0].horizon == 14.0   # (9.0 - 2.0) / 0.5
    assert out.decision.regime_assessment.regime == "Mission"
    assert out.decision.selection.selected_policy_id == "graph:continue_sampling"


def test_low_battery_recharges_because_sampling_is_inadequate():
    _, out = decide(5.0)
    assert out.decision.regime_assessment.regime == "Stabilization"   # 6 periods left, within 8
    assert out.decision.adequacy.adequate_policy_ids == ("graph:restore_battery",)
    assert out.decision.selection.selected_policy_id == "graph:restore_battery"


def test_order_only_breaks_ties():
    reversed_order = build_registry(order=("graph:restore_battery", "graph:continue_sampling"))
    rt = PVPPRuntime(reversed_order, World(), projection_service=Projection())
    healthy = rt.evaluate_integrated_canonical_cycle(actual_state(9.0), request())
    low = rt.evaluate_integrated_canonical_cycle(actual_state(5.0), request())
    assert healthy.decision.selection.selected_policy_id == "graph:restore_battery"   # tie
    assert low.decision.selection.selected_policy_id == "graph:restore_battery"       # not a tie


def test_acting_recharges_the_battery_with_valid_provenance():
    license, step, result, provenance = act(5.0)
    assert license.action_ids == ("recharge",) and step.status == "completed"
    assert result.next_state.pp["battery_units"] == 8.0
    assert provenance.next_state_id == result.next_state.state_id
