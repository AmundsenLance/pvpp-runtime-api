"""The operations agent's decision model, reduced from Chapter 10 to the failover decision.

Two governing domains: availability (A) and control (C). The service is degraded by a bad
configuration, the replica route is reachable, and the change freeze is off. Whether the agent
may fail over depends on one perceived fact: whether it holds the write credential.
"""

import os, sys

if os.environ.get("PVPP_RUNTIME_PATH"):
    sys.path.insert(0, os.environ["PVPP_RUNTIME_PATH"])

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
    WorldState,
    ProductivePowerState,
    PerceivedDecisionState,
    ActualPersistentStateEnvelope,
    ActionProjection,
    PressureFactors,
    PolicyConstraintProfile,
    ConstraintObservation,
    PolicyProjectionRecord,
    RecoveryCorridorProjection,
    PVPPRuntime,
    CanonicalDecisionCycleRequest,
    PreliminaryPreservationObject,
    DomainFrame,
    DomainFrameTarget,
)

WRITE_ACTIONS = {"restart", "failover"}  # actions that need the write credential
CHANGE_ACTIONS = {"failover"}  # actions the change freeze forbids


def build_registry():
    r = PVPPRegistry()
    for d, name in (("A", "availability"), ("C", "control")):
        r.register_domain(DomainDefinition(d, name, threshold=0.0))
        r.register_power(
            ProductivePowerDefinition(f"{d}_capacity", d, f"capacity behind {name}")
        )
    for a, text in (
        ("steady", "do nothing new"),
        ("watch", "keep watching the service"),
        ("restart", "restart the service"),
        ("failover", "fail over to the replica"),
        ("escalate", "page the on-call human"),
    ):
        r.register_action(ActionDefinition(a, text, ("A", "C")))
    r.register_recovery_plan(
        RecoveryPlanDefinition(
            "service_recovery", "A", "availability", "failover", (), deadline_offset=2.0
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
    r.register_constraint_rule(ConstraintRuleDefinition("write_credential", "hard"))
    r.register_constraint_rule(ConstraintRuleDefinition("change_freeze", "hard"))
    r.register_graph_instance(
        GraphInstanceDefinition("service", "productive_system", ("A", "C"), "active")
    )
    for t, family, cls, required in (
        ("watch", "continuation", "continuation", False),
        ("restart", "corrective_repair", "recovery", True),
        ("failover", "structural_reconfiguration", "structural", False),
        ("escalate", "substitution", "escalation", False),
    ):
        r.register_graph_transformation(
            GraphTransformationDefinition(
                t,
                "service",
                "service",
                family,
                ("A", "C"),
                "reachable",
                t,
                (cls,),
                structurally_required=required,
            )
        )
    for rank, policy in enumerate(
        ("graph:failover", "graph:restart", "graph:escalate", "graph:watch"), start=1
    ):
        r.register_sigma_order(SigmaOrderDefinition(policy, 10 * rank))
    return r


def actual_state(credential=True, freeze=False, availability=4.0, time=0.0):
    """The host's record of the service: error budget (A), rollback headroom (C), and facts."""
    return ActualPersistentStateEnvelope(
        "ops-agent",
        f"svc-{time}-{credential}-{freeze}",
        time,
        {"A_capacity": availability, "C_capacity": 30.0},
        {},
        {"service_available": True},
        {"credential": credential, "freeze": freeze, "diagnosis": "bad config"},
    )


class OpsWorld:
    """World adapter: facts only. Without action the error budget falls a unit a period."""

    def perceived_decision_state_from_actual(self, actual):
        powers = {k: ProductivePowerState(k, float(v)) for k, v in actual.pp.items()}
        seen = WorldState(actual.time, powers, dict(actual.context, state_id=actual.state_id))
        return PerceivedDecisionState(
            actual.actor_id,
            actual.state_id,
            actual.time,
            seen,
            ppp={k: float(v) for k, v in actual.pp.items()},
        )

    def perceive(self, state):
        return state

    def domain_value(self, state, domain_id):
        return state.powers[f"{domain_id}_capacity"].value

    def project(self, state, action):
        drift = {"A": -1.0, "C": -0.1}
        powers = {
            k: ProductivePowerState(k, v.value + drift[k[0]]) for k, v in state.powers.items()
        }
        return ActionProjection(
            action.id, WorldState(state.time + 1, powers, dict(state.metadata)), True
        )

    def pressure_factors(self, state, domain_id, baseline_drift):
        return PressureFactors(domain_id, self.domain_value(state, domain_id), baseline_drift)

    def pressure_value(self, domain_id, factors):
        return 1.0 / max(factors.margin, 0.1)

    def expected_deterioration(
        self, state, domain_id, baseline_drift, pressure_value, pressure_factors
    ):
        return float(baseline_drift)

    def constraint_profile(self, state, policy_id, action_ids, regime, governing_domain_ids):
        m, acts = state.metadata, set(action_ids)
        return PolicyConstraintProfile(
            policy_id,
            (
                ConstraintObservation(
                    "write_credential", bool(acts & WRITE_ACTIONS) and not m["credential"]
                ),
                ConstraintObservation(
                    "change_freeze", bool(acts & CHANGE_ACTIONS) and m["freeze"]
                ),
            ),
        )


class OpsProjection:
    """Projected consequences, as in Listing 10.1, for a bad-configuration diagnosis."""

    def project(self, req):
        a, c = {
            "watch": (0.8, 30.0),
            "restart": (0.5, 30.0),
            "failover": (25.0, 30.0),
            "escalate": (12.0, 30.0),
        }[req.action_ids[0]]
        corridors = tuple(
            RecoveryCorridorProjection(
                k, f, h > 1, h > 1, h > 1, 1.0 if h > 1 else None, None if h > 1 else h
            )
            for k, f, h in (("A", "availability", a), ("C", "control", c))
        )
        bound = req.projection_horizon
        horizons = {"A": min(a, bound), "C": min(c, bound)}
        return PolicyProjectionRecord(
            req.policy_id,
            True,
            req.represented_state,
            horizons,
            corridors,
            projection_horizon=req.projection_horizon,
            right_censored_domain_ids=tuple(k for k, h in horizons.items() if h >= bound),
            state_id=req.state_id,
            state_time=req.represented_state.time,
            candidate_mode=req.candidate_mode,
            model_version="ops-q1",
            projection_input_trace=dict(req.projection_input_trace),
        )


def make_runtime():
    return PVPPRuntime(build_registry(), OpsWorld(), projection_service=OpsProjection())


def request():
    return CanonicalDecisionCycleRequest(
        PreliminaryPreservationObject(
            "keep_service", "keep the service available and under control"
        ),
        DomainFrame((DomainFrameTarget("A", "availability"),)),
        required_graph_family_ids=("continuation", "corrective_repair"),
        materially_required_policy_class_ids=("continuation", "recovery"),
        projection_horizon=30.0,
    )


def decide(actual, rt=None):
    rt = rt or make_runtime()
    return rt, rt.evaluate_integrated_canonical_cycle(actual, request())


if __name__ == "__main__":
    for cred in (True, False):
        _, out = decide(actual_state(credential=cred))
        d = out.decision
        print(f"credential={cred}: {out.status}")
        print("  regime:   ", d.regime_assessment.regime)
        print("  candidates:", tuple(c.id for c in d.pi_construction.policy_space.candidates))
        print("  adequate: ", d.adequacy.adequate_policy_ids if d.adequacy else None)
        print("  selected: ", d.selection.selected_policy_id if d.selection else None)
