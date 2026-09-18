"""PV-PP Runtime V2 battery call-through application.

This example extends the canonical battery-service decision cycle through V2
native execution.  A real host callable is registered for the consequential
``recharge`` action, but registration itself grants no authority.  The callable
can be entered only through a single-use runtime-issued native execution
authorization derived from the canonical decision -> execution license ->
epsilon episode lineage.

The host still owns actual persistent state and the Layer-1 transition. Native
callable completion is execution evidence; it is not itself authoritative state
mutation.
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
    CleanExecutionFailure, ExecutionBindingIdentity, ExecutionBindingRegistry,
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



class BatteryCharger:
    """Small host-side device boundary used to prove real native call-through."""
    def __init__(self, failure_mode: str | None = None):
        self.failure_mode = failure_mode
        self.calls: list[dict] = []

    def recharge(self, context, *, target_units: float = 8.0):
        self.calls.append({
            "execution_id": context.execution_id,
            "action_id": context.action_id,
            "binding_id": context.binding_id,
            "target_units": target_units,
        })
        if self.failure_mode == "clean":
            # Explicit evidence that no external charging effect occurred.
            raise CleanExecutionFailure("charger rejected command before external effect")
        if self.failure_mode == "indeterminate":
            # An unclassified failure after callable entry cannot prove absence
            # of external effect, so V2 conservatively reports indeterminate.
            raise RuntimeError("charger connection lost after command dispatch")
        return {"accepted": True, "target_units": target_units}


def build_bindings(rt: PVPPRuntime, charger: BatteryCharger) -> ExecutionBindingRegistry:
    bindings = ExecutionBindingRegistry(tuple(rt.registry.actions))
    bindings.register(
        ExecutionBindingIdentity(
            "battery-recharge-native", "recharge", "1.0",
            ("battery-callthrough-example", "host-charger-adapter"),
        ),
        charger.recharge,
    )
    return bindings


def prepare_callthrough(actual=None, *, failure_mode: str | None = None, episode_id: str = "battery-episode-1"):
    """Run canonical governance through issuance of one native authorization."""
    actual = actual or make_actual()
    rt = build_runtime()
    request = make_request()
    integrated = rt.evaluate_integrated_canonical_cycle(actual, request)
    cycle = integrated.decision
    license = rt.build_execution_license_from_cycle(cycle, request.domain_frame)
    entry = rt.instantiate_execution(episode_id, license, entry_sufficient=True, max_steps=2)

    charger = BatteryCharger(failure_mode)
    bindings = build_bindings(rt, charger)
    action_id = license.action_ids[0]
    authorization = rt.issue_native_execution_authorization(
        entry.episode,
        action_id,
        bindings,
        decision_cycle_id=f"battery-cycle:{actual.state_id}",
    )
    return actual, rt, request, integrated, license, entry.episode, charger, bindings, authorization


def run_once(actual=None):
    """Successful V2 path: canonical decision -> authorized callable -> Layer 1."""
    (actual, rt, request, integrated, license, episode,
     charger, bindings, authorization) = prepare_callthrough(actual)

    # The consequential host callable is entered by the runtime, not directly
    # by application code. Authorization is consumed immediately before entry.
    native_result = rt.invoke_authorized_native(
        authorization, bindings, target_units=8.0
    )

    terminal = rt.advance_execution(
        episode,
        ExecutionObservation(
            "native-recharge-result",
            completed=(native_result.status == "succeeded"),
            information={
                "native_execution_id": native_result.execution_id,
                "native_status": native_result.status,
                "native_return_value": native_result.return_value,
            },
        ),
    )

    handoff = rt.build_layer1_transition_handoff(terminal)
    transition = rt.apply_layer1_transition(actual, handoff)
    validation = rt.validate_layer1_transition_result(actual, handoff, transition)
    provenance = rt.build_execution_transition_provenance(actual, handoff, transition, validation)
    return {
        "actual": actual, "runtime": rt, "integrated": integrated,
        "license": license, "episode": episode, "charger": charger,
        "bindings": bindings, "authorization": authorization,
        "native_result": native_result, "terminal": terminal,
        "handoff": handoff, "transition": transition,
        "validation": validation, "provenance": provenance,
    }


def run_denied_before_call(actual=None):
    """Issue authority, invalidate it, and prove the callable is never entered."""
    (actual, rt, request, integrated, license, episode,
     charger, bindings, authorization) = prepare_callthrough(actual, episode_id="battery-episode-denied")
    rt.invalidate_native_execution_authorizations(
        episode_id=episode.episode_id,
        reason="battery state changed before external execution",
    )
    try:
        rt.invoke_authorized_native(authorization, bindings, target_units=8.0)
    except RuntimeError as exc:
        return {
            "runtime": rt, "charger": charger, "authorization": authorization,
            "error": exc,
        }
    raise AssertionError("invalidated native authorization unexpectedly executed")


def run_failure(failure_mode: str = "indeterminate", actual=None):
    """Enter the callable and return V2's normalized execution-failure evidence."""
    (actual, rt, request, integrated, license, episode,
     charger, bindings, authorization) = prepare_callthrough(
        actual, failure_mode=failure_mode, episode_id=f"battery-episode-{failure_mode}"
    )
    native_result = rt.invoke_authorized_native(
        authorization, bindings, target_units=8.0
    )
    return {
        "runtime": rt, "charger": charger, "authorization": authorization,
        "native_result": native_result,
    }


if __name__ == "__main__":
    success = run_once()
    print("SUCCESS")
    print("  sigma_selected:", success["integrated"].decision.selection.selected_policy_id)
    print("  licensed_actions:", success["license"].action_ids)
    print("  native_status:", success["native_result"].status)
    print("  native_return:", success["native_result"].return_value)
    print("  callable_calls:", len(success["charger"].calls))
    print("  authorization_status:", success["runtime"].native_execution_authorization_status(success["authorization"].authorization_id))
    print("  layer1_next_state:", success["transition"].next_state.pp)
    print("  transition_valid:", success["validation"].valid)

    denied = run_denied_before_call()
    print("DENIED")
    print("  callable_calls:", len(denied["charger"].calls))
    print("  authorization_status:", denied["runtime"].native_execution_authorization_status(denied["authorization"].authorization_id))
    print("  error:", str(denied["error"]))

    failed = run_failure("indeterminate")
    print("FAILURE")
    print("  callable_calls:", len(failed["charger"].calls))
    print("  native_status:", failed["native_result"].status)
    print("  error_type:", failed["native_result"].error_type)
    print("  error_message:", failed["native_result"].error_message)
    print("  external_effect_possible:", failed["native_result"].external_effect_possible)
