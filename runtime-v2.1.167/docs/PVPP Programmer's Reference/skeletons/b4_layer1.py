"""B.4 Layer-1 transition service: the host's only mutation boundary."""

from pvpp_runtime import ActualPersistentStateEnvelope, Layer1TransitionResult


class Layer1Service:
    def transition(self, current, handoff):
        pp = dict(current.pp)
        acts = set(handoff.licensed_action_ids)
        if "recharge" in acts:
            pp["battery_units"] = 8.0
        elif "sample" in acts:
            pp["battery_units"] = max(0.0, float(pp["battery_units"]) - 1.0)
        nxt = ActualPersistentStateEnvelope(
            current.actor_id,
            current.state_id + ":next",
            current.time + 1.0,
            pp,
            current.spv,
            current.avs,
            dict(current.context),
        )
        # Echo the handoff's identities; report host invariants; give the new state a new id.
        return Layer1TransitionResult(
            handoff.episode_id,
            handoff.selected_policy_id,
            current.state_id,
            nxt,
            True,
            {"battery_nonnegative": pp["battery_units"] >= 0.0},
        )
