"""B.3 Execution lineage: license to transition provenance, observation route and native route."""

from pvpp_runtime import (
    ExecutionObservation,
    ExecutionBindingRegistry,
    ExecutionBindingIdentity,
    ExecutionContext,
    RecoveryActionConfirmation,
)
from b2_cycle import run_cycle, make_request, make_actual


def observation_route():
    rt, integrated = run_cycle()
    actual, frame = make_actual(), make_request().domain_frame
    license = rt.build_execution_license_from_cycle(integrated.decision, frame)  # 11.2
    step = rt.instantiate_execution(
        "episode-1", license, entry_sufficient=True, max_steps=2  # host asserts sufficiency
    )  # 11.3
    # The host performs the action by its own means, then reports what happened (11.4).
    step = rt.advance_execution(step.episode, ExecutionObservation("obs-1", completed=True))
    assert step.terminal and step.status == "completed"  # treat the first terminal result as final
    handoff = rt.build_layer1_transition_handoff(step)  # 11.10
    transition = rt.apply_layer1_transition(actual, handoff)  # validated inside
    validation = rt.validate_layer1_transition_result(actual, handoff, transition)
    provenance = rt.build_execution_transition_provenance(
        actual, handoff, transition, validation
    )  # 11.11
    bookkeeping = rt.record_recovery_bookkeeping_from_transition(  # once per transition
        actual, step, transition, (RecoveryActionConfirmation("recharge", "battery_recovery"),)
    )
    return rt, transition, provenance, bookkeeping


def native_route():
    rt, integrated = run_cycle()  # a separate decision: execute each selection at most once
    actual, frame = make_actual(), make_request().domain_frame
    license = rt.build_execution_license_from_cycle(integrated.decision, frame)
    episode = rt.instantiate_execution(
        "episode-n1", license, entry_sufficient=True, max_steps=1
    ).episode
    bindings = ExecutionBindingRegistry(tuple(rt.registry.actions))  # 11.5
    action = license.action_ids[0]
    bindings.register(
        ExecutionBindingIdentity("recharge-v1", action, "1.0", ("appendix-b",)),
        lambda context: "charged",
    )  # the callable receives the ExecutionContext
    auth = rt.issue_native_execution_authorization(
        episode, action, bindings, decision_cycle_id="cycle-1"
    )  # 11.6
    result = rt.invoke_authorized_native(auth, bindings)  # 11.7; consumes auth
    # invoke_authorized_native does not return the context;
    # rebuild it from the result and the authorization (11.8).
    ctx = ExecutionContext(
        result.execution_id,
        auth.action_id,
        auth.binding_id,
        auth.decision_cycle_id,
        auth.attempt,
        configuration_id=auth.configuration_id,
    )
    step = rt.advance_execution(episode, bindings.epsilon_observation(ctx, result))
    handoff = rt.build_layer1_transition_handoff(step)
    transition = rt.apply_layer1_transition(actual, handoff)
    return rt, auth, result, step, transition


if __name__ == "__main__":
    _, t, p, b = observation_route()
    print(
        "observation:",
        t.next_state.state_id,
        t.next_state.pp,
        p.next_state_id,
        b.started_corridor_ids,
    )
    rt, a, r, s, t2 = native_route()
    print(
        "native:",
        r.status,
        rt.native_execution_authorization_status(a.authorization_id),
        s.status,
        t2.next_state.pp,
    )
