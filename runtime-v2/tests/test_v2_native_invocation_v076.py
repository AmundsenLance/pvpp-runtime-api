from dataclasses import replace

import pytest

from pvpp_runtime import (
    CleanExecutionFailure,
    CompletedInvalidExecution,
    ExecutionBindingIdentity,
    ExecutionBindingRegistry,
    IndeterminateExecutionFailure,
)


def prepared(target):
    r = ExecutionBindingRegistry(("steady", "repair"))
    r.register(ExecutionBindingIdentity("repair-native", "repair", "1.0", ("prov-native",)), target)
    c = r.create_context(action_id="repair", decision_cycle_id="cycle-76", correlation_id="corr-76")
    return r, c


def test_success_invokes_once_and_preserves_execution_identity():
    calls=[]
    def target(context, value):
        calls.append(context.execution_id)
        return value * 2
    r,c=prepared(target)
    result=r._invoke_authorized_context(c, 4)
    assert result.status == "succeeded" and result.return_value == 8
    assert result.execution_id == c.execution_id and calls == [c.execution_id]
    assert result.completed and result.external_effect_possible


def test_clean_failure_requires_explicit_binding_signal():
    def target(context): raise CleanExecutionFailure("rejected before effect")
    r,c=prepared(target); result=r._invoke_authorized_context(c)
    assert result.status == "failed_cleanly"
    assert result.external_effect_possible is False


def test_timeout_is_indeterminate_not_clean_failure():
    def target(context): raise TimeoutError("lost response")
    r,c=prepared(target); result=r._invoke_authorized_context(c)
    assert result.status == "indeterminate"
    assert result.external_effect_possible is True
    assert result.failure_stage == "transport"


def test_connection_loss_is_indeterminate():
    def target(context): raise ConnectionError("connection dropped")
    r,c=prepared(target); result=r._invoke_authorized_context(c)
    assert result.status == "indeterminate" and result.external_effect_possible


def test_binding_declared_indeterminate_is_preserved():
    def target(context): raise IndeterminateExecutionFailure("remote outcome unknown")
    r,c=prepared(target); result=r._invoke_authorized_context(c)
    assert result.status == "indeterminate" and result.failure_stage == "external_unknown"


def test_arbitrary_exception_defaults_conservatively_to_indeterminate():
    def target(context): raise RuntimeError("failed after unknown progress")
    r,c=prepared(target); result=r._invoke_authorized_context(c)
    assert result.status == "indeterminate" and result.external_effect_possible
    assert result.error_type == "RuntimeError"


def test_completed_invalid_is_distinct_from_technical_failure():
    def target(context): raise CompletedInvalidExecution("realized transition violates validation")
    r,c=prepared(target); result=r._invoke_authorized_context(c)
    assert result.status == "completed_invalid"
    assert result.completed and result.transition_valid is False


def test_context_binding_mismatch_fails_before_invocation():
    calls=[]
    r,c=prepared(lambda context: calls.append(context.execution_id))
    bad=replace(c, action_id="steady")
    with pytest.raises(ValueError): r._invoke_authorized_context(bad)
    assert calls == []


def test_unknown_binding_context_fails_before_invocation():
    r,c=prepared(lambda context: None)
    bad=replace(c, binding_id="missing")
    with pytest.raises(KeyError): r._invoke_authorized_context(bad)
