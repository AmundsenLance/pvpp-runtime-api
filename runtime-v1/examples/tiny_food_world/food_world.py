from __future__ import annotations
from pvpp_runtime import WorldState
from pvpp_runtime.models import ActionDefinition, ActionProjection, ProductivePowerState, ExecutionResult


class TinyFoodWorld:
    """Deliberately tiny deterministic host world.

    food_stock is an F productive power.
    labor_available is an L productive power with current executability semantics.
    Each application invocation represents one period.
    """

    consumption = 10.0
    spoilage = 2.0

    def perceive(self, state: WorldState) -> WorldState:
        return state

    def domain_value(self, state: WorldState, domain_id: str) -> float:
        if domain_id == "F":
            return state.power_value("food_stock")
        if domain_id == "L":
            return state.power_value("labor_available")
        raise KeyError(domain_id)

    def project(self, state: WorldState, action: ActionDefinition) -> ActionProjection:
        food = state.power_value("food_stock")
        labor = state.power_value("labor_available")
        reasons = []
        if action.id == "gather_food" and labor < 4:
            reasons.append("requires 4 labor units")
        if reasons:
            return ActionProjection(action.id, state, False, tuple(reasons))

        if action.id == "steady":
            next_food, next_labor = food - 12, labor
        elif action.id == "gather_food":
            next_food, next_labor = food + 20 - 12, labor - 4
        elif action.id == "rest":
            next_food, next_labor = food - 12, min(10.0, labor + 4)
        else:
            return ActionProjection(action.id, state, False, ("unknown host action",))

        next_state = WorldState(
            state.time + 1,
            {
                "food_stock": ProductivePowerState("food_stock", max(0.0, next_food)),
                "labor_available": ProductivePowerState(
                    "labor_available", max(0.0, next_labor), executable_value=max(0.0, next_labor)
                ),
            },
        )
        return ActionProjection(action.id, next_state, True)

    def execute(self, state: WorldState, action_id: str) -> WorldState:
        action = ActionDefinition(action_id, action_id, ("F", "L"))
        projection = self.project(state, action)
        if not projection.feasible:
            raise RuntimeError(projection.reasons)
        return ExecutionResult(action_id, projection.next_state, True)
