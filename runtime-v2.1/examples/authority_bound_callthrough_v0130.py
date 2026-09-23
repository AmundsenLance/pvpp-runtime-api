"""Minimal authority-bound native call-through example for Runtime V2.1 / v0.141.

The execution license is issued from a completed canonical decision cycle.  The
example intentionally does not construct an ExecutionLicenseEnvelope by hand.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pvpp_runtime import (
    PVPPRuntime, PVPPRegistry, ActionDefinition, ExecutionBindingRegistry,
    ExecutionBindingIdentity, DomainDefinition, GoverningConfiguration,
    RegimeConfiguration, ConstraintRuleDefinition, GraphInstanceDefinition,
    GraphTransformationDefinition, SigmaOrderDefinition, WorldState,
    PressureFactors, PolicyConstraintProfile, ConstraintObservation,
    PolicyProjectionRecord, RecoveryCorridorProjection,
    CanonicalDecisionCycleRequest, PreliminaryPreservationObject,
    DomainFrame, DomainFrameTarget,
)
from pvpp_runtime.models import ActionProjection

class World:
    def perceive(self, state): return state
    def domain_value(self, state, domain_id): return float(state.powers.get(domain_id, 10.0))
    def project(self, state, action):
        if action.id == "steady":
            return ActionProjection(action.id, WorldState(state.time + 1, {**state.powers, "G": self.domain_value(state, "G") - 1}), True)
        return ActionProjection(action.id, state, True)
    def pressure_factors(self, state, domain_id, baseline_drift):
        return PressureFactors(domain_id, self.domain_value(state, domain_id) - 5.0, baseline_drift)
    def pressure_value(self, domain_id, factors): return 1.0 / max(factors.margin, 0.1)
    def expected_deterioration(self, state, domain_id, baseline_drift, pressure_value, pressure_factors): return baseline_drift
    def constraint_profile(self, state, policy_id, action_ids, regime, governing):
        return PolicyConstraintProfile(policy_id, (ConstraintObservation("soft", False),))
    def compare_constraint_violation_severity(self, a, pa, b, pb, cls): return 0
    def project_policy_record(self, state, policy_id, action_ids):
        horizon = 20.0 if policy_id == "graph:act" else 19.0
        corridor = RecoveryCorridorProjection("G", "continuity", True, True, True, 2.0, horizon)
        return PolicyProjectionRecord(policy_id, True, state, {"G": horizon}, (corridor,), projection_horizon=30.0)

registry = PVPPRegistry()
registry.register_domain(DomainDefinition("G", "governing continuity", 5.0))
for action_id in ("steady", "act"):
    registry.register_action(ActionDefinition(action_id, action_id, ("G",)))
registry.register_governing_configuration(GoverningConfiguration(0.0))
registry.register_regime_configuration(RegimeConfiguration(1, 2, 4, 100, 50, 10))
registry.register_constraint_rule(ConstraintRuleDefinition("soft", "soft"))
registry.register_graph_instance(GraphInstanceDefinition("i", "system", ("G",), "active"))
registry.register_graph_transformation(GraphTransformationDefinition("act", "i", "i", "continuation", ("G",), "reachable", "act", ("continuation",)))
registry.register_sigma_order(SigmaOrderDefinition("graph:act", 20))

runtime = PVPPRuntime(registry, World())
request = CanonicalDecisionCycleRequest(
    preservation_object=PreliminaryPreservationObject("p", "preserve governing continuity"),
    domain_frame=DomainFrame((DomainFrameTarget("G", "continuity"),)),
    required_graph_family_ids=("continuation",),
    materially_required_policy_class_ids=("continuation",),
)
cycle = runtime.evaluate_canonical_decision_cycle(WorldState(0, {"G": 10.0}), request)
license = runtime.build_execution_license_from_cycle(cycle, request.domain_frame)

episode = runtime.instantiate_execution("episode-1", license, entry_sufficient=True, max_steps=1).episode
bindings = ExecutionBindingRegistry(tuple(runtime.registry.actions))
bindings.register(ExecutionBindingIdentity("act-native", "act", "1.0", ("example",)), lambda context: "executed")
authorization = runtime.issue_native_execution_authorization(episode, "act", bindings, decision_cycle_id="cycle-1")
result = runtime.invoke_authorized_native(authorization, bindings)
print(result.status, result.return_value)
