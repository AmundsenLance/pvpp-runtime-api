"""Coffee vending — one canonical decision cycle against PV-PP Runtime V2.1 (v0.141).

Chapter 6 example. The host owns every domain semantic in this file: what the
domains mean, how margins and drift are measured, what each policy is projected to
do, and which constraints apply. The runtime owns the stage order and the rules
each stage enforces. Execution is not requested, so nothing here changes the
machine's actual state.
"""
import os, sys
# Point PVPP_RUNTIME_PATH at the runtime-v2.1 folder (the one containing pvpp_runtime/).
if os.environ.get("PVPP_RUNTIME_PATH"):
    sys.path.insert(0, os.environ["PVPP_RUNTIME_PATH"])

from pvpp_runtime import (
    PVPPRuntime, PVPPRegistry, WorldState,
    DomainDefinition, ActionDefinition, GoverningConfiguration, RegimeConfiguration,
    ConstraintRuleDefinition, GraphInstanceDefinition, GraphTransformationDefinition,
    SigmaOrderDefinition, PressureFactors, ConstraintObservation, PolicyConstraintProfile,
    PolicyProjectionRecord, RecoveryCorridorProjection,
    CanonicalDecisionCycleRequest, PreliminaryPreservationObject, DomainFrame, DomainFrameTarget,
)
from pvpp_runtime.models import ActionProjection

# --------------------------------------------------------------------------- registry
# Two domains. Values are host-defined margins; thresholds mark failure.
#   D  delivery     — a paying buyer receives coffee or is made whole
#   T  transaction  — money moves only against delivery or a completed remedy
def build_registry(include_exit=True):
    reg = PVPPRegistry()
    reg.register_domain(DomainDefinition("D", "delivery: buyer receives coffee or is made whole", 5.0))
    reg.register_domain(DomainDefinition("T", "transaction integrity: money moves only against delivery", 5.0))

    # Actions. "steady" is required by the runtime: baseline continuation, used by H.
    reg.register_action(ActionDefinition("steady", "baseline: machine idles, buyer waits", ("D", "T")))
    reg.register_action(ActionDefinition("sell", "authorize, dispense, then capture payment", ("D", "T")))
    reg.register_action(ActionDefinition("decline", "refuse the sale before any charge", ("D", "T")))

    reg.register_governing_configuration(GoverningConfiguration(epsilon_h=10.0))
    reg.register_regime_configuration(RegimeConfiguration(
        tau_h_existential=1, tau_h_survival=2, tau_h_stabilization=4,
        tau_phi_existential=100, tau_phi_survival=50, tau_phi_stabilization=10))
    reg.register_constraint_rule(ConstraintRuleDefinition("card_network", "hard",
        description="a card sale requires a reachable payment network"))

    # Graph: one instance (the purchase episode) and one transformation per family.
    reg.register_graph_instance(GraphInstanceDefinition("purchase", "episode", ("D", "T"), "active"))
    reg.register_graph_transformation(GraphTransformationDefinition(
        "sell", "purchase", "purchase", "continuation", ("D", "T"), "reachable", "sell", ("continuation",)))
    if include_exit:
        reg.register_graph_transformation(GraphTransformationDefinition(
            "decline", "purchase", "purchase", "exit_transfer_liquidation", ("D", "T"), "reachable",
            "decline", ("exit",)))

    # Sigma order: deterministic tie resolution only (Stage 3), never a preference score.
    reg.register_sigma_order(SigmaOrderDefinition("graph:sell", 10))
    reg.register_sigma_order(SigmaOrderDefinition("graph:decline", 20))
    return reg

# --------------------------------------------------------------------------- host adapter
class CoffeeWorld:
    """Host-owned mechanics. `state.powers` holds the represented (perceived) state."""

    def perceive(self, state):
        return state

    def domain_value(self, state, domain_id):
        return float(state.powers[domain_id])

    def project(self, state, action):
        # Baseline continuation: the waiting buyer's delivery margin erodes.
        if action.id == "steady":
            p = dict(state.powers); p["D"] -= 1.0; p["T"] -= 0.5
            return ActionProjection(action.id, WorldState(state.time + 1, p, state.metadata), True)
        return ActionProjection(action.id, state, True)

    # Phi and H: host supplies margins and drift; the runtime computes pressure and horizon.
    def pressure_factors(self, state, domain_id, baseline_drift):
        threshold = 5.0
        drift = {"D": -1.0, "T": -0.5}[domain_id]
        return PressureFactors(domain_id, self.domain_value(state, domain_id) - threshold, drift)

    def pressure_value(self, domain_id, factors):
        return 1.0 / max(factors.margin, 0.1)

    def expected_deterioration(self, state, domain_id, baseline_drift, pressure_value, pressure_factors):
        return pressure_factors.local_trajectory

    # Constraints: typed observations over the represented state.
    def constraint_profile(self, state, policy_id, action_ids, regime, governing):
        network_down = not state.metadata.get("network_up", True)
        violated = "sell" in action_ids and network_down
        return PolicyConstraintProfile(policy_id, (ConstraintObservation("card_network", violated),))

    def compare_constraint_violation_severity(self, a, pa, b, pb, cls):
        return 0

# --------------------------------------------------------------------------- projection service
class CoffeeProjection:
    """Shared projection Q_t(pi), supplied as a PolicyProjectionService.

    It says what each policy is projected to do to each domain. It projects; it never
    filters, ranks, or selects. The runtime licenses each request and validates each record.
    """

    def project(self, req):
        state, action_ids = req.represented_state, req.action_ids
        cups = state.metadata.get("cups", 0)
        corridors, horizons = [], {}
        if "sell" in action_ids:
            ok = cups > 0
            # Delivery succeeds only if a cup is available; a failed dispense after
            # capture leaves the buyer charged and unserved.
            horizons = {"D": 30.0 if ok else 0.5, "T": 30.0 if ok else 0.5}
            for d, f in (("D", "delivery"), ("T", "transaction")):
                corridors.append(RecoveryCorridorProjection(d, f, ok, ok, ok, 1.0 if ok else None,
                                                            None if ok else 0.5))
        else:  # decline: nobody is charged; the buyer is made whole but not served
            horizons = {"D": 12.0, "T": 30.0}
            for d, f in (("D", "delivery"), ("T", "transaction")):
                corridors.append(RecoveryCorridorProjection(d, f, True, True, True, 1.0))
        # Echo the request's identity and horizon; horizons at the limit are right-censored.
        censored = tuple(d for d, h in horizons.items() if h >= req.projection_horizon)
        return PolicyProjectionRecord(
            req.policy_id, True, state, horizons, tuple(corridors),
            projection_horizon=req.projection_horizon, right_censored_domain_ids=censored,
            state_id=req.state_id, state_time=state.time, candidate_mode=req.candidate_mode,
            model_version="coffee-q1", projection_input_trace=dict(req.projection_input_trace),
        )

# --------------------------------------------------------------------------- one cycle
def request(required_families=("continuation", "exit_transfer_liquidation"),
            required_classes=("continuation", "exit")):
    return CanonicalDecisionCycleRequest(
        preservation_object=PreliminaryPreservationObject(
            "buyer-whole", "a paying buyer receives coffee or is made whole"),
        domain_frame=DomainFrame((DomainFrameTarget("D", "delivery"), DomainFrameTarget("T", "transaction"))),
        required_graph_family_ids=required_families,
        materially_required_policy_class_ids=required_classes,
        projection_horizon=30.0,
    )

def make_runtime(include_exit=True):
    return PVPPRuntime(build_registry(include_exit), CoffeeWorld(),
                       projection_service=CoffeeProjection())

def decide(cups, network_up=True, include_exit=True):
    rt = make_runtime(include_exit)
    state = WorldState(0, {"D": 10.0, "T": 10.0}, {"cups": cups, "network_up": network_up})
    return rt.evaluate_canonical_decision_cycle(state, request())

def summarize(label, cyc):
    print(f"\n== {label}")
    print("  trace:      ", " -> ".join(cyc.pipeline_trace))
    print("  status:     ", cyc.status, "| stopped at:", cyc.stopped_at)
    if cyc.governing_assessment:
        print("  governing:  ", cyc.governing_assessment.governing_domain_ids,
              "| regime:", cyc.regime_assessment.regime)
    if cyc.graph_assessment:
        print("  graph:      ", cyc.graph_assessment.status, cyc.graph_assessment.seed_ids,
              cyc.graph_assessment.failure_codes or "")
    if cyc.constraints:
        print("  feasible:   ", cyc.constraints.feasible_policy_ids,
              "| infeasible:", cyc.constraints.infeasible_policy_ids)
    if cyc.adequacy:
        print("  adequate:   ", cyc.adequacy.adequate_policy_ids,
              "| inadequate:", cyc.adequacy.inadequate_policy_ids)
    if cyc.selection:
        s1 = cyc.selection.sigma.stage1.survivor_policy_ids if cyc.selection.sigma else ()
        print("  selected:   ", cyc.selection.selected_policy_id, "| Stage 1 frontier:", s1)

if __name__ == "__main__":
    summarize("A. cups available", decide(cups=12))
    summarize("B. cups exhausted (evidence admitted)", decide(cups=0))
    summarize("C. payment network down", decide(cups=12, network_up=False))
    summarize("D. exit family never represented", decide(cups=12, include_exit=False))
