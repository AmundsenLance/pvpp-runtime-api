from pvpp_runtime import (
    ActionDefinition, ActualPersistentStateEnvelope, DomainDefinition,
    ExecutionBindingIdentity, ExecutionBindingRegistry, Layer1TransitionResult,
    PVPPRuntime, PVPPRegistry,
)


def registry_and_runtime(service=None):
    reg = PVPPRegistry()
    reg.register_domain(DomainDefinition("d", "D", 0.0))
    reg.register_action(ActionDefinition("steady", "steady", ("d",)))
    reg.register_action(ActionDefinition("act", "act", ("d",)))
    class World:
        pass
    return reg, PVPPRuntime(reg, World(), layer1_transition_service=service)


def binding_registry():
    br = ExecutionBindingRegistry({"steady", "act"})
    br.register(ExecutionBindingIdentity("b-act", "act", "1"), lambda ctx: {"ok": True})
    return br


def test_success_builds_handoff_without_transition_side_effect():
    br = binding_registry(); ctx = br.create_context(action_id="act", decision_cycle_id="c1", execution_id="e1")
    result = br._invoke_authorized_context(ctx)
    h = br.build_layer1_handoff(ctx, result, selected_policy_id="p1")
    assert h.episode_id == "e1" and h.execution_status == "completed"
    assert h.return_upstream is False and h.licensed_action_ids == ("act",)
    assert h.execution_information[0]["execution_id"] == "e1"


def test_indeterminate_requests_upstream_return():
    br = ExecutionBindingRegistry({"act"})
    def target(ctx): raise TimeoutError("lost")
    br.register(ExecutionBindingIdentity("b", "act", "1"), target)
    ctx = br.create_context(action_id="act", decision_cycle_id="c", execution_id="e")
    h = br.build_layer1_handoff(ctx, br._invoke_authorized_context(ctx), selected_policy_id="p")
    assert h.execution_status == "partial_realization" and h.return_upstream is True


def test_clean_failure_is_not_transitioned():
    from pvpp_runtime import CleanExecutionFailure
    br = ExecutionBindingRegistry({"act"})
    def target(ctx): raise CleanExecutionFailure("no effect")
    br.register(ExecutionBindingIdentity("b", "act", "1"), target)
    ctx = br.create_context(action_id="act", decision_cycle_id="c")
    import pytest
    with pytest.raises(ValueError, match="no material external effect"):
        br.build_layer1_handoff(ctx, br._invoke_authorized_context(ctx), selected_policy_id="p")


def test_identity_mismatch_fails_before_handoff():
    from dataclasses import replace
    br = binding_registry(); ctx = br.create_context(action_id="act", decision_cycle_id="c")
    r = replace(br._invoke_authorized_context(ctx), execution_id="other")
    import pytest
    with pytest.raises(ValueError, match="execution_id"):
        br.build_layer1_handoff(ctx, r, selected_policy_id="p")


def test_existing_layer1_service_receives_native_handoff_and_runtime_validates():
    class Service:
        def __init__(self): self.calls = 0
        def transition(self, current_state, handoff):
            self.calls += 1
            nxt = ActualPersistentStateEnvelope(current_state.actor_id, "s2", current_state.time + 1, current_state.pp, current_state.spv, current_state.avs, current_state.context)
            return Layer1TransitionResult(handoff.episode_id, handoff.selected_policy_id, current_state.state_id, nxt, True, {"ok": True})
    svc = Service(); reg, rt = registry_and_runtime(svc); br = binding_registry()
    ctx = br.create_context(action_id="act", decision_cycle_id="c", execution_id="e")
    handoff = br.build_layer1_handoff(ctx, br._invoke_authorized_context(ctx), selected_policy_id="p")
    prior = ActualPersistentStateEnvelope("a", "s1", 1.0, {}, {}, {}, {})
    result = rt.apply_layer1_transition(prior, handoff)
    assert svc.calls == 1 and result.next_state.state_id == "s2"
    assessment = rt.validate_layer1_transition_result(prior, handoff, result)
    assert assessment.valid


def test_invalid_host_transition_still_fails_closed():
    class BadService:
        def transition(self, current_state, handoff):
            return Layer1TransitionResult(handoff.episode_id, handoff.selected_policy_id, current_state.state_id, current_state, True, {})
    reg, rt = registry_and_runtime(BadService()); br = binding_registry()
    ctx = br.create_context(action_id="act", decision_cycle_id="c")
    handoff = br.build_layer1_handoff(ctx, br._invoke_authorized_context(ctx), selected_policy_id="p")
    prior = ActualPersistentStateEnvelope("a", "s1", 1.0, {}, {}, {}, {})
    import pytest
    with pytest.raises(ValueError, match="invalid Layer 1 transition result"):
        rt.apply_layer1_transition(prior, handoff)
