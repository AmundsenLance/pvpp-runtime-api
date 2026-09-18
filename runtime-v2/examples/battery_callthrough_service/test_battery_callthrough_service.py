import pytest
from battery_callthrough_service import (
    make_actual, prepare_callthrough, run_once, run_denied_before_call, run_failure,
)


def test_success_is_canonical_authority_bound_callthrough():
    out = run_once(make_actual(3.0))
    assert out["integrated"].decision.selection.selected_policy_id == "graph:restore_battery"
    assert out["license"].action_ids == ("recharge",)
    assert out["native_result"].status == "succeeded"
    assert len(out["charger"].calls) == 1
    assert out["charger"].calls[0]["action_id"] == "recharge"
    assert out["runtime"].native_execution_authorization_status(out["authorization"].authorization_id) == "consumed"
    assert out["transition"].next_state.pp["battery_units"] == 8.0
    assert out["validation"].valid
    # The caller's prior actual state remains immutable; Layer 1 produced a new envelope.
    assert out["actual"].pp["battery_units"] == 3.0


def test_registration_alone_cannot_bypass_native_authorization():
    (_, _, _, _, _, _, charger, bindings, _) = prepare_callthrough()
    context = bindings.create_context(action_id="recharge", decision_cycle_id="fake")
    with pytest.raises(RuntimeError, match="native execution authorization"):
        bindings.invoke(context, target_units=8.0)
    assert charger.calls == []


def test_invalidated_authorization_never_enters_callable():
    out = run_denied_before_call()
    assert out["charger"].calls == []
    assert out["runtime"].native_execution_authorization_status(out["authorization"].authorization_id) == "invalidated"
    assert "invalidated" in str(out["error"])


def test_authorization_is_single_use_and_replay_fails_closed():
    (_, rt, _, _, _, _, charger, bindings, authorization) = prepare_callthrough()
    result = rt.invoke_authorized_native(authorization, bindings, target_units=8.0)
    assert result.status == "succeeded" and len(charger.calls) == 1
    with pytest.raises(RuntimeError, match="consumed"):
        rt.invoke_authorized_native(authorization, bindings, target_units=8.0)
    assert len(charger.calls) == 1


def test_unclassified_callable_failure_propagates_as_indeterminate():
    out = run_failure("indeterminate")
    result = out["native_result"]
    assert len(out["charger"].calls) == 1
    assert result.status == "indeterminate"
    assert result.error_type == "RuntimeError"
    assert result.error_message == "charger connection lost after command dispatch"
    assert result.external_effect_possible is True
    assert out["runtime"].native_execution_authorization_status(out["authorization"].authorization_id) == "consumed"


def test_clean_failure_propagates_without_claiming_external_effect():
    out = run_failure("clean")
    result = out["native_result"]
    assert len(out["charger"].calls) == 1
    assert result.status == "failed_cleanly"
    assert result.error_type == "CleanExecutionFailure"
    assert result.error_message == "charger rejected command before external effect"
    assert result.external_effect_possible is False
