"""Step 3: say what each option would do. The projection service projects; it never chooses."""

from step1_registry import DOMAIN, POWER, FUNCTION
from step2_world import DRAIN, FULL, World, actual_state
from pvpp_runtime import (
    WorldState, ProductivePowerState, PolicyProjectionRecord, RecoveryCorridorProjection,
    ProjectionRequest,
)


class Projection:
    """A PolicyProjectionService: one projection record per candidate policy."""

    def project(self, req):
        start = req.represented_state.powers[POWER].value
        horizon = req.projection_horizon
        if "recharge" in req.action_ids:
            end, fails_at = FULL, None                 # recharged: safe past the horizon
        else:
            end = start - DRAIN * horizon              # sampling all the way to the horizon
            t = (start - 2.0) / DRAIN                  # periods until the 2.0 threshold
            fails_at = t if t < horizon else None
        safe = fails_at is None
        corridor = RecoveryCorridorProjection(
            DOMAIN, FUNCTION,
            pre_recovery_viability_preserved=safe,
            recovery_capable_region_reached=safe,      # recharging reaches it; a healthy
            joint_sustainment_supported=True,          # sensor never leaves it
            recovery_entry_time=(1.0 if "recharge" in req.action_ids else 0.0) if safe else None,
            projected_extinction_time=fails_at)
        return PolicyProjectionRecord(
            req.policy_id, False,
            WorldState(req.represented_state.time + 1,
                       {POWER: ProductivePowerState(POWER, max(end, 0.0))},
                       dict(req.represented_state.metadata)),
            {DOMAIN: fails_at if fails_at is not None else horizon},
            (corridor,),
            # Echo the request so the runtime can check that this record answers it.
            projection_horizon=horizon,
            right_censored_domain_ids=(DOMAIN,) if safe else (),   # "still fine at the horizon"
            state_id=req.state_id, state_time=req.represented_state.time,
            candidate_mode=req.candidate_mode, model_version="battery-q1",
            projection_input_trace=dict(req.projection_input_trace))


if __name__ == "__main__":
    for battery in (9.0, 5.0):
        seen = World().perceived_decision_state_from_actual(actual_state(battery))
        for policy, action in (("graph:continue_sampling", "sample"),
                               ("graph:restore_battery", "recharge")):
            q = Projection().project(ProjectionRequest(
                seen.represented_state, policy, (action,), "ordinary_adequacy", 10.0,
                state_id=seen.state_id))
            h = q.projected_horizons[DOMAIN]
            note = "safe through the horizon" if q.right_censored_domain_ids else "fails at"
            print(f"battery {battery}: {policy:24} {note} {h}")
