"""Step 1: declare what exists. A battery-powered sensor with one domain and three actions."""

import os, sys

# Point PVPP_RUNTIME_PATH at the runtime folder (the folder that contains pvpp_runtime/).
if os.environ.get("PVPP_RUNTIME_PATH"):
    sys.path.insert(0, os.environ["PVPP_RUNTIME_PATH"])

from pvpp_runtime import (
    PVPPRegistry, DomainDefinition, ProductivePowerDefinition, ActionDefinition,
    RecoveryPlanDefinition, GoverningConfiguration, RegimeConfiguration,
    ConstraintRuleDefinition, GraphInstanceDefinition, GraphTransformationDefinition,
    SigmaOrderDefinition,
)

DOMAIN = "energy"               # what must stay viable
POWER = "battery_capacity"      # the productive power that carries it
FUNCTION = "measurement"        # what the energy is for


def build_registry(order=("graph:continue_sampling", "graph:restore_battery")):
    r = PVPPRegistry()
    # The domain fails if usable energy falls to 2.0 units.
    r.register_domain(DomainDefinition(DOMAIN, "usable battery energy", threshold=2.0))
    r.register_power(ProductivePowerDefinition(POWER, DOMAIN, "capacity to power sensing"))

    # Every registry needs "steady": what happens if the sensor does nothing new.
    for action, meaning in (("steady", "idle drain"),
                            ("sample", "take a measurement"),
                            ("recharge", "restore the battery")):
        r.register_action(ActionDefinition(action, meaning, (DOMAIN,)))

    # Recharging is the recovery route for the measurement function.
    r.register_recovery_plan(RecoveryPlanDefinition(
        "battery_recovery", DOMAIN, FUNCTION, "recharge", (), deadline_offset=2.0))

    # How close to failure counts as Stabilization, Survival, or Existential.
    r.register_governing_configuration(GoverningConfiguration(epsilon_h=0.0))
    r.register_regime_configuration(RegimeConfiguration(
        tau_h_existential=1.0, tau_h_survival=3.0, tau_h_stabilization=8.0,
        tau_phi_existential=10.0, tau_phi_survival=2.0, tau_phi_stabilization=0.5))

    # One hard rule. The host reports whether a candidate breaks it.
    r.register_constraint_rule(ConstraintRuleDefinition("action_allowed", "hard"))

    # The graph: two ways the sensor can go on from here.
    r.register_graph_instance(
        GraphInstanceDefinition("sensor", "productive_system", (DOMAIN,), "active"))
    r.register_graph_transformation(GraphTransformationDefinition(
        "continue_sampling", "sensor", "sensor", "continuation", (DOMAIN,),
        "reachable", "sample", ("continuation",)))
    r.register_graph_transformation(GraphTransformationDefinition(
        "restore_battery", "sensor", "sensor", "corrective_repair", (DOMAIN,),
        "reachable", "recharge", ("recovery",), structurally_required=True))

    # Tie-break order, used only when two options are equally good. Lower wins.
    for rank, policy in enumerate(order, start=1):
        r.register_sigma_order(SigmaOrderDefinition(policy, 10 * rank))
    return r


if __name__ == "__main__":
    r = build_registry()
    print("domains:        ", tuple(r.domains))
    print("actions:        ", tuple(r.actions))
    print("transformations:", tuple(r.graph_transformations))
