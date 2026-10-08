import pytest
from pvpp_runtime import ExecutionBindingIdentity, ExecutionBindingRegistry


def reg():
    r=ExecutionBindingRegistry({"a"})
    r.register(ExecutionBindingIdentity("b","a","1"),lambda ctx: "ok")
    return r

def ctx(r):
    return r.create_context(action_id="a",decision_cycle_id="cycle",correlation_id="corr",configuration_id="cfg")

def test_control_change_is_bookkept_with_prior_and_new_state():
    r=reg(); c=ctx(r)
    r.set_control_state(c.execution_id,"paused",reason="sensor uncertainty",requested_by="monitor",evidence_ids=("e1",))
    e=r.control_history(c.execution_id)[0]
    assert (e.prior_state,e.new_state,e.reason,e.evidence_ids)==("ready","paused","sensor uncertainty",("e1",))

def test_control_history_is_ordered_and_immutable_snapshot():
    r=reg(); c=ctx(r)
    r.set_control_state(c.execution_id,"paused",reason="r1")
    r.set_control_state(c.execution_id,"reauthorization_required",reason="r2")
    h=r.control_history(c.execution_id)
    assert [x.new_state for x in h]==["paused","reauthorization_required"] and isinstance(h,tuple)

def test_nonready_without_reason_is_bookkept_as_unspecified_for_compatibility():
    r=reg(); c=ctx(r)
    r.set_control_state(c.execution_id,"paused")
    assert r.control_history(c.execution_id)[0].reason=="unspecified"

def test_duplicate_control_evidence_rejected():
    r=reg(); c=ctx(r)
    with pytest.raises(ValueError): r.set_control_state(c.execution_id,"aborted",reason="stop",evidence_ids=("e","e"))

def test_reauthorization_handoff_preserves_execution_and_configuration_identity():
    r=reg(); c=ctx(r)
    r.set_control_state(c.execution_id,"reauthorization_required",reason="authority stale",requested_by="runtime")
    h=r.build_reauthorization_handoff(c,evidence_ids=("obs1",))
    assert (h.execution_id,h.action_id,h.binding_id,h.decision_cycle_id)==(c.execution_id,"a","b","cycle")
    assert h.correlation_id=="corr" and h.configuration_id=="cfg" and h.return_to_governance is True

def test_reauthorization_handoff_does_not_claim_reentry_stage():
    r=reg(); c=ctx(r)
    r.set_control_state(c.execution_id,"reauthorization_required",reason="new evidence")
    h=r.build_reauthorization_handoff(c)
    assert not hasattr(h,"reentry_stage")
    assert any("earliest-invalidated-stage" in n for n in h.notes)

def test_handoff_requires_reauthorization_control_state():
    r=reg(); c=ctx(r)
    with pytest.raises(ValueError): r.build_reauthorization_handoff(c,reason="x")

def test_duplicate_reauthorization_evidence_rejected():
    r=reg(); c=ctx(r)
    r.set_control_state(c.execution_id,"reauthorization_required",reason="x")
    with pytest.raises(ValueError): r.build_reauthorization_handoff(c,evidence_ids=("e","e"))
