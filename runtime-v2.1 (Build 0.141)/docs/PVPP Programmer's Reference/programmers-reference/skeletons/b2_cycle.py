"""B.2 One decision cycle: host adapter, projection service, request, and the integrated entry."""

from pvpp_runtime import (
    PVPPRuntime,
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
    CanonicalDecisionCycleRequest,
    PreliminaryPreservationObject,
    DomainFrame,
    DomainFrameTarget,
)
from b1_registry import build_registry, DOMAIN, POWER, FUNCTION
from b4_layer1 import Layer1Service


class World:
    """WorldAdapter (10.2). States facts; decides nothing."""

    def perceived_decision_state_from_actual(self, actual):  # typed perception hook (preferred)
        b = float(actual.pp["battery_units"])
        rep = WorldState(
            actual.time, {POWER: ProductivePowerState(POWER, b)}, {"state_id": actual.state_id}
        )
        return PerceivedDecisionState(
            actual.actor_id, actual.state_id, actual.time, rep, ppp={POWER: b}
        )

    def perceive(self, state):  # must return an already-represented state unchanged (10.2)
        return state

    def domain_value(self, state, domain_id):
        return state.powers[POWER].value

    def project(self, state, action):  # baseline continuation with "steady"
        b = self.domain_value(state, DOMAIN) + {"steady": -1.0, "sample": -1.0}.get(action.id, 0.0)
        if action.id == "recharge":
            b = 8.0
        return ActionProjection(
            action.id,
            WorldState(
                state.time + 1, {POWER: ProductivePowerState(POWER, b)}, dict(state.metadata)
            ),
            True,
        )

    def pressure_factors(self, state, domain_id, baseline_drift):
        return PressureFactors(domain_id, self.domain_value(state, domain_id) - 2.0, baseline_drift)

    def pressure_value(self, domain_id, factors):
        return 1.0 / max(factors.margin, 0.1)

    def expected_deterioration(
        self, state, domain_id, baseline_drift, pressure_value, pressure_factors
    ):
        return float(baseline_drift)  # signed change per period; negative when falling

    def constraint_profile(self, state, policy_id, action_ids, regime, governing_domain_ids):
        return PolicyConstraintProfile(policy_id, (ConstraintObservation("action_allowed", False),))


class Projection:
    """PolicyProjectionService (10.3): one Q_t(pi) per request; never selects."""

    def project(self, req):
        start = req.represented_state.powers[POWER].value
        recharge = "recharge" in req.action_ids
        end = 8.0 if recharge else start - 1.0
        horizon = (
            req.projection_horizon if recharge else max(0.0, min(req.projection_horizon, end - 2.0))
        )
        corridor = RecoveryCorridorProjection(
            DOMAIN,
            FUNCTION,
            pre_recovery_viability_preserved=start >= 2.0,
            recovery_capable_region_reached=recharge,
            joint_sustainment_supported=True,
            recovery_entry_time=1.0 if recharge else None,
            projected_extinction_time=None if recharge else horizon,
        )
        terminal = WorldState(
            req.represented_state.time + 1,
            {POWER: ProductivePowerState(POWER, end)},
            dict(req.represented_state.metadata),
        )
        return PolicyProjectionRecord(
            req.policy_id,
            False,
            terminal,
            {DOMAIN: horizon},
            (corridor,),
            projection_horizon=req.projection_horizon,
            right_censored_domain_ids=(DOMAIN,) if recharge else (),
            state_id=req.state_id,
            state_time=req.represented_state.time,
            candidate_mode=req.candidate_mode,
            model_version="skeleton-q1",
            projection_input_trace=dict(req.projection_input_trace),
        )


def make_runtime():
    return PVPPRuntime(
        build_registry(),
        World(),
        projection_service=Projection(),
        layer1_transition_service=Layer1Service(),
    )


def make_request():
    return CanonicalDecisionCycleRequest(
        PreliminaryPreservationObject("keep_service", "preserve measurement-service continuity"),
        DomainFrame((DomainFrameTarget(DOMAIN, FUNCTION),)),
        required_graph_family_ids=("continuation", "corrective_repair"),
        materially_required_policy_class_ids=("continuation", "recovery"),
        projection_horizon=10.0,
        projection_input_trace={"source": "appendix-b"},
    )


def make_actual(battery=3.0):
    return ActualPersistentStateEnvelope(
        "sensor-A",
        "state-0",
        0.0,
        {"battery_units": battery},
        {"stored_charge": battery},
        {"service_available": True},
        {},
    )


def run_cycle(rt=None):
    rt = rt or make_runtime()
    integrated = rt.evaluate_integrated_canonical_cycle(
        make_actual(), make_request()
    )  # execute=False
    return rt, integrated


if __name__ == "__main__":
    _, out = run_cycle()
    d = out.decision
    print(out.status, d.stopped_at, d.selection.selected_policy_id if d.selection else None)
