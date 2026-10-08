"""B.1 Registry setup: domains, actions, constraints, configurations, graph, and Sigma order."""

from pvpp_runtime import (
    PVPPRegistry,
    DomainDefinition,
    ProductivePowerDefinition,
    ActionDefinition,
    RecoveryPlanDefinition,
    GoverningConfiguration,
    RegimeConfiguration,
    ConstraintRuleDefinition,
    GraphInstanceDefinition,
    GraphTransformationDefinition,
    SigmaOrderDefinition,
)

DOMAIN, POWER, FUNCTION = "energy", "battery_capacity", "measurement_service"


def build_registry() -> PVPPRegistry:
    r = PVPPRegistry()
    r.register_domain(DomainDefinition(DOMAIN, "usable battery energy", threshold=2.0))
    r.register_power(ProductivePowerDefinition(POWER, DOMAIN, "capacity to power sensing"))
    # "steady" is required by the PVPPRuntime constructor: it is the baseline continuation.
    for aid, desc in (
        ("steady", "baseline drain"),
        ("sample", "take one measurement"),
        ("recharge", "restore the battery"),
    ):
        r.register_action(ActionDefinition(aid, desc, (DOMAIN,)))
    r.register_recovery_plan(
        RecoveryPlanDefinition(
            "battery_recovery", DOMAIN, FUNCTION, "recharge", (), deadline_offset=2.0
        )
    )
    r.register_governing_configuration(GoverningConfiguration(epsilon_h=0.0))
    r.register_regime_configuration(
        RegimeConfiguration(
            tau_h_existential=1.0,
            tau_h_survival=3.0,
            tau_h_stabilization=8.0,
            tau_phi_existential=10.0,
            tau_phi_survival=2.0,
            tau_phi_stabilization=0.5,
        )
    )
    r.register_constraint_rule(ConstraintRuleDefinition("action_allowed", "hard"))
    r.register_graph_instance(
        GraphInstanceDefinition("sensor", "productive_system", (DOMAIN,), "active")
    )
    r.register_graph_transformation(
        GraphTransformationDefinition(
            "continue_sampling",
            "sensor",
            "sensor",
            "continuation",
            (DOMAIN,),
            "reachable",
            "sample",
            ("continuation",),
        )
    )
    r.register_graph_transformation(
        GraphTransformationDefinition(
            "restore_battery",
            "sensor",
            "sensor",
            "corrective_repair",
            (DOMAIN,),
            "reachable",
            "recharge",
            ("recovery",),
            structurally_required=True,
        )
    )
    # Standard Sigma needs an explicit order for Stage-3 ties (3.11). Lower index wins.
    r.register_sigma_order(SigmaOrderDefinition("graph:continue_sampling", 20))
    r.register_sigma_order(SigmaOrderDefinition("graph:restore_battery", 10))
    return r
