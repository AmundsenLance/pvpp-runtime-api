"""Step 5: carry out the decision and apply the state change. The host owns the change."""

from step2_world import FULL, DRAIN
from step2_world import actual_state
from step4_decide import decide, make_runtime, request
from pvpp_runtime import (
    ActualPersistentStateEnvelope, Layer1TransitionResult, ExecutionObservation,
)


class Layer1Service:
    """The host's only way to change the sensor's recorded state."""

    def transition(self, current, handoff):
        pp = dict(current.pp)
        if "recharge" in handoff.licensed_action_ids:
            pp["battery_units"] = FULL
        else:
            pp["battery_units"] = float(pp["battery_units"]) - DRAIN
        nxt = ActualPersistentStateEnvelope(
            current.actor_id, current.state_id + ":next", current.time + 1.0,
            pp, current.spv, current.avs, dict(current.context))
        return Layer1TransitionResult(
            handoff.episode_id, handoff.selected_policy_id, current.state_id, nxt, True,
            {"battery_nonnegative": pp["battery_units"] >= 0.0})


def act(battery):
    rt, out = decide(battery, make_runtime(Layer1Service()))
    actual = actual_state(battery)
    # 1. A license: the runtime's permission to carry out this one decision.
    license = rt.build_execution_license_from_cycle(out.decision, request().domain_frame)
    # 2. An execution episode. The host asserts the action can start now.
    step = rt.instantiate_execution("episode-1", license, entry_sufficient=True, max_steps=1)
    # 3. The host performs the action by its own means, then reports what happened.
    step = rt.advance_execution(step.episode, ExecutionObservation("obs-1", completed=True))
    # 4. The host applies the state change through its Layer-1 service; the runtime checks it.
    handoff = rt.build_layer1_transition_handoff(step)
    result = rt.apply_layer1_transition(actual, handoff)
    check = rt.validate_layer1_transition_result(actual, handoff, result)
    provenance = rt.build_execution_transition_provenance(actual, handoff, result, check)
    return license, step, result, provenance


if __name__ == "__main__":
    license, step, result, provenance = act(5.0)
    print("licensed actions:", license.action_ids)
    print("execution status:", step.status)
    print("battery:          5.0 ->", result.next_state.pp["battery_units"])
    print("new state id:    ", provenance.next_state_id)
