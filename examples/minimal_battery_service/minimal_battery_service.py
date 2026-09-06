"""PV-PP Runtime v0.70 native minimal application.

Scenario: a remote sensor must preserve measurement-service continuity while its
battery is near the operating floor.  The canonical cycle compares ordinary
sampling with a battery-recharge recovery path.  The host owns actual state and
Layer-1 mutation; the runtime owns the PV-PP decision cycle.
"""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import sys

# For the standalone beta-package example, point at an untouched v0.70 checkout.
RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "pvpp70" / "pvpp_runtime_prototype_v0_70"
if RUNTIME_ROOT.exists():
    sys.path.insert(0, str(RUNTIME_ROOT))

from pvpp_runtime import (
    ActionDefinition, ActionProjection, ActualPersistentStateEnvelope,
    CanonicalDecisionCycleRequest, ConstraintObservation, ConstraintRuleDefinition,
    DomainDefinition, DomainFrame, DomainFrameTarget, ExecutionObservation,
    GoverningConfiguration, GraphInstanceDefinition, GraphTransformationDefinition,
    Layer1TransitionResult, PerceivedDecisionState, PolicyConstraintProfile,
    PolicyProjectionRecord, PreliminaryPreservationObject, ProductivePowerDefinition,
    ProductivePowerState, PVPPRegistry, PVPPRuntime, RecoveryCorridorProjection,
    RecoveryPlanDefinition, RegimeConfiguration, SigmaOrderDefinition, WorldState,
    PressureFactors,
)

ENERGY_DOMAIN = "energy"
BATTERY_POWER = "battery_capacity"
FUNCTION_ID = "measurement_service"


def build_registry() -> PVPPRegistry:
    r = PVPPRegistry()
    r.register_domain(DomainDefinition(ENERGY_DOMAIN, "usable battery energy", threshold=2.0))
    r.register_power(ProductivePowerDefinition(BATTERY_POWER, ENERGY_DOMAIN, "capacity to power sensing and transmission"))

    # 'steady' is a frozen-runtime constructor requirement and represents baseline continuation.
    for aid, desc in (
        ("steady", "baseline continuation with background battery drain"),
        ("sample", "take and transmit one measurement"),
        ("recharge", "recharge the battery and restore service reserve"),
    ):
        r.register_action(ActionDefinition(aid, desc, (ENERGY_DOMAIN,)))

    # Recovery structure is stable registered structure. The first example uses a
    # one-step recovery trigger, so no continuation actions are needed.
    r.register_recovery_plan(RecoveryPlanDefinition(
        "battery_recovery", ENERGY_DOMAIN, FUNCTION_ID, "recharge", (), deadline_offset=2.0
    ))

    r.register_governing_configuration(GoverningConfiguration(epsilon_h=0.0))
    r.register_regime_configuration(RegimeConfiguration(
        tau_h_existential=1.0, tau_h_survival=3.0, tau_h_stabilization=8.0,
        tau_phi_existential=10.0, tau_phi_survival=2.0, tau_phi_stabilization=0.5,
    ))
    r.register_constraint_rule(ConstraintRuleDefinition("battery_action_allowed", "hard"))

    r.register_graph_instance(GraphInstanceDefinition(
        "sensor", "productive_system", (ENERGY_DOMAIN,), "active", roles=("measurement_service",)
    ))
    r.register_graph_transformation(GraphTransformationDefinition(
        "continue_sampling", "sensor", "sensor", "continuation", (ENERGY_DOMAIN,),
        "reachable", "sample", ("continuation",), structural_effect="continue current service"
    ))
    r.register_graph_transformation(GraphTransformationDefinition(
        "restore_battery", "sensor", "sensor", "corrective_repair", (ENERGY_DOMAIN,),
        "reachable", "recharge", ("recovery",), structurally_required=True,
        structural_effect="restore energy reserve before further service"
    ))

    # Ordinary Sigma Stage 3 uses explicit architecture order only after the
    # upstream gates. Lower order index wins.
    r.register_sigma_order(SigmaOrderDefinition("graph:continue_sampling", 20))
    r.register_sigma_order(SigmaOrderDefinition("graph:restore_battery", 10))
    return r


class SensorWorldAdapter:
    """Host-owned semantics used by the generic runtime."""
    def perceived_decision_state_from_actual(self, actual: ActualPersistentStateEnvelope) -> PerceivedDecisionState:
        battery = float(actual.pp["battery_units"])
        represented = WorldState(
            actual.time,
            {BATTERY_POWER: ProductivePowerState(BATTERY_POWER, battery)},
            {"state_id": actual.state_id},
        )
        return PerceivedDecisionState(
            actual.actor_id, actual.state_id, actual.time, represented,
            ppp={BATTERY_POWER: battery},
            spv_hat={"stored_charge": battery},
            pvs={FUNCTION_ID: battery > 0.0},
            x_hat={"charger_available": bool(actual.context["charger_available"])},
            confidence={BATTERY_POWER: "direct_sensor_reading"},
            uncertainty={"future_drain": "bounded_model"},
        )

    def perceive(self, state):
        return state

    def domain_value(self, state: WorldState, domain_id: str) -> float:
        assert domain_id == ENERGY_DOMAIN
        return state.powers[BATTERY_POWER].value

    def project(self, state: WorldState, action: ActionDefinition) -> ActionProjection:
        battery = self.domain_value(state, ENERGY_DOMAIN)
        if action.id == "steady":
            battery -= 1.0
        elif action.id == "sample":
            battery -= 1.0
        elif action.id == "recharge":
            battery = 8.0
        nxt = WorldState(
            state.time + 1.0,
            {BATTERY_POWER: ProductivePowerState(BATTERY_POWER, battery)},
            dict(state.metadata),
        )
        return ActionProjection(action.id, nxt, True)

    def pressure_factors(self, state, domain_id, baseline_drift):
        margin = self.domain_value(state, domain_id) - 2.0
        return PressureFactors(domain_id, margin, baseline_drift)

    def pressure_value(self, domain_id, factors):
        return 1.0 / max(factors.margin, 0.1)

    def expected_deterioration(self, state, domain_id, baseline_drift, pressure_value, pressure_factors):
        # H expects a positive deterioration magnitude; steady drains one unit/cycle.
        return abs(float(baseline_drift))

    def constraint_profile(self, state, policy_id, action_ids, regime, governing_domain_ids):
        return PolicyConstraintProfile(policy_id, (ConstraintObservation("battery_action_allowed", False),))

    def compare_constraint_violation_severity(self, *args):
        return 0


class SharedProjectionQ:
    """Canonical shared Q service: projects, but never selects."""
    def project(self, req):
        start = req.represented_state.powers[BATTERY_POWER].value
        if "recharge" in req.action_ids:
            projected = 8.0
            horizon = req.projection_horizon
            censored = (ENERGY_DOMAIN,)
            entry = 1.0
        else:
            projected = start - 1.0
            horizon = max(0.0, min(req.projection_horizon, projected - 2.0))
            censored = ()
            entry = None

        terminal = WorldState(
            req.represented_state.time + 1.0,
            {BATTERY_POWER: ProductivePowerState(BATTERY_POWER, projected)},
            dict(req.represented_state.metadata),
        )
        corridor = RecoveryCorridorProjection(
            ENERGY_DOMAIN, FUNCTION_ID,
            pre_recovery_viability_preserved=(start >= 2.0),
            recovery_capable_region_reached=("recharge" in req.action_ids),
            joint_sustainment_supported=True,
            recovery_entry_time=entry,
            projected_extinction_time=None if censored else horizon,
        )
        return PolicyProjectionRecord(
            req.policy_id, False, terminal, {ENERGY_DOMAIN: horizon}, (corridor,),
            projection_horizon=req.projection_horizon,
            right_censored_domain_ids=censored,
            state_id=req.state_id,
            state_time=req.represented_state.time,
            candidate_mode=req.candidate_mode,
            projected_domain_trajectories={ENERGY_DOMAIN: (start, projected)},
            reachable_viable={ENERGY_DOMAIN: ("sensor",)},
            information_quality_trace={"basis": "deterministic teaching model"},
            model_version="battery-demo-q1",
            projection_input_trace=dict(req.projection_input_trace),
        )


class SensorLayer1Transition:
    """The authoritative host mutation boundary."""
    def transition(self, current, handoff):
        pp = dict(current.pp)
        context = dict(current.context)
        actions = set(handoff.licensed_action_ids)
        if "recharge" in actions:
            pp["battery_units"] = 8.0
            context["last_host_transition"] = "recharged"
        elif "sample" in actions:
            pp["battery_units"] = max(0.0, float(pp["battery_units"]) - 1.0)
            context["samples_delivered"] = int(context.get("samples_delivered", 0)) + 1
            context["last_host_transition"] = "sampled"
        else:
            raise ValueError("host received no known licensed action")
        nxt = ActualPersistentStateEnvelope(
            current.actor_id, current.state_id + ":next", current.time + 1.0,
            pp, current.spv, current.avs, context,
        )
        return Layer1TransitionResult(
            handoff.episode_id, handoff.selected_policy_id, current.state_id,
            nxt, True, {"battery_nonnegative": pp["battery_units"] >= 0.0},
        )


def make_request() -> CanonicalDecisionCycleRequest:
    return CanonicalDecisionCycleRequest(
        PreliminaryPreservationObject("preserve_measurement_service", "preserve measurement-service continuity"),
        DomainFrame((DomainFrameTarget(ENERGY_DOMAIN, FUNCTION_ID),)),
        required_graph_family_ids=("continuation", "corrective_repair"),
        materially_required_policy_class_ids=("continuation", "recovery"),
        projection_horizon=10.0,
        projection_input_trace={"example": "battery-service-v0.1"},
    )


def make_actual(battery_units: float = 3.0, charger_available: bool = True):
    return ActualPersistentStateEnvelope(
        "sensor-A", "state-0", 0.0,
        {"battery_units": battery_units},
        {"stored_energy_record": battery_units},
        {"measurement_service_available": battery_units > 0.0},
        {"charger_available": charger_available, "samples_delivered": 0},
    )


def build_runtime():
    return PVPPRuntime(
        build_registry(), SensorWorldAdapter(),
        projection_service=SharedProjectionQ(),
        layer1_transition_service=SensorLayer1Transition(),
    )


def run_once(actual=None):
    actual = actual or make_actual()
    rt = build_runtime()
    request = make_request()

    # 1. Canonical host-driven decision cycle. No actual-world mutation occurs.
    integrated = rt.evaluate_integrated_canonical_cycle(actual, request)
    cycle = integrated.decision

    # 2. Build execution authority from the completed Sigma result.
    license = rt.build_execution_license_from_cycle(cycle, request.domain_frame)

    # 3. epsilon owns bounded realization, not Layer-1 state transition.
    entry = rt.instantiate_execution("episode-1", license, entry_sufficient=True, max_steps=2)
    terminal = rt.advance_execution(
        entry.episode,
        ExecutionObservation(
            "host-observation-1", completed=True,
            information={"host_observed": tuple(license.action_ids)},
        ),
    )

    # 4. Explicit handoff to the host-owned Layer-1 transition.
    handoff = rt.build_layer1_transition_handoff(terminal)
    transition = rt.apply_layer1_transition(actual, handoff)
    validation = rt.validate_layer1_transition_result(actual, handoff, transition)

    # 5. Build auditable transition provenance for possible later-cycle use.
    provenance = rt.build_execution_transition_provenance(actual, handoff, transition, validation)
    return rt, integrated, license, terminal, handoff, transition, validation, provenance


if __name__ == "__main__":
    _, integrated, license, terminal, handoff, transition, validation, provenance = run_once()
    print("cycle_status:", integrated.status)
    print("stopped_at:", integrated.decision.stopped_at)
    print("sigma_selected:", integrated.decision.selection.selected_policy_id)
    print("licensed_actions:", license.action_ids)
    print("epsilon_status:", terminal.status)
    print("layer1_next_state:", transition.next_state.state_id, transition.next_state.pp)
    print("transition_valid:", validation.valid)
    print("provenance_chain:", provenance.prior_state_id, "->", provenance.next_state_id)
