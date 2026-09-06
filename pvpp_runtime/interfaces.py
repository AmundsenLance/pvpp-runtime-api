from __future__ import annotations
from typing import Protocol
from .models import WorldState, ActionDefinition, ActionProjection, ExecutionResult, PolicyProjectionRecord, ProjectionRequest, PressureFactors, PressureDomainResult, PolicyConstraintProfile, FallbackStructuralProfile, ConstraintViolationProfile, ActualPersistentStateEnvelope, Layer1TransitionHandoff, Layer1TransitionResult, MemoryRetrievalRequest, MemoryRetrievalPackage, ExpectationStateReference, PostExecutionEpistemicUpdateRequest, PostExecutionEpistemicUpdateResult, CapacityAuthorityRequest, CapacityAuthorityEnvelope, PredictionErrorRequest, PredictionErrorAssessment, PerceivedDecisionState

class WorldAdapter(Protocol):
    def perceive(self, state: WorldState) -> WorldState: ...
    # Optional v0.41 boundary hook. The host, not the runtime, maps opaque
    # canonical Layer 1 actual state into the represented Layer 2 decision state.
    def represented_state_from_actual(self, state: ActualPersistentStateEnvelope) -> WorldState: ...
    # Optional v0.56 typed P_i(t) hook. Preferred for new integrations.
    def perceived_decision_state_from_actual(self, state: ActualPersistentStateEnvelope) -> PerceivedDecisionState: ...
    # Optional v0.43 memory-conditioned perception boundary. Raw M_i(t) is not
    # passed here; the host receives only current retrieval R^M_i(t,q) plus K_i(t).
    def represented_state_from_perception_inputs(self, state: ActualPersistentStateEnvelope, retrieval: MemoryRetrievalPackage, expectation_state: ExpectationStateReference | None) -> WorldState: ...
    # Optional v0.56 typed memory-conditioned P_i(t) hook. Raw M remains excluded.
    def perceived_decision_state_from_perception_inputs(self, state: ActualPersistentStateEnvelope, retrieval: MemoryRetrievalPackage, expectation_state: ExpectationStateReference | None) -> PerceivedDecisionState: ...
    def domain_value(self, state: WorldState, domain_id: str) -> float: ...
    def project(self, state: WorldState, action: ActionDefinition) -> ActionProjection: ...
    # Optional strict Phi/H interface. Hosts supply domain-sensitive f_k semantics;
    # the runtime owns operator ordering and invariant/boundary enforcement.
    def pressure_factors(self, state: WorldState, domain_id: str, baseline_drift: float) -> PressureFactors: ...
    def pressure_value(self, domain_id: str, factors: PressureFactors) -> float: ...
    def expected_deterioration(self, state: WorldState, domain_id: str, baseline_drift: float, pressure_value: float, pressure_factors: PressureFactors) -> float: ...
    # Optional v0.9 policy-level projection. Hosts should implement this when
    # same-period actions cannot be represented safely as sequential project() calls.
    def project_policy(self, state: WorldState, action_ids: tuple[str, ...]) -> ActionProjection: ...
    # Optional authoritative shared policy-conditioned projection Q_t(pi).
    def project_policy_record(self, state: WorldState, policy_id: str, action_ids: tuple[str, ...]) -> PolicyProjectionRecord: ...
    # Optional canonical Constraint System interface over authorized perceived evidence.
    def constraint_profile(self, state: WorldState, policy_id: str, action_ids: tuple[str, ...], regime: str, governing_domain_ids: tuple[str, ...]) -> PolicyConstraintProfile: ...
    # Optional upstream structural classification consumed by recovery-unavailable Sigma.
    def fallback_structure_profile(self, state: WorldState, policy_id: str, action_ids: tuple[str, ...], governing_domain_ids: tuple[str, ...]) -> FallbackStructuralProfile: ...
    # Optional terminal-Sigma comparator for one constraint class. Return -1 if
    # profile_a is less severe, 0 if comparison-equivalent, +1 if more severe.
    # Sigma owns hard -> conditional -> soft precedence; this hook supplies only
    # within-class structured severity comparison.
    def compare_constraint_violation_severity(self, policy_a: str, profile_a: ConstraintViolationProfile, policy_b: str, profile_b: ConstraintViolationProfile, constraint_class: str) -> int | None: ...
    def execute(self, state: WorldState, action_id: str) -> ExecutionResult: ...


class PolicyProjectionService(Protocol):
    """Canonical shared Layer-2 projection service; not a decision operator."""
    def project(self, request: ProjectionRequest) -> PolicyProjectionRecord: ...


class Layer1TransitionService(Protocol):
    """Explicit host-owned Layer 1 transition boundary.

    The runtime may call this service only through an explicit host/requested
    transition method. The canonical decision cycle and epsilon never invoke it
    automatically.
    """
    def transition(self, current_state: ActualPersistentStateEnvelope, handoff: Layer1TransitionHandoff) -> Layer1TransitionResult: ...


class MemoryRetrievalService(Protocol):
    """Host-owned cue/context-conditioned retrieval service.

    This service owns reconstruction from retained M_i(t). The runtime validates
    the returned retrieval package but does not implement memory storage or recall.
    """
    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryRetrievalPackage: ...


class EpistemicUpdateService(Protocol):
    """Host-owned post-execution update service for retained memory and K_i(t).

    The service may update M_i, K_i, both, or neither from the realized outcome.
    The runtime validates attribution and temporal continuity only.
    """
    def update(self, request: PostExecutionEpistemicUpdateRequest) -> PostExecutionEpistemicUpdateResult: ...


class CapacityAuthorityService(Protocol):
    """Host-owned derivation of represented shared capacity from actual Layer-1 state.

    The service may interpret host-specific individuals, skills, temporary
    availability, commitments, equipment, liquidity windows, and restoration
    rules. The runtime validates only attribution/time/calendar shape.
    """
    def derive(self, actual_state: ActualPersistentStateEnvelope,
               request: CapacityAuthorityRequest) -> CapacityAuthorityEnvelope: ...


class PredictionErrorService(Protocol):
    """Host/domain-owned typed mismatch classifier.

    It compares the appropriate projected/expected stage with realized outcome.
    The runtime validates type, attribution, and permitted error classes only; it
    does not impose a scalar surprise score or learning formula.
    """
    def evaluate(self, request: PredictionErrorRequest) -> PredictionErrorAssessment: ...
