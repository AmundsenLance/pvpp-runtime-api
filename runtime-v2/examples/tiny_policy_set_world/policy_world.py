from __future__ import annotations
from pvpp_runtime import ActionProjection, ExecutionResult, ProductivePowerState, WorldState

class PolicyChoiceWorld:
    """Tiny host world for same-period policy-set consequence comparison."""
    def __init__(self, gains=None):
        self.gains = gains or {"gather_small": 15.0, "gather_large": 20.0}

    def perceive(self, state):
        return state

    def domain_value(self, state, domain_id):
        if domain_id == "F":
            return state.power_value("food")
        if domain_id == "K":
            return state.power_value("knowledge")
        raise KeyError(domain_id)

    def project(self, state, action):
        powers = dict(state.powers)
        food = state.power_value("food")
        if action.id == "steady":
            food -= 10.0
        elif action.id in self.gains:
            food += float(self.gains[action.id])
        powers["food"] = ProductivePowerState("food", food)
        return ActionProjection(action.id, WorldState(state.time, powers, dict(state.metadata)), True)

    def project_policy(self, state, action_ids):
        # All listed actions are represented as occurring in the same host period.
        # Teaching actions do not alter food; each discretionary gather action adds its
        # registered host-world gain. No time/baseline transition is applied twice.
        powers = dict(state.powers)
        food = state.power_value("food")
        for aid in action_ids:
            if aid in self.gains:
                food += float(self.gains[aid])
        powers["food"] = ProductivePowerState("food", food)
        return ActionProjection("policy:"+"+".join(action_ids), WorldState(state.time, powers, dict(state.metadata)), True)

    def execute(self, state, action_id):
        pr = self.project(state, type("A", (), {"id": action_id})())
        return ExecutionResult(action_id, pr.next_state, pr.feasible, pr.reasons)
