"""Banked expectations for the Appendix B skeletons.

Run: PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
"""

import pytest
from b6_harness import verify_runtime_identity
from b2_cycle import run_cycle
from b3_lineage import observation_route, native_route
from b5_reentry import reenter_sigma


def test_runtime_is_frozen_v0141():
    assert verify_runtime_identity() == []


def test_one_cycle_selects_recovery_without_executing():
    _, out = run_cycle()
    assert out.status == "integrated_cycle_selected_not_executed"
    assert out.decision.stopped_at == "Sigma"
    assert out.decision.selection.selected_policy_id == "graph:restore_battery"


def test_observation_route_reaches_a_validated_transition():
    rt, transition, provenance, bookkeeping = observation_route()
    assert transition.next_state.pp["battery_units"] == 8.0
    assert rt.validate_execution_transition_provenance(provenance, transition.next_state).valid
    assert bookkeeping.started_corridor_ids == ("battery_recovery",)


def test_native_route_consumes_authorization_once():
    rt, auth, result, step, transition = native_route()
    assert result.status == "succeeded" and step.status == "completed"
    assert rt.native_execution_authorization_status(auth.authorization_id) == "consumed"


def test_native_replay_is_refused():
    rt, auth, *_ = native_route()
    # A consumed authorization is refused before any binding lookup.
    with pytest.raises(RuntimeError, match="consumed"):
        rt.invoke_authorized_native(auth, None)


def test_sigma_reentry_recomputes_only_sigma():
    original, out = reenter_sigma()
    assert out.valid and out.status == "reentry_pass_completed"
    assert out.recomputed_stage_ids == ("Sigma",)
    assert out.decision.selection.selected_policy_id == original.selection.selected_policy_id
