import pytest
from pvpp_runtime import ExecutionBindingIdentity, ExecutionBindingRegistry


def registry(target=lambda ctx: "ok"):
    r=ExecutionBindingRegistry({"a"})
    r.register(ExecutionBindingIdentity("b","a","1"),target)
    return r


def context(r):
    return r.create_context(action_id="a",decision_cycle_id="cycle",correlation_id="corr",configuration_id="cfg")


def test_success_telemetry_preserves_execution_identity_and_completion():
    r=registry(); c=context(r); result=r._invoke_authorized_context(c); t=r.telemetry(c,result,telemetry_id="t1")
    assert (t.telemetry_id,t.execution_id,t.status,t.completed)==("t1",c.execution_id,"succeeded",True)
    assert t.correlation_id=="corr" and t.configuration_id=="cfg"


def test_indeterminate_telemetry_preserves_possible_external_effect():
    def f(ctx): raise TimeoutError("lost")
    r=registry(f); c=context(r); t=r.telemetry(c,r._invoke_authorized_context(c))
    assert t.status=="indeterminate" and t.external_effect_possible is True


def test_telemetry_rejects_wrong_context_identity():
    r=registry(); c1=context(r); c2=context(r); result=r._invoke_authorized_context(c1)
    with pytest.raises(ValueError): r.telemetry(c2,result)

@pytest.mark.parametrize("state",["paused","aborted","reauthorization_required"])
def test_control_gate_blocks_invocation_before_callable(state):
    calls=[]
    r=registry(lambda ctx: calls.append(ctx.execution_id)); c=context(r)
    r.set_control_state(c.execution_id,state,reason="test")
    with pytest.raises(RuntimeError): r._invoke_authorized_context(c)
    assert calls==[]


def test_ready_control_allows_invocation():
    r=registry(); c=context(r); r.set_control_state(c.execution_id,"ready")
    assert r._invoke_authorized_context(c).status=="succeeded"


def test_control_state_does_not_claim_async_cancellation():
    r=registry(); c=context(r); control=r.set_control_state(c.execution_id,"paused")
    assert any("no asynchronous cancellation" in n for n in control.notes)


def test_unknown_control_state_rejected():
    r=registry(); c=context(r)
    with pytest.raises(ValueError): r.set_control_state(c.execution_id,"cancelled")
