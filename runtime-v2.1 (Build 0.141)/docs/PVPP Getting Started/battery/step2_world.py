"""Step 2: tell the runtime what the world looks like. The world adapter states facts."""

from step1_registry import DOMAIN, POWER
from pvpp_runtime import (
    WorldState, ProductivePowerState, PerceivedDecisionState, ActualPersistentStateEnvelope,
    ActionProjection, PressureFactors, PolicyConstraintProfile, ConstraintObservation,
)

DRAIN = 0.5          # energy used per period, idle or sampling
FULL = 8.0           # battery level after a recharge


def actual_state(battery):
    """The host's record of the real sensor: its actual persistent state."""
    return ActualPersistentStateEnvelope(
        "sensor-A", f"battery-{battery}", 0.0,
        {"battery_units": battery}, {"stored_charge": battery},
        {"service_available": True}, {})


class World:
    """The world adapter. It answers the runtime's questions; it never decides."""

    # Perception: what the sensor believes about itself, formed from its actual state.
    def perceived_decision_state_from_actual(self, actual):
        b = float(actual.pp["battery_units"])
        seen = WorldState(actual.time, {POWER: ProductivePowerState(POWER, b)},
                          {"state_id": actual.state_id})
        return PerceivedDecisionState(actual.actor_id, actual.state_id, actual.time,
                                      seen, ppp={POWER: b})

    def perceive(self, state):          # already perceived: return it unchanged
        return state

    def domain_value(self, state, domain_id):
        return state.powers[POWER].value

    # One step of an action, used for the baseline ("steady") and horizons.
    def project(self, state, action):
        b = self.domain_value(state, DOMAIN)
        b = FULL if action.id == "recharge" else b - DRAIN
        return ActionProjection(action.id, WorldState(
            state.time + 1, {POWER: ProductivePowerState(POWER, b)}, dict(state.metadata)), True)

    # Pressure: how far above failure the domain is, and how fast it is falling.
    def pressure_factors(self, state, domain_id, baseline_drift):
        return PressureFactors(domain_id, self.domain_value(state, domain_id) - 2.0,
                               baseline_drift)

    def pressure_value(self, domain_id, factors):
        return 1.0 / max(factors.margin, 0.1)

    def expected_deterioration(self, state, domain_id, baseline_drift, pressure_value,
                               pressure_factors):
        # Signed change per period under "steady": negative means the domain is falling.
        return float(baseline_drift)

    # Constraints: nothing is forbidden in this example.
    def constraint_profile(self, state, policy_id, action_ids, regime, governing_domain_ids):
        return PolicyConstraintProfile(policy_id,
                                       (ConstraintObservation("action_allowed", False),))


if __name__ == "__main__":
    p = World().perceived_decision_state_from_actual(actual_state(9.0))
    print("state:", p.state_id, "| perceived battery:", p.represented_state.powers[POWER].value)
