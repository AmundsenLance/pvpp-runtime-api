from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pvpp_runtime import (
    PVPPRuntime, PVPPRegistry, DomainDefinition, ActionDefinition,
    ProductivePowerDefinition, ProductivePowerState, WorldState,
)
from food_world import TinyFoodWorld


def build_runtime():
    registry = PVPPRegistry()
    registry.register_domain(DomainDefinition("F", "Food productive power", threshold=0.0, governing_horizon=3.0))
    registry.register_domain(DomainDefinition("L", "Labor productive power", threshold=0.0, governing_horizon=1.0))
    registry.register_power(ProductivePowerDefinition("food_stock", "F", "Accessible food stock"))
    registry.register_power(ProductivePowerDefinition("labor_available", "L", "Currently executable labor", persistent=False))
    registry.register_action(ActionDefinition("steady", "Continue without intervention", ("F", "L")))
    registry.register_action(ActionDefinition("gather_food", "Spend 4 labor to gather 20 food", ("F", "L")))
    registry.register_action(ActionDefinition("rest", "Recover 4 labor while consuming food", ("F", "L")))
    return PVPPRuntime(registry, TinyFoodWorld())


def initial_state(food=30.0, labor=10.0, time=0.0):
    return WorldState(time, {
        "food_stock": ProductivePowerState("food_stock", food),
        "labor_available": ProductivePowerState("labor_available", labor, executable_value=labor),
    })


if __name__ == "__main__":
    rt = build_runtime()
    state = initial_state()
    for _ in range(4):
        a = rt.decide(state)
        print(
            f"t={state.time:g} F={state.power_value('food_stock'):g} L={state.power_value('labor_available'):g} "
            f"G={a.governing_domains} steady={a.steady_adequate} selected={a.selected_action}"
        )
        if a.selected_action is None:
            break
        er = rt.world.execute(state, a.selected_action)
        rt.record_execution(er)
        state = er.next_state
