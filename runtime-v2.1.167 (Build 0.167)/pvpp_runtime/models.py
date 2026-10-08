from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class DomainDefinition:
    id: str
    description: str
    threshold: float
    governing_horizon: float | None = None
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductivePowerDefinition:
    id: str
    domain_id: str
    description: str
    persistent: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductivePowerState:
    power_id: str
    value: float
    executable_value: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AccessOperabilityState:
    """Typed V2 access/control/operability surface for one resource or capability.

    These dimensions are deliberately independent.  The runtime carries and
    validates their representation; it does not infer that possession,
    availability, permission, control, or operability implies any other
    dimension or establishes PP by itself.
    """
    resource_id: str
    observed_time: float
    possessed: bool | None = None
    available: bool | None = None
    permitted: bool | None = None
    controlled: bool | None = None
    operable: bool | None = None
    conditions: Mapping[str, Any] = field(default_factory=dict)
    provenance_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AccessOperabilityValidationAssessment:
    valid: bool
    resource_id: str
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductiveConfigurationState:
    """Non-scalar V2 carrier for configuration-dependent productive capability.

    ``component_ids`` identifies represented components and ``dependency_ids``
    identifies represented dependencies.  ``jointly_feasible`` is an optional
    domain-supplied fact, not a runtime-derived aggregate PP score.
    """
    configuration_id: str
    component_ids: tuple[str, ...]
    dependency_ids: tuple[str, ...] = ()
    jointly_feasible: bool | None = None
    evidence_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductiveConfigurationValidationAssessment:
    valid: bool
    configuration_id: str
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecoveryResourceState:
    """V2 carrier separating reserve, recovery capability, and reachability.

    ``reserve`` is an opaque domain-owned stored-value/resource observation.
    ``recovery_capable`` records whether a represented recovery mechanism is
    capable under its stated conditions. ``currently_reachable`` is a separate
    decision-time reachability fact. No field implies either of the others.
    """
    recovery_id: str
    observed_time: float
    reserve: Any = None
    recovery_capable: bool | None = None
    currently_reachable: bool | None = None
    prerequisite_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryResourceValidationAssessment:
    valid: bool
    recovery_id: str
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class QualifiedUnitState:
    """Neutral V2 identity/nesting carrier for a modeled unit.

    Registration and nesting are descriptive. ``productive_role_qualified``
    may be true only when explicit qualification evidence is supplied; the
    runtime never infers collective productive status from membership, nesting,
    possession, or an entity-level state reference.
    """
    unit_id: str
    unit_type: str
    member_ids: tuple[str, ...] = ()
    parent_unit_id: str | None = None
    boundary_id: str | None = None
    entity_state_id: str | None = None
    productive_role_qualified: bool = False
    qualification_evidence_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QualifiedUnitValidationAssessment:
    valid: bool
    unit_id: str
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionBindingIdentity:
    """Identity/provenance for a host callable bound to a registered action.

    This record grants no governance authority.  It identifies an invocation target
    that may only be resolved after the canonical decision path has licensed the
    corresponding action.
    """
    binding_id: str
    action_id: str
    implementation_version: str
    provenance_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NativeExecutionAuthorization:
    """Single-use runtime-issued authority for one native callable attempt.

    The immutable public record is descriptive; runtime-private ledger state is
    controlling. Reconstructing matching field values does not create authority.
    """
    authorization_id: str
    episode_id: str
    decision_cycle_id: str
    selected_policy_id: str
    action_id: str
    binding_id: str
    binding_implementation_version: str
    configuration_id: str | None
    attempt: int
    issued_sequence: int
    status: str = "issued"
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionContext:
    """Runtime-owned identity and correlation envelope for one execution attempt.

    No callable is invoked merely by constructing this object.
    """
    execution_id: str
    action_id: str
    binding_id: str
    decision_cycle_id: str
    attempt: int = 1
    correlation_id: str | None = None
    configuration_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionBindingAssessment:
    valid: bool
    binding_id: str
    action_id: str
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionDefinition:
    id: str
    description: str
    domains: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorldState:
    time: float
    powers: Mapping[str, ProductivePowerState]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def power_value(self, power_id: str) -> float:
        return float(self.powers[power_id].value)


@dataclass(frozen=True)
class ProjectionCausalStateInput:
    """One explicitly represented causal input licensed for policy projection.

    The runtime preserves identity, provenance, and decision-time availability only.
    ``value`` remains domain/host-owned and is never converted into utility, rank,
    feasibility, or confidence by the runtime.
    """
    input_id: str
    kind: str
    value: Any
    license_basis: str
    represented_time: float
    source_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectionInputLicenseAssessment:
    valid: bool
    licensed_input_ids: tuple[str, ...] = ()
    required_input_ids: tuple[str, ...] = ()
    missing_required_input_ids: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectionModelAuthority:
    """Explicit authority for the predictive model used by one canonical Q call.

    The runtime validates identity/version/configuration/horizon provenance only.
    It does not interpret model parameters, compare model quality, select models,
    or derive L_P(t).
    """
    model_id: str
    model_version: str
    configuration_id: str
    parameter_set_id: str
    license_basis: str
    licensed_projection_horizon: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectionModelAuthorityAssessment:
    valid: bool
    model_id: str = ""
    model_version: str = ""
    configuration_id: str = ""
    parameter_set_id: str = ""
    licensed_projection_horizon: float | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObjectiveTemporalBounds:
    """Application-qualified temporal bounds for one V2.1 objective.

    Fields are optional because the owner specification requires only material
    time qualification. They remain application/domain facts, not runtime
    deadlines or scheduling instructions.
    """
    start: float | None = None
    deadline: float | None = None
    horizon: float | None = None
    expiration: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectiveRelation:
    """Declared relation among qualified objectives; never a ranking rule."""
    related_objective_id: str
    relation: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QualifiedObjectiveRecord:
    """Qualified V2.1 objective record o_k.

    This record represents purpose only. It is not utility, viability, PP/PPP,
    authority to execute, a policy ranking, or a Layer-2 operator.
    """
    id: str
    content: Any
    source: str
    scope: Any
    status: str = "active"
    temporal_bounds: ObjectiveTemporalBounds | None = None
    relations: tuple[ObjectiveRelation, ...] = ()
    authority: Any = None
    version: str = "1"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectiveSet:
    """Adjacent typed objective input O_i(t) for one actor and decision time.

    Only currently applicable active objectives belong in this set. Historical,
    suspended, completed, abandoned, and expired objectives may remain in memory
    or history but are not active members of O_i(t).
    """
    actor_id: str
    time: float
    objectives: tuple[QualifiedObjectiveRecord, ...] = ()
    objective_set_id: str = ""
    version: str = "1"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectiveSetValidationAssessment:
    valid: bool
    actor_id: str
    objective_set_id: str = ""
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObjectiveResponsivenessRecord:
    """Application-owned descriptive relation Resp(pi,o).

    The framework owns only the four relation labels.  Evidence and causal
    semantics remain application-owned.  This object is never a gate, ranking,
    authorization, adequacy result, viability result, or selection signal.
    """
    policy_id: str
    objective_id: str
    relation: str
    evidence: Any = None
    provenance: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectiveResponsivenessAssessment:
    valid: bool
    records: tuple[ObjectiveResponsivenessRecord, ...] = ()
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObjectiveDiscoveryHint:
    """Bounded application hint for objective-relevant discovery/representation.

    Hints may point only at already registered structural objects or carry an
    application retrieval cue.  They do not admit Graph structure, create PP,
    establish reachability, confer information-use authority, or rank policies.
    """
    objective_id: str
    graph_transformation_ids: tuple[str, ...] = ()
    graph_instance_ids: tuple[str, ...] = ()
    retrieval_cues: tuple[Any, ...] = ()
    provenance: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectiveDiscoveryAssessment:
    valid: bool
    objective_set_id: str = ""
    admitted_hint_count: int = 0
    referenced_transformation_ids: tuple[str, ...] = ()
    referenced_instance_ids: tuple[str, ...] = ()
    retrieval_cues: tuple[Any, ...] = ()
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PerceivedDecisionState:
    """Typed perception/decision-state interface P_i(t).

    PPP is only the perceived productive-capability component. SPV-hat, PVS,
    X-hat, current retrieval, K, confidence, and uncertainty remain distinct
    optional interfaces. ``represented_state`` is the existing projection-
    compatible runtime payload and is not a new canonical state component.
    """
    actor_id: str
    state_id: str
    time: float
    represented_state: "WorldState"
    ppp: Any
    spv_hat: Any = None
    pvs: Any = None
    x_hat: Any = None
    retrieval: "MemoryRetrievalPackage | None" = None
    expectation_state: "ExpectationStateReference | None" = None
    confidence: Any = None
    uncertainty: Any = None
    projection_causal_inputs: tuple["ProjectionCausalStateInput", ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PerceivedDecisionStateValidationAssessment:
    valid: bool
    actor_id: str
    state_id: str
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActualPersistentStateEnvelope:
    """Opaque host-owned Layer 1 actual persistent state crosswalk.

    The outer structure mirrors the canonical crosswalk
    ``S_i(t) = [PP_i(t), SPV_i(t), AVS_i(t), X_i(t)]``. The runtime does not
    define, scalarize, normalize, or mutate the inner semantics of those four
    components. They remain owned by the Canonical State Object and Layer 1.
    """
    actor_id: str
    state_id: str
    time: float
    pp: Any
    spv: Any
    avs: Any
    context: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransitionRelevantStateBasis:
    """V2.1 host declaration of prospective transition-relevant state sufficiency.

    The declaration identifies the represented current-state surfaces and the
    admissible context for a modeled purpose.  It is not a new state primitive
    and does not import historical event records into live state.
    """
    basis_id: str
    actor_id: str
    state_id: str
    modeled_purpose: str
    admissible_context_id: str
    material_state_surface_ids: tuple[str, ...] = ()
    authoritative_reference_ids: tuple[str, ...] = ()
    source_version_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    host_validated_complete: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransitionRelevantStateSufficiencyAssessment:
    sufficient: bool
    basis_id: str
    actor_id: str
    state_id: str
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransitionRelevantStatePairAssessment:
    """Paired hostile-test result for the V2.1 same-state/context invariant."""
    consistent: bool
    left_basis_id: str
    right_basis_id: str
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Layer1TransitionResult:
    """Host-returned result of one explicit Layer 1 transition request.

    ``next_state`` is host-owned actual persistent state. The runtime validates
    identity, monotonic time, and transition attribution only; it does not
    derive SPV/AVS/PP semantics or perform state mutation itself.
    """
    episode_id: str
    selected_policy_id: str
    prior_state_id: str
    next_state: ActualPersistentStateEnvelope
    transition_applied: bool
    invariant_checks: Mapping[str, bool] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Layer1TransitionValidationAssessment:
    valid: bool
    actor_id: str
    prior_state_id: str
    next_state_id: str | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionTransitionProvenance:
    """Cycle-local provenance from epsilon authority through Layer-1 transition.

    This record is an audit carrier only. It does not mutate state, persist across
    runtime instances, or authorize a later decision. A host may explicitly pass
    it into the next integrated cycle to prove that the supplied starting state is
    the validated result of the prior epsilon -> handoff -> Layer-1 chain.
    """
    actor_id: str
    episode_id: str
    selected_policy_id: str
    licensed_action_ids: tuple[str, ...]
    mandatory_recovery_action_ids: tuple[str, ...]
    execution_status: str
    execution_path: tuple[str, ...]
    prior_state_id: str
    prior_state_time: float
    next_state_id: str
    next_state_time: float
    transition_applied: bool
    realized_pv_evidence_signature: str | None = None
    execution_information_signature: str | None = None
    return_upstream: bool | None = None


@dataclass(frozen=True)
class ExecutionTransitionProvenanceAssessment:
    valid: bool
    actor_id: str
    episode_id: str | None = None
    prior_state_id: str | None = None
    next_state_id: str | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryStateReference:
    """Opaque host-owned retained-memory reference M_i(t).

    The runtime does not inspect, partition, consolidate, decay, or rewrite the
    retained memory payload. This object exists only to preserve identity,
    attribution, and time at the memory/retrieval interface.
    """
    actor_id: str
    memory_state_id: str
    time: float
    payload: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalQualityMetadata:
    """Object-local information-quality markers for one retrieval package.

    No field is treated as a global confidence scalar and no numeric scale is
    imposed by the runtime. Hosts may use domain-specific representations.
    """
    confidence: Any = None
    source_basis: Any = None
    completeness: Any = None
    distortion_risk: Any = None
    freshness: Any = None
    corroboration: Any = None
    relevance_scope: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InformationTemporalProvenance:
    """Material V2.1 temporal provenance for an information object.

    valid_time describes when the content applied in the modeled world.
    record_or_knowledge_time describes when the governed system observed,
    learned, recorded, or accepted it.  Either may remain absent when the
    distinction is immaterial to the application.
    """
    valid_time: Any = None
    record_or_knowledge_time: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InformationGovernanceMetadata:
    """V2.1 governance qualifiers carried with one retrieval.

    Quality/confidence, source authority, and applicability/permitted use are
    intentionally separate.  The runtime preserves and validates these
    qualifiers but does not infer domain authority from information quality.
    """
    source_authority: Any = None
    applicability_scope: Any = None
    permitted_use_scope: Any = None
    authorized_surfaces: tuple[str, ...] = ()
    disposition: str = "current"
    supersedes_or_superseded_by: Any = None
    temporal_provenance: InformationTemporalProvenance | None = None
    source_version: Any = None
    provenance: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InformationGovernanceAssessment:
    valid: bool
    disposition: str = ""
    usable_as_current_positive_evidence: bool = False
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryRetrievalRequest:
    """Cue/context-conditioned request for current retrieval R^M_i(t,q)."""
    actor_id: str
    memory_state: MemoryStateReference
    query: Any = None
    context: Any = None
    governing_concerns: tuple[str, ...] = ()
    current_time: float | None = None
    request_trace: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryRetrievalPackage:
    """Current reconstructed retrieval output, distinct from stored M_i(t)."""
    actor_id: str
    retrieval_id: str
    memory_state_id: str
    time: float
    content: Any
    quality: RetrievalQualityMetadata
    query_trace: Any = None
    source_trace: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()
    governance: InformationGovernanceMetadata | None = None


@dataclass(frozen=True)
class TransferHistoryEvent:
    """One V2.1 PV/PP-relevant event record beneath retained memory.

    The event is an audit/event substrate, not memory, expectation, current PP,
    current transition-relevant state, or execution authority. Domain payloads
    remain host-owned and non-scalar.
    """
    event_id: str
    actor_id: str
    participants: tuple[str, ...] = ()
    interaction_id: str | None = None
    sequence_index: int | None = None
    transfer_type: str | None = None
    signal_or_claim: Any = None
    projected_pv: Any = None
    projected_pp_effect: Any = None
    realized_pv: Any = None
    revealed_pp_effect: Any = None
    surrendered_pv: Any = None
    domain_effects: Mapping[str, Any] = field(default_factory=dict)
    commitment_effect: Any = None
    interpretation: Any = None
    memory_status: Any = None
    expectation_update: Any = None
    quality_markers: Any = None
    temporal_provenance: InformationTemporalProvenance | None = None
    provenance: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransferHistoryReference:
    """Opaque host-owned identity for an ordered transfer-history substrate."""
    actor_id: str
    transfer_history_id: str
    time: float
    version: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransferHistoryPackage:
    """Host-returned append/result package for one or more transfer events."""
    actor_id: str
    prior_history: TransferHistoryReference | None
    next_history: TransferHistoryReference
    events: tuple[TransferHistoryEvent, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransferHistoryValidationAssessment:
    valid: bool
    actor_id: str
    transfer_history_id: str | None = None
    event_ids: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExpectationStateReference:
    """Opaque generalized expectation-state reference K_i(t), distinct from memory."""
    actor_id: str
    expectation_state_id: str
    time: float
    payload: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PredictionErrorComponent:
    """One typed mismatch class; payload remains host/domain-defined, not scalarized."""
    error_class: str
    expected: Any = None
    realized: Any = None
    material: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PredictionErrorRequest:
    """Realized-outcome comparison request after terminal epsilon + validated Layer 1."""
    actor_id: str
    episode_id: str
    selected_policy_id: str
    prior_actual_state_id: str
    next_actual_state_id: str
    next_actual_time: float
    execution_status: str
    prior_expectation_state: ExpectationStateReference | None = None
    selected_projection_record: PolicyProjectionRecord | None = None
    execution_path: tuple[str, ...] = ()
    realized_pv_bundles: tuple[Mapping[str, Any], ...] = ()
    execution_information: tuple[Mapping[str, Any], ...] = ()
    return_upstream: bool = False
    transition_notes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_transition_provenance: ExecutionTransitionProvenance | None = None


@dataclass(frozen=True)
class PredictionErrorAssessment:
    actor_id: str
    episode_id: str
    selected_policy_id: str
    components: tuple[PredictionErrorComponent, ...] = ()
    material_mismatch: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PredictionErrorValidationAssessment:
    valid: bool
    actor_id: str
    episode_id: str
    selected_policy_id: str
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PostExecutionEpistemicUpdateRequest:
    """Typed outcome handoff for host-owned M/K update after realized execution.

    The runtime routes realized evidence but does not decide what is memorable,
    how memory changes, or how expectation learning is computed.
    """
    actor_id: str
    episode_id: str
    selected_policy_id: str
    execution_status: str
    prior_actual_state_id: str
    next_actual_state_id: str
    next_actual_time: float
    prior_memory_state: MemoryStateReference
    prior_expectation_state: ExpectationStateReference | None = None
    execution_path: tuple[str, ...] = ()
    realized_pv_bundles: tuple[Mapping[str, Any], ...] = ()
    execution_information: tuple[Mapping[str, Any], ...] = ()
    return_upstream: bool = False
    transition_notes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    prediction_error: PredictionErrorAssessment | None = None
    execution_transition_provenance: ExecutionTransitionProvenance | None = None


@dataclass(frozen=True)
class PostExecutionEpistemicUpdateResult:
    """Host-returned references after optional memory and/or expectation update."""
    actor_id: str
    episode_id: str
    next_memory_state: MemoryStateReference
    next_expectation_state: ExpectationStateReference | None = None
    memory_updated: bool = False
    expectation_updated: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EpistemicUpdateValidationAssessment:
    valid: bool
    actor_id: str
    episode_id: str
    memory_state_id: str | None = None
    expectation_state_id: str | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryConditionedCycleSnapshot:
    """Perception-side integration record for one memory-conditioned cycle."""
    actual_state: ActualPersistentStateEnvelope
    memory_state: MemoryStateReference
    retrieval: MemoryRetrievalPackage
    expectation_state: ExpectationStateReference | None
    represented_state: "WorldState"
    notes: tuple[str, ...] = ()
    perceived_decision_state: PerceivedDecisionState | None = None


@dataclass(frozen=True)
class MemoryConditionedIntegratedCycleResult:
    """One explicit cycle spanning retrieval, decision, optional execution and M/K update."""
    initial_actual_state_id: str
    initial_memory_state_id: str
    initial_expectation_state_id: str | None
    perception_snapshot: MemoryConditionedCycleSnapshot
    decision: "CanonicalDecisionCycleAssessment"
    execution_license: "ExecutionLicenseEnvelope | None" = None
    epsilon_result: "EpsilonStepResult | None" = None
    handoff: "Layer1TransitionHandoff | None" = None
    transition_result: Layer1TransitionResult | None = None
    transition_validation: Layer1TransitionValidationAssessment | None = None
    epistemic_update_request: PostExecutionEpistemicUpdateRequest | None = None
    epistemic_update_result: PostExecutionEpistemicUpdateResult | None = None
    epistemic_update_validation: EpistemicUpdateValidationAssessment | None = None
    final_actual_state: ActualPersistentStateEnvelope | None = None
    final_memory_state: MemoryStateReference | None = None
    final_expectation_state: ExpectationStateReference | None = None
    status: str = ""
    notes: tuple[str, ...] = ()
    prediction_error_request: PredictionErrorRequest | None = None
    prediction_error: PredictionErrorAssessment | None = None
    prediction_error_validation: PredictionErrorValidationAssessment | None = None


@dataclass(frozen=True)
class MemoryConditionedCycleDirective:
    """One host-authored finite-cycle directive with explicit retrieval cue/context."""
    request: "CanonicalDecisionCycleRequest"
    query: Any = None
    retrieval_context: Any = None
    governing_concerns: tuple[str, ...] = ()
    request_trace: Mapping[str, Any] = field(default_factory=dict)
    execute: bool = False
    update_epistemic_state: bool = False
    episode_id: str = "memory-conditioned-cycle"
    max_execution_steps: int = 1
    execution_observations: tuple["ExecutionObservation", ...] = ()
    expected_actual_state_id: str | None = None
    expected_memory_state_id: str | None = None
    expected_expectation_state_id: str | None = None
    label: str = ""




@dataclass(frozen=True)
class CrossObjectExecutionIdentityAssessment:
    """Testing/integration-only audit of identity continuity across post-selection artifacts."""
    valid: bool
    actor_id: str
    episode_id: str
    selected_policy_id: str
    licensed_action_ids: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntegratedCycleLifecycleIntegrityAssessment:
    """Testing/integration-only audit of lifecycle-shaped artifact continuity.

    The assessment does not create execution authority or infer state semantics.
    It checks that an integrated cycle's status is consistent with which artifacts
    exist and with the terminal/nonterminal posture already represented by epsilon.
    """
    valid: bool
    status: str
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class MemoryConditionedCycleLedgerEntry:
    cycle_index: int
    label: str
    actual_state_id_before: str
    memory_state_id_before: str
    expectation_state_id_before: str | None
    retrieval_id: str
    decision_status: str
    selected_policy_id: str | None = None
    epsilon_status: str | None = None
    transition_applied: bool = False
    memory_updated: bool = False
    expectation_updated: bool = False
    actual_state_id_after: str | None = None
    memory_state_id_after: str | None = None
    expectation_state_id_after: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryConditionedCycleSequenceAssessment:
    status: str
    requested_cycle_count: int
    completed_cycle_count: int
    ledger: tuple[MemoryConditionedCycleLedgerEntry, ...]
    final_actual_state: ActualPersistentStateEnvelope
    final_memory_state: MemoryStateReference
    final_expectation_state: ExpectationStateReference | None = None
    invariant_violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CanonicalCycleSnapshot:
    """One host-supplied pair of Layer 1 actual state and Layer 2 represented state.

    The runtime validates identity/time alignment but does not derive perception
    from the opaque actual-state components.
    """
    actual_state: ActualPersistentStateEnvelope
    represented_state: "WorldState"
    notes: tuple[str, ...] = ()
    perceived_decision_state: PerceivedDecisionState | None = None
    objective_set: ObjectiveSet | None = None


@dataclass(frozen=True)
class CanonicalIntegratedCycleResult:
    """One explicit end-to-end runtime pass across the Layer 1 / Layer 2 boundary.

    The decision cycle remains host-invoked and stop-safe. epsilon and Layer 1
    transition occur only when explicitly requested by this integration method.
    """
    initial_actual_state_id: str
    decision: "CanonicalDecisionCycleAssessment"
    execution_license: "ExecutionLicenseEnvelope | None" = None
    epsilon_result: "EpsilonStepResult | None" = None
    handoff: "Layer1TransitionHandoff | None" = None
    transition_result: Layer1TransitionResult | None = None
    transition_validation: Layer1TransitionValidationAssessment | None = None
    final_actual_state: ActualPersistentStateEnvelope | None = None
    status: str = ""
    notes: tuple[str, ...] = ()
    prior_transition_provenance_validation: ExecutionTransitionProvenanceAssessment | None = None
    transition_provenance: ExecutionTransitionProvenance | None = None


@dataclass(frozen=True)
class CanonicalCycleDirective:
    """One host-authored instruction in a finite multi-cycle stress sequence.

    The runtime does not manufacture directives from prior outcomes. In
    particular, regime hysteresis input remains whatever the host explicitly
    places inside ``request.previous_regime``.
    """
    request: "CanonicalDecisionCycleRequest"
    execute: bool = False
    episode_id: str = "canonical-cycle"
    max_execution_steps: int = 1
    execution_observations: tuple["ExecutionObservation", ...] = ()
    expected_initial_state_id: str | None = None
    label: str = ""


@dataclass(frozen=True)
class CanonicalCycleLedgerEntry:
    """Compact trace-ledger row for one completed host directive."""
    cycle_index: int
    label: str
    initial_state_id: str
    initial_state_time: float
    decision_status: str
    stopped_at: str
    regime: str | None = None
    governing_domain_ids: tuple[str, ...] = ()
    selected_policy_id: str | None = None
    selection_mode: str | None = None
    epsilon_status: str | None = None
    return_upstream: bool | None = None
    transition_applied: bool = False
    final_state_id: str | None = None
    final_state_time: float | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CanonicalCycleSequenceAssessment:
    """Result of a finite host-supplied sequence of canonical cycle directives."""
    status: str
    requested_cycle_count: int
    completed_cycle_count: int
    ledger: tuple[CanonicalCycleLedgerEntry, ...]
    final_actual_state: ActualPersistentStateEnvelope
    invariant_violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PressureFactors:
    """Domain-local inputs to the host-authoritative Phi mapping f_k."""
    domain_id: str
    margin: float
    local_trajectory: float
    discontinuity: float = 0.0
    persistence: float = 0.0
    propagation: float = 0.0
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PressureDomainResult:
    domain_id: str
    factors: PressureFactors
    pressure: float
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PressureFieldAssessment:
    domain_results: tuple[PressureDomainResult, ...]
    notes: tuple[str, ...] = ()

    @property
    def pressures(self) -> Mapping[str, float]:
        return {r.domain_id:r.pressure for r in self.domain_results}


@dataclass(frozen=True, slots=True)
class PressureInvariantAssessment:
    domain_id: str
    valid: bool
    tested_margins: tuple[float, ...]
    pressures: tuple[float, ...]
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HorizonConfiguration:
    """Architecture-visible numerical stabilizer for canonical baseline H."""
    epsilon_deterioration: float = 1e-12


@dataclass(frozen=True, slots=True)
class HorizonDomainResult:
    domain_id: str
    margin: float
    expected_deterioration: float
    horizon: float


@dataclass(frozen=True, slots=True)
class HorizonAssessment:
    domain_results: tuple[HorizonDomainResult, ...]
    notes: tuple[str, ...] = ()

    @property
    def horizons(self) -> Mapping[str, float]:
        return {r.domain_id:r.horizon for r in self.domain_results}


@dataclass(frozen=True)
class DomainAssessment:
    domain_id: str
    perceived_value: float
    pressure: float
    horizon: float
    governing: bool
    threshold: float


@dataclass(frozen=True)
class ActionProjection:
    action_id: str
    next_state: WorldState
    feasible: bool
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionEvaluation:
    action_id: str
    feasible: bool
    adequate: bool
    projected_horizons: Mapping[str, float]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecoveryAdequacyAssessment:
    status: str
    jointly_feasible: bool | None = None
    active_corridors: tuple[str, ...] = ()
    infeasible_corridor_sets: tuple[tuple[str, ...], ...] = ()
    schedule: tuple["ScheduledRecoveryStep", ...] = ()
    deadline_slack: Mapping[str, float] = field(default_factory=dict)
    bottleneck_resources: Mapping[tuple[str, ...], tuple[str, ...]] = field(default_factory=dict)
    residual_capacity: Mapping[int, Mapping[str, float]] = field(default_factory=dict)
    infeasible_sets_complete: bool = True
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SelectedPolicy:
    """Prototype decision surface: one or more actions intended for the same host period."""
    action_ids: tuple[str, ...]
    period_offset: int = 0
    recovery_constrained: bool = False
    required_action_ids: tuple[str, ...] = ()
    supplemental_action_ids: tuple[str, ...] = ()
    residual_capacity: Mapping[str, float] = field(default_factory=dict)
    notes: tuple[str, ...] = ()




@dataclass(frozen=True)
class DiscretionarySelectionAssessment:
    """Prototype residual-capacity selection surface after required recovery is fixed."""
    status: str
    eligible_action_ids: tuple[str, ...] = ()
    maximal_feasible_sets: tuple[tuple[str, ...], ...] = ()
    selected_action_ids: tuple[str, ...] = ()
    residual_capacity_before: Mapping[str, float] = field(default_factory=dict)
    residual_capacity_after: Mapping[str, float] = field(default_factory=dict)
    notes: tuple[str, ...] = ()




@dataclass(frozen=True)
class PreliminaryPreservationObject:
    id: str
    function_statement: str
    mechanism_independence_note: str = ""
    mechanism_identity_exception: str = ""
    rationale: str = ""


@dataclass(frozen=True)
class GraphInstanceDefinition:
    id: str
    instance_type: str
    domain_ids: tuple[str, ...]
    current_state: str
    roles: tuple[str, ...] = ()
    reachability_relevance: str = ""
    composition_relevance: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphTransformationDefinition:
    id: str
    source_instance_id: str
    destination_instance_id: str
    family: str
    affected_domain_ids: tuple[str, ...]
    reachability_status: str
    action_id: str
    policy_class_ids: tuple[str, ...] = ()
    enabling_conditions: tuple[str, ...] = ()
    blocking_conditions: tuple[str, ...] = ()
    relevant_horizon: float | None = None
    irreversible: bool = False
    structurally_required: bool = False
    uncertainty_note: str = ""
    structural_effect: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    # v0.57 explicit Graph conditional-pass materiality marker. This is not
    # inferred by the runtime because "only viable" is host/domain structural knowledge.
    only_viable_path_candidate: bool = False


@dataclass(frozen=True)
class GraphCompositionDefinition:
    id: str
    transformation_ids: tuple[str, ...]
    represented_family: str
    affected_domain_ids: tuple[str, ...]
    policy_class_ids: tuple[str, ...] = ()
    recovery_relevance: str = ""
    distinctness_justification: str = ""
    structurally_required: bool = False


@dataclass(frozen=True)
class GraphConstructionConfig:
    max_seeds: int = 64


@dataclass(frozen=True)
class GraphConstructionAssessment:
    status: str
    preservation_object_id: str
    regime: str
    governing_domain_ids: tuple[str, ...]
    validated_transformation_ids: tuple[str, ...] = ()
    excluded_transformation_ids: tuple[str, ...] = ()
    uncertain_transformation_ids: tuple[str, ...] = ()
    composition_ids: tuple[str, ...] = ()
    represented_families: tuple[str, ...] = ()
    missing_required_families: tuple[str, ...] = ()
    seed_ids: tuple[str, ...] = ()
    failure_codes: tuple[str, ...] = ()
    policy_seeds: tuple["PolicySeedDefinition", ...] = ()
    notes: tuple[str, ...] = ()
    # v0.39 composition-sufficiency diagnostics. Required path classes remain
    # explicit upstream declarations; Graph does not infer staging materiality.
    invalid_composition_ids: tuple[str, ...] = ()
    missing_required_path_class_ids: tuple[str, ...] = ()
    open_uncertainty_markers: tuple[str, ...] = ()
    uncertain_family_presence_ids: tuple[str, ...] = ()
    uncertain_only_viable_path_ids: tuple[str, ...] = ()
    safe_to_handoff: bool = False


@dataclass(frozen=True)
class PolicySeedDefinition:
    """Bounded graph-layer seed visible to Pi; not a projected or ranked policy."""
    id: str
    action_ids: tuple[str, ...]
    family: str
    affected_domain_ids: tuple[str, ...] = ()
    policy_class_ids: tuple[str, ...] = ()
    structurally_required: bool = False
    coherent: bool = True
    visible: bool = True
    metadata: Mapping[str, Any] | None = None
    source_family: str = ""
    path_type: str = ""
    source_ids: tuple[str, ...] = ()
    structural_distinctness_note: str = ""


@dataclass(frozen=True)
class PiConstructionConfig:
    """Architecture-visible boundedness controls for Pi construction."""
    max_candidates: int = 64


@dataclass(frozen=True)
class PiConstructionAssessment:
    status: str
    regime: str
    governing_domain_ids: tuple[str, ...]
    visible_seed_ids: tuple[str, ...] = ()
    eligible_seed_ids: tuple[str, ...] = ()
    emitted_candidate_ids: tuple[str, ...] = ()
    suppressed_seed_ids: tuple[str, ...] = ()
    malformed_seed_ids: tuple[str, ...] = ()
    duplicate_seed_ids: tuple[str, ...] = ()
    overflow_count: int = 0
    policy_space: "CandidatePolicySpace | None" = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidatePolicySet:
    """First-class candidate policy for one represented host period.

    ``policy_class_ids`` identifies materially distinct policy classes represented
    by this candidate for Pi-completeness accounting. Class membership is
    structural coverage metadata only; it never ranks candidates.
    """
    id: str
    action_ids: tuple[str, ...]
    required_action_ids: tuple[str, ...] = ()
    discretionary_action_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy_class_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidatePolicySpace:
    """Bounded Pi output plus an explicit completeness-validation basis.

    ``materially_required_class_ids`` is supplied by the upstream policy-space
    construction/graph layer. It is the set of structurally reachable, feasible,
    materially relevant policy classes that must be represented for this
    decision problem. The runtime does not invent omitted classes.
    """
    candidates: tuple[CandidatePolicySet, ...]
    materially_required_class_ids: tuple[str, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EpistemicSubstrateQualification:
    """Explicit supporting-protocol status for the Graph -> Pi substrate."""
    status: str
    basis: str
    warning_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class QualifiedPiCompletenessAssessment:
    """Supporting qualification of local Pi completeness by substrate integrity."""
    status: str
    local_completeness: "PiCompletenessAssessment"
    substrate_qualification: EpistemicSubstrateQualification
    local_pi_complete: bool
    unqualified_structural_pass: bool
    downstream_full_confidence_licensed: bool
    layered_attribution: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PiCompletenessAssessment:
    status: str
    complete: bool
    required_class_ids: tuple[str, ...] = ()
    represented_class_ids: tuple[str, ...] = ()
    missing_class_ids: tuple[str, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()



@dataclass(frozen=True)
class GoverningConfiguration:
    """Architecture-visible horizon proximity tolerance for canonical G."""
    epsilon_h: float = 0.0


@dataclass(frozen=True)
class RecoveryNecessityDefinition:
    """Explicit upstream structural fact: support is strictly recovery-necessary for target."""
    id: str
    support_domain_id: str
    target_domain_id: str
    basis: str = "registered_recovery_necessity"
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GoverningAssessment:
    """Typed output of the Governing Domain Identification Operator G."""
    seed_domain_ids: tuple[str, ...]
    governing_domain_ids: tuple[str, ...]
    added_by_dependency_ids: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    provenance: Mapping[str, tuple[str, str]] = field(default_factory=dict)
    epsilon_h: float = 0.0
    minimum_horizon: float = float("inf")
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RegimeConfiguration:
    """Architecture-visible deterministic thresholds for the canonical regime map."""
    tau_h_existential: float
    tau_h_survival: float
    tau_h_stabilization: float
    tau_phi_existential: float
    tau_phi_survival: float
    tau_phi_stabilization: float
    tau_m_survival: int = 2
    tau_m_stabilization: int = 2
    tau_h_mult_survival: float | None = None
    tau_h_mult_stabilization: float | None = None
    delta_h_escalation: float = 0.0
    delta_h_deescalation: float = 0.0


@dataclass(frozen=True)
class PreviousRegimeState:
    """Explicit prior-timestep input for deterministic hysteresis; not runtime persistence."""
    regime: str
    governing_min_horizon: float


@dataclass(frozen=True)
class RegimeAssessment:
    """Typed output of the Regime Classification Operator R."""
    regime: str
    governing_domain_ids: tuple[str, ...]
    governing_min_horizon: float
    governing_max_pressure: float
    governing_multiplicity: int
    contextual_interruption: bool = False
    base_regime: str = "Mission"
    hysteresis_applied: bool = False
    trigger: str = ""
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConstraintRuleDefinition:
    """Registered feasibility rule classified as hard, conditional, or soft."""
    id: str
    constraint_class: str
    conditional_class: str = ""
    description: str = ""
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConstraintObservation:
    """Host-supplied policy/rule observation under authorized perceived evidence.

    Conditional relaxation requires two distinct facts: the active regime permits
    relaxation of the relevant class, and an explicit necessity authorization has
    been established. The runtime does not infer downstream adequacy here.
    """
    rule_id: str
    violated: bool
    active: bool = True
    regime_relaxable: bool = False
    necessity_authorized: bool = False
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PolicyConstraintProfile:
    policy_id: str
    observations: tuple[ConstraintObservation, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConstraintViolationProfile:
    hard_violation_ids: tuple[str, ...] = ()
    conditional_violation_ids: tuple[str, ...] = ()
    relaxed_conditional_violation_ids: tuple[str, ...] = ()
    soft_violation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConstraintAssessment:
    """Explicit Constraints-stage result for one candidate policy."""
    policy_id: str
    feasible: bool
    reasons: tuple[str, ...] = ()
    violation_profile: ConstraintViolationProfile | None = None
    evidence_basis: str = "compatibility_host_feasibility"


@dataclass(frozen=True)
class ConstraintsAssessment:
    status: str
    candidate_results: tuple[ConstraintAssessment, ...] = ()
    feasible_policy_ids: tuple[str, ...] = ()
    infeasible_policy_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class DomainFrameTarget:
    """Explicit pre-Adequacy preservation target for one governing domain.

    The runtime does not infer persistence-bearing function semantics from labels.
    ``function_id`` is an upstream-declared stable identifier for the function being
    preserved. ``basis`` records whether the target is function-anchored or a
    justified non-substitutable mechanism. This is framing metadata, never a score.
    """
    domain_id: str
    function_id: str
    basis: str = "function"
    locked: bool = True
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainFrame:
    """Explicit Domain Framing output consumed by Adequacy.

    A complete frame must cover every current governing domain exactly once.
    Semantic claims about substitutability/reachability are supplied upstream;
    this deterministic gate validates the declared framing contract and does not
    invent substitutes or broaden domains by intuition.
    """
    targets: tuple[DomainFrameTarget, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainFramingAssessment:
    status: str
    valid: bool
    governing_domain_ids: tuple[str, ...] = ()
    framed_domain_ids: tuple[str, ...] = ()
    missing_domain_ids: tuple[str, ...] = ()
    duplicate_domain_ids: tuple[str, ...] = ()
    invalid_target_domain_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class RecoveryCorridorProjection:
    """One Q_t(pi) recovery-corridor fact for a framed domain/function target.

    These facts are supplied by the authoritative shared projection service.
    Adequacy consumes them; it does not infer them from a terminal horizon.
    """
    domain_id: str
    function_id: str
    pre_recovery_viability_preserved: bool
    recovery_capable_region_reached: bool
    joint_sustainment_supported: bool
    recovery_entry_time: float | None = None
    projected_extinction_time: float | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectionInformationQualityClaim:
    """Typed audit metadata for one projected reachability/closure assertion.

    Confidence is deliberately opaque to the runtime: it is trace evidence, not a
    score, utility, probability, feasibility flag, or Sigma ordering input.
    """
    subject_kind: str
    subject_id: str
    basis: str
    confidence: Any
    uncertainty_note: str = ""
    source_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyProjectionRecord:
    """Authoritative shared policy-conditioned projection record Q_t(pi).

    ``projected_horizons`` stores the exact horizon when observed inside the
    licensed projection window. For a right-censored domain it stores the common
    censoring bound ``projection_horizon`` while ``right_censored_domain_ids``
    records that the canonical observation is T^ext > L_P rather than equality.
    Downstream Sigma must preserve that information boundary.
    """
    policy_id: str
    feasible: bool
    terminal_state: WorldState | None = None
    projected_horizons: Mapping[str, float] = field(default_factory=dict)
    recovery_corridors: tuple[RecoveryCorridorProjection, ...] = ()
    closure_annotations: Mapping[str, Any] = field(default_factory=dict)
    reopening_annotations: Mapping[str, Any] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    projection_horizon: float | None = None
    right_censored_domain_ids: tuple[str, ...] = ()
    # v0.36 canonical projection-service trace fields. ``feasible`` remains only
    # for backward compatibility with pre-Constraint-System hosts; canonical
    # projection does not own present-time feasibility.
    state_id: str | None = None
    state_time: float | None = None
    candidate_mode: str = ""
    projected_domain_trajectories: Mapping[str, Any] = field(default_factory=dict)
    reachable_viable: Mapping[str, Any] = field(default_factory=dict)
    information_quality_trace: Mapping[str, Any] = field(default_factory=dict)
    information_quality_claims: tuple[ProjectionInformationQualityClaim, ...] = ()
    model_version: str = ""
    projection_input_trace: Mapping[str, Any] = field(default_factory=dict)
    model_id: str = ""
    model_configuration_id: str = ""
    model_parameter_set_id: str = ""


@dataclass(frozen=True)
class ProjectionRequest:
    """Typed call contract for the shared policy-conditional projection service.

    The runtime supplies represented decision-time state, an explicitly licensed
    policy, a finite projection horizon, and the read-only Graph assessment. The
    service remains stateless/non-selective and returns one authoritative Q_t(pi).
    """
    represented_state: WorldState
    policy_id: str
    action_ids: tuple[str, ...]
    candidate_mode: str
    projection_horizon: float
    graph_assessment: GraphConstructionAssessment | None = None
    state_id: str | None = None
    projection_input_trace: Mapping[str, Any] = field(default_factory=dict)
    perceived_decision_state: PerceivedDecisionState | None = None
    input_license_assessment: ProjectionInputLicenseAssessment | None = None
    model_authority: ProjectionModelAuthority | None = None
    model_authority_assessment: ProjectionModelAuthorityAssessment | None = None


@dataclass(frozen=True)
class ProjectionConsistencyAudit:
    """Audit that downstream consumers received one unchanged authoritative Q record set."""
    policy_ids: tuple[str, ...]
    adequacy_consumed_policy_ids: tuple[str, ...]
    sigma_consumed_policy_ids: tuple[str, ...]
    unchanged_through_adequacy: bool
    unchanged_through_sigma: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CycleArtifactIntegrityAssessment:
    """Implementation-level identity/freshness audit across one completed cycle.

    This is not a sovereign PV-PP operator. It verifies that cycle-local artifacts
    refer to the same state/time, governing structure, candidate set, feasible set,
    and authoritative projection set before execution licensing may rely on them.
    """
    valid: bool
    state_id: str | None = None
    state_time: float | None = None
    candidate_policy_ids: tuple[str, ...] = ()
    feasible_policy_ids: tuple[str, ...] = ()
    projection_policy_ids: tuple[str, ...] = ()
    adequacy_policy_ids: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainAdequacyResult:
    domain_id: str
    function_id: str
    adequate: bool
    pre_recovery_viability_preserved: bool
    recovery_capable_region_reached: bool
    joint_sustainment_supported: bool
    recovery_entry_time: float | None = None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PolicyAdequacyResult:
    policy_id: str
    adequate: bool
    domain_results: tuple[DomainAdequacyResult, ...] = ()
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdequacyAssessment:
    status: str
    policy_results: tuple[PolicyAdequacyResult, ...] = ()
    adequate_policy_ids: tuple[str, ...] = ()
    inadequate_policy_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PolicySetEvaluation:
    policy_id: str
    action_ids: tuple[str, ...]
    feasible: bool
    adequate: bool
    projected_horizons: Mapping[str, float] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
    projection_horizon: float | None = None
    right_censored_domain_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainRelationDefinition:
    """Prototype registered structural relation used to interpret policy consequences.

    relation_type is deliberately narrow in v0.13. The first supported type is
    ``dependency_floor``: the source domain is a prerequisite whose projected
    horizon must remain at or above ``minimum_source_horizon`` before the target
    domain's improvement can count as a structurally admissible policy outcome.
    """
    id: str
    relation_type: str
    source_domain_id: str
    target_domain_id: str
    minimum_source_horizon: float
    description: str = ""


@dataclass(frozen=True)
class DependencyRequirementDefinition:
    """Prototype grouped prerequisite semantics.

    ``mode='all_of'`` means every listed source is required: failure of any
    source makes the target structurally unavailable. ``mode='any_of'`` means
    the listed sources are substitutes: the target becomes structurally
    unavailable only when every source fails. This is an experimental runtime
    representation of dependency structure, not a preference rule.
    """
    id: str
    mode: str
    source_domain_ids: tuple[str, ...]
    target_domain_id: str
    minimum_source_horizon: float
    description: str = ""


@dataclass(frozen=True)
class StructuralPolicyAssessment:
    status: str
    relation_ids: tuple[str, ...] = ()
    excluded_policy_ids: tuple[str, ...] = ()
    surviving_policy_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    # policy -> unavailable domain -> (relation_id, prior unavailable domain or None)
    # Compact predecessor witness; linear in the number of unavailable domains.
    provenance: Mapping[str, Mapping[str, tuple[str, str | None]]] = field(default_factory=dict)
    # policy -> unavailable domain -> immediate registered causes.
    # This preserves converging causal structure without enumerating every full path.
    provenance_causes: Mapping[str, Mapping[str, tuple[tuple[str, str | None], ...]]] = field(default_factory=dict)
    provenance_paths_exhaustive: bool = False
    # policy -> target domain -> requirement id -> failed source domains.
    # For any_of groups, this records all failed substitutes that jointly caused
    # the target to become unavailable.
    requirement_failures: Mapping[str, Mapping[str, Mapping[str, tuple[str, ...]]]] = field(default_factory=dict)

    def provenance_path(self, policy_id: str, domain_id: str) -> tuple[str, ...]:
        """Reconstruct one registered-relation witness path for an exclusion."""
        graph=self.provenance.get(policy_id, {})
        if domain_id not in graph:
            return ()
        path=[]
        seen=set()
        current=domain_id
        while current in graph and current not in seen:
            seen.add(current)
            relation_id,parent=graph[current]
            path.append(relation_id)
            if parent is None:
                break
            current=parent
        path.reverse()
        return tuple(path)

    def immediate_causes(self, policy_id: str, domain_id: str) -> tuple[tuple[str, str | None], ...]:
        """Return all immediate registered causes retained for a converging exclusion."""
        return self.provenance_causes.get(policy_id, {}).get(domain_id, ())


    def requirement_failure_sources(self, policy_id: str, domain_id: str, requirement_id: str) -> tuple[str, ...]:
        """Return failed sources that made one grouped requirement fail."""
        return self.requirement_failures.get(policy_id, {}).get(domain_id, {}).get(requirement_id, ())

@dataclass(frozen=True)
class SigmaOrderDefinition:
    """Explicit state-independent Stage-3 order index for ordinary Sigma.

    This is architecture configuration, not candidate/registration order and not
    a consequence score. Lower index wins only after A1 and A2 are complete.
    """
    policy_id: str
    order_index: int


@dataclass(frozen=True)
class FallbackConfiguration:
    """Initial frozen fallback override parameterization from the V2 addendum.

    alpha_base is a relative margin in (0, 1). The initial V2 freeze uses one
    common coefficient across governing structure classes; splitting by class is
    intentionally deferred until canonical testing requires it.
    """
    alpha_base: float = 0.05


@dataclass(frozen=True)
class FallbackStructuralProfile:
    """Upstream-supplied categorical/ordinal structure for fallback refinement.

    Sigma consumes these facts; it does not infer governing criticality. Stage-2
    fields are categorical sets. Stage-3 fields are explicit ordinal ranks supplied
    by the integration: lower irreversible/spillover ranks are better; higher
    maneuver rank is better. They are not added or weighted.
    """
    policy_id: str
    critical_damage_structure_ids: tuple[str, ...] = ()
    critical_maneuver_structure_ids: tuple[str, ...] = ()
    irreversible_damage_rank: int = 0
    noncritical_maneuver_rank: int = 0
    spillover_damage_rank: int = 0
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SigmaFallbackAssessment:
    """Typed recovery-unavailable fallback result."""
    mode: str
    input_policy_ids: tuple[str, ...]
    maximal_policy_ids: tuple[str, ...]
    stage1_policy_ids: tuple[str, ...]
    stage2_override_policy_id: str | None = None
    stage3_policy_ids: tuple[str, ...] = ()
    selected_policy_id: str | None = None
    selected_order_index: int | None = None
    status: str = ""
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SigmaStageAssessment:
    """One explicit canonical Sigma frontier stage."""
    stage: str
    input_policy_ids: tuple[str, ...]
    domain_ids: tuple[str, ...]
    survivor_policy_ids: tuple[str, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SigmaAssessment:
    """Typed standard-mode Sigma result: A1 governing frontier, then A2 global refinement."""
    mode: str
    stage1: SigmaStageAssessment
    stage2: SigmaStageAssessment
    final_policy_ids: tuple[str, ...]
    selected_policy_id: str | None = None
    selected_order_index: int | None = None
    notes: tuple[str, ...] = ()




@dataclass(frozen=True)
class SigmaTerminalAssessment:
    """Terminal infeasibility Sigma over structured violation profiles.

    Sigma owns class priority (hard -> conditional -> soft) and deterministic
    residual tie resolution. Within-class severity comparison is supplied by the
    integration boundary because canonical authority does not freeze a universal
    severity metric.
    """
    mode: str
    input_policy_ids: tuple[str, ...]
    hard_survivor_policy_ids: tuple[str, ...]
    conditional_survivor_policy_ids: tuple[str, ...]
    soft_survivor_policy_ids: tuple[str, ...]
    final_policy_ids: tuple[str, ...]
    selected_policy_id: str | None = None
    selected_order_index: int | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CanonicalDecisionCycleRequest:
    """Explicit upstream inputs for one host-invoked canonical Layer-2 decision cycle."""
    preservation_object: PreliminaryPreservationObject
    domain_frame: DomainFrame
    required_graph_family_ids: tuple[str, ...] = ()
    required_graph_path_class_ids: tuple[str, ...] = ()
    materially_required_policy_class_ids: tuple[str, ...] = ()
    contextual_interruption: bool = False
    previous_regime: PreviousRegimeState | None = None
    graph_config: GraphConstructionConfig | None = None
    pi_config: PiConstructionConfig | None = None
    # Required when a canonical PolicyProjectionService is attached. Legacy
    # world.project_policy_record() integrations may continue to self-report L_P.
    projection_horizon: float | None = None
    projection_input_trace: Mapping[str, Any] = field(default_factory=dict)
    # Optional represented shared-capacity authority for the current decision.
    # If supplied while active recovery corridors exist, the runtime's exact
    # joint-feasibility engine is authoritative for that active set before
    # ordinary Restoration Adequacy / Sigma may proceed.
    joint_recovery_capacity_calendar: "CapacityCalendar | None" = None
    joint_recovery_diagnostic_mode: str = "witness"
    # Optional model/host declaration of represented causal inputs required by Q.
    # The runtime does not infer these requirements from Graph, policy identity,
    # metadata, or actual Layer-1 state.
    projection_required_causal_input_ids: tuple[str, ...] = ()
    # Optional explicit predictive-model authority. When supplied, Q must echo
    # model/version/configuration/parameter-set identity and the same licensed L_P.
    projection_model_authority: "ProjectionModelAuthority | None" = None


@dataclass(frozen=True)
class CanonicalDecisionCycleAssessment:
    """Typed stop-safe result for one canonical decision cycle through Sigma.

    epsilon is intentionally not invoked here. The host may build an execution
    license only after this result contains a uniquely selected policy.
    """
    status: str
    stopped_at: str
    pipeline_trace: tuple[str, ...]
    pressure_field: PressureFieldAssessment | None = None
    horizon_assessment: HorizonAssessment | None = None
    governing_assessment: GoverningAssessment | None = None
    regime_assessment: RegimeAssessment | None = None
    graph_assessment: GraphConstructionAssessment | None = None
    pi_construction: PiConstructionAssessment | None = None
    pi_completeness: PiCompletenessAssessment | None = None
    constraints: ConstraintsAssessment | None = None
    domain_framing: DomainFramingAssessment | None = None
    adequacy: AdequacyAssessment | None = None
    selection: "PolicySelectionAssessment | None" = None
    projection_records: tuple[PolicyProjectionRecord, ...] = ()
    notes: tuple[str, ...] = ()
    joint_recovery_feasibility: "JointRecoveryFeasibilityAssessment | None" = None
    joint_recovery_execution_binding: "JointRecoveryExecutionBindingAssessment | None" = None
    projection_consistency_audit: "ProjectionConsistencyAudit | None" = None
    projection_input_license_assessment: "ProjectionInputLicenseAssessment | None" = None
    projection_model_authority_assessment: "ProjectionModelAuthorityAssessment | None" = None
    cycle_artifact_integrity: "CycleArtifactIntegrityAssessment | None" = None
    pi_before_joint_recovery_binding: "PiConstructionAssessment | None" = None
    objective_responsiveness: "ObjectiveResponsivenessAssessment | None" = None
    objective_discovery: "ObjectiveDiscoveryAssessment | None" = None


@dataclass(frozen=True)
class PolicySelectionAssessment:
    """Prototype policy-level Sigma surface; comparison may remain unresolved."""
    status: str
    candidates: tuple[CandidatePolicySet, ...] = ()
    evaluations: tuple[PolicySetEvaluation, ...] = ()
    undominated_policy_ids: tuple[str, ...] = ()
    selected_policy_id: str | None = None
    conflicting_domains: tuple[str, ...] = ()
    structural_assessment: StructuralPolicyAssessment | None = None
    pi_completeness: PiCompletenessAssessment | None = None
    domain_framing: DomainFramingAssessment | None = None
    constraints: ConstraintsAssessment | None = None
    adequacy: AdequacyAssessment | None = None
    sigma: SigmaAssessment | None = None
    notes: tuple[str, ...] = ()
    fallback_sigma: "SigmaFallbackAssessment | None" = None
    terminal_sigma: "SigmaTerminalAssessment | None" = None


@dataclass(frozen=True)
class PVPPAssessment:
    state_time: float
    domains: Mapping[str, DomainAssessment]
    governing_domains: tuple[str, ...]
    regime: str
    preservation_targets: tuple[str, ...]
    steady_adequate: bool
    action_evaluations: tuple[ActionEvaluation, ...]
    selected_action: str | None
    pipeline_trace: tuple[str, ...]
    recovery_adequacy: RecoveryAdequacyAssessment | None = None
    selected_policy: SelectedPolicy | None = None
    discretionary_selection: DiscretionarySelectionAssessment | None = None
    policy_selection: PolicySelectionAssessment | None = None
    regime_assessment: RegimeAssessment | None = None
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class RecoveryPlanDefinition:
    id: str
    domain_id: str
    function_id: str
    trigger_action: str
    continuation_actions: tuple[str, ...]
    deadline_offset: float


@dataclass(frozen=True)
class ActiveRecoveryCorridor:
    plan_id: str
    domain_id: str
    function_id: str
    remaining_actions: tuple[str, ...]
    deadline: float
    status: str = "active"


@dataclass(frozen=True)
class ExecutionLicenseEnvelope:
    """Execution-relevant upstream licensing consumed by epsilon.

    This is not a new policy object. It records the already-selected policy and
    the upstream conditions epsilon is forbidden to recompute or repair.

    ``selection_mode`` preserves whether Sigma selected under standard,
    recovery-unavailable fallback, or terminal infeasibility semantics.
    ``entry_authorized`` is the explicit execution-boundary gate. It allows the
    runtime to preserve upstream failure posture without laundering it into a
    generic executable=True flag.
    """
    selected_policy_id: str
    action_ids: tuple[str, ...]
    governing_domain_ids: tuple[str, ...]
    framed_function_ids: tuple[str, ...]
    pi_complete: bool
    constraints_feasible: bool
    framing_valid: bool
    adequacy_sufficient: bool
    notes: tuple[str, ...] = ()
    selection_mode: str = "standard"
    entry_authorized: bool = True
    selected_candidate_action_ids: tuple[str, ...] = ()
    mandatory_recovery_action_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionObservation:
    """Host-supplied execution-side fact bundle for one bounded epsilon step."""
    event_id: str
    continuation_sufficient: bool = True
    completion_sufficient: bool = True
    completed: bool = False
    staged: bool = False
    failed: bool = False
    emergency: bool = False
    material_policy_class_change_required: bool = False
    realized_pv_bundle: Mapping[str, Any] = field(default_factory=dict)
    information: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionTraceNode:
    """Persistent linked trace node: O(1) append, materialized only on demand."""
    event_id: str
    realized_pv_bundle: Mapping[str, Any] = field(default_factory=dict)
    information: Mapping[str, Any] = field(default_factory=dict)
    prior: "ExecutionTraceNode | None" = None


@dataclass(frozen=True)
class ExecutionEpisode:
    """x_exec / E_exec prototype state for bounded realization.

    The selected policy remains the upstream policy; this object is the concrete
    execution episode, not a second executable-policy representation.
    """
    episode_id: str
    license: ExecutionLicenseEnvelope
    max_steps: int
    step_count: int = 0
    entry_sufficient: bool = True
    trace_tail: ExecutionTraceNode | None = None
    active: bool = True


@dataclass(frozen=True)
class EpsilonStepResult:
    """One bounded epsilon realization result.

    ``status`` is ``active`` while execution remains inside the licensed
    corridor, otherwise one of the canonical terminal execution status classes.
    """
    episode: ExecutionEpisode
    status: str
    terminal: bool
    return_upstream: bool
    realized_pv_bundles: tuple[Mapping[str, Any], ...] = ()
    information_events: tuple[Mapping[str, Any], ...] = ()
    execution_path: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Layer1TransitionHandoff:
    """Immutable epsilon -> Layer 1 transition packet.

    This is not a new Layer 2 operator and contains no next-state value. Layer 1 /
    the host remains solely responsible for applying T to actual persistent state.
    """
    episode_id: str
    selected_policy_id: str
    execution_status: str
    execution_path: tuple[str, ...]
    realized_pv_bundles: tuple[Mapping[str, Any], ...]
    execution_information: tuple[Mapping[str, Any], ...]
    return_upstream: bool
    notes: tuple[str, ...] = ()
    licensed_action_ids: tuple[str, ...] = ()
    mandatory_recovery_action_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecoveryActionConfirmation:
    """Host-confirmed realized action used only for runtime recovery bookkeeping.

    ``recovery_plan_id`` is optional when the action maps unambiguously to one
    registered recovery plan/corridor. It is required when inference would depend
    on registration order or another hidden priority.
    """
    action_id: str
    recovery_plan_id: str | None = None


@dataclass(frozen=True)
class Layer1ExecutionCommit:
    """Post-transition confirmation returned by Layer 1 / the host.

    This record does not contain or mutate world state. It merely confirms that
    Layer 1 transition handling has occurred and supplies the realized actions
    that may update runtime-local recovery-path bookkeeping.
    """
    episode_id: str
    committed_state_time: float
    state_transition_applied: bool
    action_confirmations: tuple[RecoveryActionConfirmation, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionBookkeepingAssessment:
    """Result of applying post-Layer-1 confirmations to runtime-local ledgers."""
    episode_id: str
    started_corridor_ids: tuple[str, ...] = ()
    advanced_corridor_ids: tuple[str, ...] = ()
    completed_corridor_ids: tuple[str, ...] = ()
    ignored_action_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionResult:
    """Legacy compatibility result for pre-epsilon action execution paths."""
    action_id: str
    next_state: WorldState
    success: bool = True
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapacityCalendar:
    """Prototype discrete capacity calendar. Keys are period offsets 0..N-1."""
    capacities: Mapping[int, Mapping[str, float]]


@dataclass(frozen=True)
class CapacityAuthorityRequest:
    """Typed host-derivation request for represented current/future capacity.

    The runtime supplies structural demand context only. The host interprets
    actual persistent state, individuals, skills, temporary depletion,
    commitments, and restoration dynamics.
    """
    actor_id: str
    state_id: str
    state_time: float
    active_corridor_ids: tuple[str, ...] = ()
    remaining_action_ids: tuple[str, ...] = ()
    demanded_resource_ids: tuple[str, ...] = ()
    latest_deadline: float | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapacityAuthorityEnvelope:
    """Host-derived represented capacity authority for one actual-state snapshot."""
    actor_id: str
    state_id: str
    state_time: float
    calendar: CapacityCalendar
    source_id: str = "host_capacity_authority"
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapacityAuthorityValidationAssessment:
    valid: bool
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduledRecoveryStep:
    period_offset: int
    corridor_id: str
    action_id: str
    demands: Mapping[str, float]


@dataclass(frozen=True)
class CorridorFeasibilityReport:
    jointly_feasible: bool
    schedule: tuple[ScheduledRecoveryStep, ...] = ()
    infeasible_corridor_sets: tuple[tuple[str, ...], ...] = ()
    deadline_slack: Mapping[str, float] = field(default_factory=dict)
    bottleneck_resources: Mapping[tuple[str, ...], tuple[str, ...]] = field(default_factory=dict)
    residual_capacity: Mapping[int, Mapping[str, float]] = field(default_factory=dict)
    infeasible_sets_complete: bool = True
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class JointRecoveryFeasibilityAssessment:
    """Adequacy-side integration view of active shared-capacity feasibility.

    This is not a new Layer-2 operator. It records a structural precondition
    computed from the runtime's active recovery ledger plus an explicitly
    supplied represented CapacityCalendar.
    """
    status: str
    active_corridor_ids: tuple[str, ...] = ()
    capacity_authority_supplied: bool = False
    runtime_verified: bool = False
    jointly_feasible: bool | None = None
    report: CorridorFeasibilityReport | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class JointRecoveryExecutionBindingAssessment:
    """Verified current-period recovery obligations bound into policy authority.

    This is an integration binding, not a selector or new policy preference.
    """
    status: str
    period_offset: int | None = None
    mandatory_action_ids: tuple[str, ...] = ()
    bound_candidate_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class AdapterIdentity:
    """Versioned identity for one application/domain adapter surface.

    Identity is descriptive/provenance-bearing only. Registration does not grant
    an adapter authority to replace or bypass canonical runtime operators.
    """
    adapter_id: str
    adapter_role: str
    implementation_version: str
    provenance_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionReplayPackage:
    """V2.1 replay-sufficient historical decision evidence package.

    This is an audit/reconstruction carrier, not live state, a Context Graph,
    a replay operator, or authorization for a later decision. Objects are
    retained as the decision-time artifacts/references actually used.
    """
    decision_episode_id: str
    actor_id: str
    decision_time: float
    framework_version: str
    runtime_version: str
    actual_state: ActualPersistentStateEnvelope | None = None
    actual_state_reference: Any = None
    perceived_decision_state: PerceivedDecisionState | None = None
    objective_set: ObjectiveSet | None = None
    retrieval: MemoryRetrievalPackage | None = None
    expectation_state: ExpectationStateReference | None = None
    transfer_history_references: tuple[TransferHistoryReference, ...] = ()
    decision: "CanonicalDecisionCycleAssessment | None" = None
    execution_license: "ExecutionLicenseEnvelope | None" = None
    epsilon_result: "EpsilonStepResult | None" = None
    transition_result: Layer1TransitionResult | None = None
    final_actual_state: ActualPersistentStateEnvelope | None = None
    runtime_configuration: "RuntimeConfigurationProvenance | None" = None
    source_snapshot_ids: tuple[str, ...] = ()
    governing_rule_ids: tuple[str, ...] = ()
    stop_condition: str | None = None
    temporal_provenance: InformationTemporalProvenance | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReplaySufficiencyAssessment:
    sufficient: bool
    decision_episode_id: str
    missing_material: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeConfigurationProvenance:
    """Reproducibility identity for one runtime/application configuration.

    This record names the framework/runtime version and registered adapter
    surfaces. It is not a mutable configuration store and carries no operator
    semantics, weights, or selection authority.
    """
    configuration_id: str
    framework_version: str
    runtime_version: str
    created_at: float
    adapter_identities: tuple[AdapterIdentity, ...] = ()
    source_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeConfigurationProvenanceAssessment:
    valid: bool
    configuration_id: str
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class NativeExecutionResult:
    """Normalized result of one bounded native call-through attempt.

    ``status`` is one of ``succeeded``, ``failed_cleanly``, ``indeterminate``,
    or ``completed_invalid``.  A timeout/lost response belongs to
    ``indeterminate`` unless the binding itself supplies authoritative evidence
    that no material external effect occurred.
    """
    execution_id: str
    action_id: str
    binding_id: str
    status: str
    return_value: Any = None
    failure_stage: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    external_effect_possible: bool = False
    completed: bool = False
    transition_valid: bool | None = None
    notes: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"


class CleanExecutionFailure(Exception):
    """Binding-declared failure with authoritative no-material-effect evidence."""


class IndeterminateExecutionFailure(Exception):
    """Binding-declared failure for which material external effect is unknown."""


class CompletedInvalidExecution(Exception):
    """Technical completion whose realized transition/validation is invalid."""

@dataclass(frozen=True)
class NativeExecutionTelemetry:
    """Immutable telemetry record for one native execution attempt.

    Telemetry reports what the call-through boundary observed.  It is evidence,
    not a Layer-1 state transition and not a governance authorization decision.
    """
    telemetry_id: str
    execution_id: str
    action_id: str
    binding_id: str
    decision_cycle_id: str
    attempt: int
    status: str
    external_effect_possible: bool
    completed: bool
    failure_stage: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    correlation_id: str | None = None
    configuration_id: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class NativeExecutionControlState:
    """Synchronous execution-control posture for a native execution identity.

    ``state`` is one of ready, paused, aborted, or reauthorization_required.
    This is a control gate only; it does not perform asynchronous cancellation.
    """
    execution_id: str
    state: str = "ready"
    reason: str | None = None
    requested_by: str | None = None
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class NativeExecutionControlEvent:
    """Immutable bookkeeping event for a native execution control change.

    This records control history only.  It neither cancels an already-running
    external action nor determines the canonical governance re-entry stage.
    """
    event_id: str
    execution_id: str
    prior_state: str
    new_state: str
    reason: str
    requested_by: str | None = None
    evidence_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class NativeReauthorizationHandoff:
    """Execution-to-governance handoff requesting fresh authorization.

    The handoff deliberately does not name an earliest-invalidated stage.  That
    determination belongs to the later dynamic invalidation/re-entry mechanism.
    """
    handoff_id: str
    execution_id: str
    action_id: str
    binding_id: str
    decision_cycle_id: str
    reason: str
    requested_by: str | None = None
    evidence_ids: tuple[str, ...] = ()
    correlation_id: str | None = None
    configuration_id: str | None = None
    return_to_governance: bool = True
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GovernanceInvalidationSignal:
    """Host/evidence-supplied invalidation of a previously established stage artifact.

    The signal states what has become stale or invalid; it does not itself perform
    recomputation or authorize a downstream repair.
    """
    signal_id: str
    invalidated_stage: str
    reason: str
    source_kind: str
    evidence_ids: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    execution_id: str | None = None
    configuration_id: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GovernanceReentryAssessment:
    """Decision-only earliest-invalidated-stage assessment.

    No stage is recomputed by this record.  ``recompute_from_stage`` identifies
    the earliest canonical boundary whose prior result may no longer be reused.
    """
    valid: bool
    signal_ids: tuple[str, ...]
    invalidated_stages: tuple[str, ...]
    recompute_from_stage: str | None
    return_to_governance: bool
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class GovernanceArtifactDependency:
    """Explicit dependency of a previously established governance artifact on host facts."""
    dependency_id: str
    artifact_id: str
    stage: str
    fact_kind: str
    fact_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GovernanceDependencyChange:
    """Explicit notice that one or more registered dependency facts changed."""
    change_id: str
    fact_kind: str
    changed_fact_ids: tuple[str, ...]
    reason: str
    evidence_ids: tuple[str, ...] = ()
    execution_id: str | None = None
    configuration_id: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObjectiveLifecycleChange:
    """Explicit change to adjacent objective state O_i(t), not to S_i(t) or P_i(t).

    The host identifies which objective identities/versions changed and whether the
    actual or perceived decision state changed independently.  The runtime uses this
    record only for dependency-scoped invalidation; it does not infer lifecycle cause.
    """
    change_id: str
    actor_id: str
    prior_objective_set_id: str
    prior_objective_set_version: str
    current_objective_set_id: str
    current_objective_set_version: str
    changed_objective_ids: tuple[str, ...]
    reason: str
    actual_state_changed: bool = False
    perceived_state_changed: bool = False
    evidence_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObjectiveLifecycleInvalidationAssessment:
    """Dependency-scoped invalidation caused by an explicit objective lifecycle change."""
    valid: bool
    change_id: str
    objective_fact_ids: tuple[str, ...]
    matched_dependency_ids: tuple[str, ...]
    invalidation_signals: tuple[GovernanceInvalidationSignal, ...]
    reentry: GovernanceReentryAssessment
    preserved_stage_ids: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GovernanceDependencyInvalidationAssessment:
    """Derived invalidations from explicit registered dependencies and explicit fact changes."""
    valid: bool
    change_ids: tuple[str, ...]
    matched_dependency_ids: tuple[str, ...]
    invalidation_signals: tuple[GovernanceInvalidationSignal, ...]
    reentry: GovernanceReentryAssessment
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class GovernanceReentryPlan:
    """Decision-only recomputation scope after a validated earliest invalidation.

    The plan identifies which canonical stage results are reusable and which must be
    recomputed. It never executes an operator or manufactures replacement artifacts.
    """
    valid: bool
    recompute_from_stage: str | None
    reusable_upstream_stages: tuple[str, ...]
    nonreusable_stages: tuple[str, ...]
    signal_ids: tuple[str, ...] = ()
    invalidated_artifact_ids: tuple[str, ...] = ()
    execute_reentry: bool = False
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class GovernanceReentryExecutionResult:
    """One bounded automatic governance re-entry attempt.

    v0.84 intentionally supports execution only when the plan begins at PPP, where
    the mature canonical-cycle entry point can recompute the complete governance
    chain without falsely claiming partial-stage reuse. Later-stage dispatch remains
    explicit unsupported work until canonical stage entry points exist.
    """
    valid: bool
    recompute_from_stage: str | None
    status: str
    decision: "CanonicalDecisionCycleAssessment | None" = None
    reused_stage_ids: tuple[str, ...] = ()
    recomputed_stage_ids: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class JointRecoveryReentryReadinessAssessment:
    """Safety/readiness gate for a future Joint Recovery Feasibility partial re-entry.

    The mature cycle evaluates joint recovery after Pi completeness but may bind
    mandatory current-period recovery actions into Pi before Constraints.  Therefore
    a Joint Recovery change can invalidate the bound Pi consumed by Constraints even
    though the presentation trace places the feasibility stage later.
    """
    ready: bool
    status: str
    preserved_pre_binding_pi: bool
    dependency_scope_sufficient: bool
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class GovernanceReusableArtifactBundle:
    """Identity-bound references to prior canonical stage artifacts proposed for reuse.

    v0.85 validates routing/identity/completeness only.  It does not prove that the
    opaque artifact payloads remain semantically valid; that authority comes from the
    invalidation/dependency assessment that produced the re-entry plan.
    """
    bundle_id: str
    cycle_id: str
    initial_state_id: str
    configuration_id: str
    stage_artifacts: tuple[tuple[str, Any], ...]
    provenance_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GovernanceReusableArtifactBundleAssessment:
    valid: bool
    bundle_id: str
    cycle_id: str
    initial_state_id: str
    configuration_id: str
    reusable_stage_ids: tuple[str, ...]
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class SigmaReusableAdequacyArtifact:
    """Reusable Adequacy boundary payload required for a standard Sigma-only re-entry.

    Adequacy and Sigma share the same immutable authoritative Q_t(pi) records in the
    mature canonical cycle.  The records are therefore carried with the Adequacy
    artifact rather than regenerated during Sigma re-entry.
    """
    adequacy: AdequacyAssessment
    projection_records: tuple[PolicyProjectionRecord, ...]
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class AdequacyReusableProjectionArtifact:
    """Reusable projection boundary payload for an Adequacy-stage re-entry.

    Q_t(pi) is authoritative upstream evidence, not something Adequacy may regenerate.
    The optional joint-recovery artifact is carried for provenance/continuity only;
    Adequacy consumes the immutable projection records plus validated framing/G.
    """
    projection_records: tuple[PolicyProjectionRecord, ...]
    joint_recovery_artifact: Any = None
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class AdequacyReusableDomainFramingArtifact:
    """Validated Domain Framing assessment plus the exact locked DomainFrame it assessed."""
    assessment: DomainFramingAssessment
    frame: DomainFrame
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class ConstraintsReusablePiArtifact:
    """Exact bound Pi plus regime/G context consumed by a Constraints re-entry.

    This payload prevents Constraints re-entry from silently reconstructing or
    rebinding Pi.  Joint-recovery binding, when applicable, is already reflected
    in pi_construction and is provenance-only here.
    """
    pi_construction: PiConstructionAssessment
    regime_assessment: RegimeAssessment
    governing_assessment: GoverningAssessment
    joint_recovery_artifact: Any = None
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class RegimeReusableClassificationInputs:
    """Exact non-world inputs and captured Phi/H domain assessments consumed by R."""
    domain_assessments: tuple[DomainAssessment, ...]
    contextual_interruption: bool = False
    previous_regime: PreviousRegimeState | None = None
    regime_configuration_identity: str = ""
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class GraphReusableConstructionInputs:
    """Exact declarations/configuration and registry identity consumed by Graph."""
    preservation_object: PreliminaryPreservationObject
    required_graph_family_ids: tuple[str, ...] = ()
    required_graph_path_class_ids: tuple[str, ...] = ()
    graph_config: GraphConstructionConfig | None = None
    graph_substrate_identity: str = ""
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PiReusableConstructionInputs:
    """Exact upstream declarations/configuration consumed by Pi construction.

    Graph carries regime/governing identity and the visible policy seeds.  The
    remaining Pi inputs are explicit upstream declarations rather than facts Pi
    may infer from Graph topology.
    """
    materially_required_policy_class_ids: tuple[str, ...] = ()
    pi_config: PiConstructionConfig | None = None
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class GoverningReusableIdentificationInputs:
    """Identity-bound registered structural substrate consumed by canonical G."""
    governing_substrate_identity: str = ""
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class HorizonReusableEvaluationInputs:
    """Captured causal/state inputs for H without a new perception step.

    perceived_state and baseline_state are the exact already-authorized host payloads
    against which Phi was formed. H may re-run the host expected-deterioration model
    over these captured states, but may not call perceive(), project(), or domain_value().
    """
    perceived_state: WorldState
    baseline_state: WorldState
    horizon_configuration_identity: str = ""
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class PhiReusableEvaluationInputs:
    """Captured state boundary and registered-domain identity consumed by Phi re-entry.

    perceived_state and baseline_state are the already-authorized payloads created
    upstream.  Phi may re-run domain_value(), pressure_factors(), and pressure_value()
    against those captured payloads, but it may not call perceive() or construct a new
    steady baseline continuation.
    """
    perceived_state: WorldState
    baseline_state: WorldState
    phi_substrate_identity: str = ""
    notes: tuple[str, ...] = ()

# v0.99 — explicit PPP / P_i(t) re-entry inputs
@dataclass(frozen=True)
class PPPReentryInputs:
    """Actual-state authority for a fresh ordinary P_i(t) perception boundary.

    v0.99 deliberately supports the ordinary actual->P_i(t) host boundary only.
    Memory-conditioned perception remains a separate licensed retrieval path and
    is not silently collapsed into this input.
    """
    actual_state: ActualPersistentStateEnvelope
    notes: tuple[str, ...] = ()

# v0.100 — explicit memory-conditioned PPP / P_i(t) re-entry inputs
@dataclass(frozen=True)
class MemoryConditionedPPPReentryInputs:
    """Licensed inputs for fresh memory-conditioned P_i(t) re-entry.

    Raw retained M_i(t) remains opaque to the perception adapter.  The runtime
    supplies it only to MemoryRetrievalService, then supplies the validated
    retrieval package R^M_i(t,q) plus optional K_i(t) to the host perception
    boundary through prepare_memory_conditioned_cycle_snapshot().
    """
    actual_state: ActualPersistentStateEnvelope
    memory_state: MemoryStateReference
    query: Any = None
    context: Any = None
    governing_concerns: tuple[str, ...] = ()
    expectation_state: ExpectationStateReference | None = None
    request_trace: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

# v0.101 — bounded dynamic reachability refresh over already-registered Graph structure
@dataclass(frozen=True)
class GraphReachabilityObservation:
    """Host-owned current reachability fact for an existing Graph transformation.

    This record may refresh reachability of represented structure only.  It cannot
    introduce a transformation, action, instance, family, or composition.
    """
    transformation_id: str
    reachability_status: str
    observed_at: float
    source_id: str
    provenance_id: str
    uncertainty_note: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class GraphReachabilityRefreshRequest:
    """Atomic identity-bound refresh request for represented Graph reachability."""
    expected_graph_substrate_identity: str
    observations: tuple[GraphReachabilityObservation, ...]
    refresh_id: str
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class GraphReachabilityRefreshAssessment:
    status: str
    refresh_id: str
    prior_graph_substrate_identity: str
    resulting_graph_substrate_identity: str = ""
    changed_transformation_ids: tuple[str, ...] = ()
    unchanged_transformation_ids: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.102 — governance trigger produced by an applied represented-structure reachability refresh
@dataclass(frozen=True)
class GraphReachabilityGovernanceTrigger:
    """Auditable bridge from a reachability refresh to ordinary Graph-stage governance re-entry.

    A material refresh creates an explicit Graph/Seed invalidation and plan. A no-op refresh
    creates no invalidation. Rejected refreshes never create governance work.
    """
    valid: bool
    refresh_assessment: GraphReachabilityRefreshAssessment
    invalidation_signal: GovernanceInvalidationSignal | None = None
    reentry_assessment: GovernanceReentryAssessment | None = None
    reentry_plan: Any | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.104 controlled structural admission.  Admission is explicit configuration
# change, not ordinary reachability refresh and not autonomous semantic discovery.
@dataclass(frozen=True)
class GraphTransformationAdmissionRequest:
    admission_id: str
    expected_graph_substrate_identity: str
    transformation: GraphTransformationDefinition
    configuration_version: str
    source_id: str
    provenance_id: str
    rationale: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class GraphTransformationAdmissionAssessment:
    status: str
    admission_id: str
    prior_graph_substrate_identity: str
    resulting_graph_substrate_identity: str = ""
    admitted_transformation_id: str = ""
    configuration_version: str = ""
    source_id: str = ""
    provenance_id: str = ""
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.127 — controlled lifecycle for already-represented Graph transformations.
@dataclass(frozen=True)
class GraphTransformationRevisionRequest:
    revision_id: str
    expected_graph_substrate_identity: str
    operation: str  # replace | remove
    transformation_id: str
    configuration_version: str
    source_id: str
    provenance_id: str
    rationale: str
    replacement: GraphTransformationDefinition | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class GraphTransformationRevisionAssessment:
    status: str
    revision_id: str
    operation: str
    prior_graph_substrate_identity: str
    resulting_graph_substrate_identity: str = ""
    transformation_id: str = ""
    configuration_version: str = ""
    source_id: str = ""
    provenance_id: str = ""
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class GraphStructuralRevisionGovernanceTrigger:
    valid: bool
    revision_assessment: GraphTransformationRevisionAssessment
    invalidation_signal: GovernanceInvalidationSignal | None = None
    reentry_assessment: GovernanceReentryAssessment | None = None
    reentry_plan: Any | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.105 — governance trigger produced by an explicit structural admission
@dataclass(frozen=True)
class GraphStructuralAdmissionGovernanceTrigger:
    """Auditable bridge from controlled Graph admission to Graph-stage governance re-entry planning.

    Admission changes represented configuration.  A successful admission therefore invalidates the
    prior Graph/Seed artifact, but it grants no execution authority for the admitted transformation.
    """
    valid: bool
    admission_assessment: GraphTransformationAdmissionAssessment
    invalidation_signal: GovernanceInvalidationSignal | None = None
    reentry_assessment: GovernanceReentryAssessment | None = None
    reentry_plan: Any | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.107 — first-class structural-coverage evidence, separate from ordinary projection uncertainty.
@dataclass(frozen=True)
class GraphStructuralCoverageObservation:
    """Host-supplied evidence about whether represented Graph structure is materially complete.

    This does not discover or admit structure.  Missing/uncertain family, path-class, or
    composition identities are explicit evidence claims whose semantics remain host/application-owned.
    """
    observation_id: str
    expected_graph_substrate_identity: str
    coverage_status: str  # sufficient | incomplete | uncertain
    source_id: str
    provenance_id: str
    observed_at: float
    missing_family_ids: tuple[str, ...] = ()
    missing_path_class_ids: tuple[str, ...] = ()
    missing_composition_ids: tuple[str, ...] = ()
    uncertainty_markers: tuple[str, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class GraphStructuralCoverageAssessment:
    """Identity-bound qualification of structural model coverage.

    Structural coverage is deliberately distinct from uncertain values/reachability inside an
    already represented Graph.  This assessment creates no structural mutation or governance
    re-entry authority by itself.
    """
    valid: bool
    observation_id: str
    graph_substrate_identity: str
    coverage_status: str
    structurally_sufficient: bool
    material_gap_present: bool
    structural_uncertainty_present: bool
    missing_family_ids: tuple[str, ...] = ()
    missing_path_class_ids: tuple[str, ...] = ()
    missing_composition_ids: tuple[str, ...] = ()
    uncertainty_markers: tuple[str, ...] = ()
    source_id: str = ""
    provenance_id: str = ""
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.108 — structural-coverage qualification -> explicit Graph-stage governance trigger
@dataclass(frozen=True)
class GraphStructuralCoverageGovernanceTrigger:
    """Auditable bridge from structural-coverage evidence to Graph/Seed authority invalidation.

    Sufficient coverage creates no invalidation. Material incompleteness or unresolved structural
    uncertainty invalidates prior Graph/Seed authority but does not discover/admit missing structure.
    """
    valid: bool
    coverage_assessment: GraphStructuralCoverageAssessment
    invalidation_signal: GovernanceInvalidationSignal | None = None
    reentry_assessment: GovernanceReentryAssessment | None = None
    reentry_plan: Any | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.109 — explicit structural-coverage blocked/unsupported outcome and admission handoff
@dataclass(frozen=True)
class GraphStructuralCoverageAdmissionHandoff:
    """Non-authorizing handoff for known missing Graph structure.

    The handoff carries only the evidence-qualified missing identities and provenance needed to begin
    a separate definition/admission workflow.  It is not a GraphTransformationAdmissionRequest and
    cannot invent the missing transformation definition.
    """
    coverage_observation_id: str
    graph_substrate_identity: str
    source_id: str
    provenance_id: str
    missing_family_ids: tuple[str, ...] = ()
    missing_path_class_ids: tuple[str, ...] = ()
    missing_composition_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class GraphStructuralCoverageDisposition:
    """Terminal disposition of structural-coverage qualification before Graph reconstruction.

    status values:
      coverage_sufficient        -- no structural block exists
      admission_definition_required -- known material gap; separate definition/admission is required
      unsupported_uncertain      -- material structural uncertainty; missing semantics are not known
      invalid                    -- evidence/trigger cannot create authority
    """
    valid: bool
    status: str
    graph_reentry_blocked: bool
    trigger: Any
    admission_handoff: GraphStructuralCoverageAdmissionHandoff | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.110 — provenance-bearing security observation / evidence-authority foundation.
@dataclass(frozen=True)
class SecurityEvidenceObservation:
    """Typed security-critical observation with explicit epistemic metadata.

    The observation reports evidence; it does not decide feasibility, adequacy, selection,
    or which canonical artifact the evidence invalidates.
    """
    observation_id: str
    fact_id: str
    value: Any
    source_id: str
    provenance_id: str
    observed_at: float
    authority_status: str  # authoritative | corroborated | provisional | disputed | untrusted
    confidence: float | None = None
    distortion_risk: str = "unknown"  # low | medium | high | unknown
    independent_confirmation_ids: tuple[str, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class SecurityEvidenceAssessment:
    """Validation/qualification of a provenance-bearing security observation.

    `usable_as_governance_evidence` is an epistemic admission result only.  It grants no
    downstream canonical authority and does not imply that the represented fact is true.
    """
    valid: bool
    observation_id: str
    fact_id: str
    source_id: str
    provenance_id: str
    authority_status: str
    usable_as_governance_evidence: bool
    requires_independent_confirmation: bool
    confidence: float | None = None
    distortion_risk: str = "unknown"
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.111 — evidence-source authority/control state and fact-to-source dependency tracking.
@dataclass(frozen=True)
class EvidenceSourceAuthorityState:
    """Current epistemic/control qualification of a named evidence source."""
    source_id: str
    provenance_id: str
    assessed_at: float
    authority_state: str  # trusted | degraded | compromised | revoked | stale
    control_state: str  # independent | governed_agent | descendant | unknown
    valid_until: float | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class GovernanceEvidenceDependency:
    """Explicit dependency of a governance fact/observation on an evidence source.

    This record identifies epistemic dependency only; it intentionally does not identify
    a canonical re-entry stage.
    """
    dependency_id: str
    fact_id: str
    observation_id: str
    source_id: str
    source_provenance_id: str
    dependency_role: str = "supporting"  # primary | supporting | corroborating
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class EvidenceDependencyAuthorityAssessment:
    """Qualification of whether a fact-to-source dependency retains epistemic authority."""
    valid: bool
    dependency_id: str
    fact_id: str
    source_id: str
    source_provenance_id: str
    retains_epistemic_authority: bool
    loss_reason: str | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.112 — explicit evidence-to-canonical-artifact dependency and authority-loss invalidation.
@dataclass(frozen=True)
class EvidenceCanonicalArtifactDependency:
    """Declared dependency of a canonical artifact on a qualified evidence dependency."""
    dependency_id: str
    evidence_dependency_id: str
    fact_id: str
    artifact_id: str
    stage: str
    provenance_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class EvidenceAuthorityGovernanceInvalidationAssessment:
    """Stage-aware invalidation derived only from explicit evidence/artifact dependencies."""
    valid: bool
    evidence_dependency_ids: tuple[str, ...]
    matched_artifact_dependency_ids: tuple[str, ...]
    invalidation_signals: tuple[GovernanceInvalidationSignal, ...]
    reentry: GovernanceReentryAssessment
    plan: GovernanceReentryPlan | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.113 — auditable epistemic invalidation/re-entry orchestration.
@dataclass(frozen=True)
class EpistemicInvalidationOrchestrationAssessment:
    """One auditable chain from source-state qualification through re-entry planning.

    The record preserves every intermediate authority assessment and the final explicit
    artifact-invalidation assessment.  It is orchestration only: no canonical operator is
    recomputed and no execution authority is created.
    """
    valid: bool
    source_id: str
    source_provenance_id: str
    evidence_dependency_ids: tuple[str, ...]
    authority_assessments: tuple[EvidenceDependencyAuthorityAssessment, ...]
    governance_invalidation: EvidenceAuthorityGovernanceInvalidationAssessment | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.114 — controlled execution dispatch for epistemically generated re-entry plans.
@dataclass(frozen=True)
class EpistemicReentryExecutionAssessment:
    """Auditable dispatch result for an epistemically generated re-entry plan.

    This wrapper does not create a new re-entry engine.  It records whether the exact
    existing stage-specific executor was available and invoked, or why execution was
    blocked before canonical recomputation.
    """
    valid: bool
    recompute_from_stage: str | None
    status: str
    execution_result: GovernanceReentryExecutionResult | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.116 — provenance-bearing capability-change observation and validation.
@dataclass(frozen=True)
class CapabilityChangeObservation:
    """Explicit evidence that a governed entity's represented capability changed.

    Capability state is intentionally opaque/non-scalar here.  The observer declares
    the change category and before/after snapshot identities; the runtime validates
    evidence hygiene but does not infer PP magnitude, domain weights, Graph structure,
    or consequential authority from this record.
    """
    observation_id: str
    entity_id: str
    capability_id: str
    observed_at: float
    change_kind: str  # gained | lost | increased | decreased | reconfigured | uncertain
    prior_snapshot_id: str | None
    current_snapshot_id: str | None
    source_id: str
    provenance_id: str
    confidence: float | None = None
    evidence_ids: tuple[str, ...] = ()
    configuration_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityChangeValidationAssessment:
    """Evidence-hygiene qualification for an explicitly reported capability change."""
    valid: bool
    observation_id: str
    entity_id: str
    capability_id: str
    change_kind: str
    material_change_reported: bool
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.117 — cumulative capability-trajectory projection over validated observations.
@dataclass(frozen=True)
class CapabilityTrajectoryProjection:
    """Auditable, non-scalar temporal projection of reported capability formation.

    This record preserves ordered change evidence and uncertainty. It is not a scalar PP
    score and does not itself modify Graph/Pi or create governance/execution authority.
    """
    trajectory_id: str
    entity_id: str
    capability_id: str
    as_of: float
    observation_ids: tuple[str, ...]
    ordered_change_kinds: tuple[str, ...]
    snapshot_chain: tuple[str, ...]
    source_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]
    configuration_ids: tuple[str, ...]
    uncertain_observation_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityTrajectoryProjectionAssessment:
    """Qualification/result for a cumulative capability trajectory projection."""
    valid: bool
    trajectory: CapabilityTrajectoryProjection | None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.118 — explicit capability-to-represented-Graph reachability dependency.
@dataclass(frozen=True)
class CapabilityGraphReachabilityDependency:
    """Host-declared consequence of a capability snapshot for existing Graph structure.

    This is not semantic discovery: the application explicitly declares which already-
    represented transformation's reachability depends on the capability trajectory and
    what reachability fact is supported at the declared snapshot.
    """
    dependency_id: str
    entity_id: str
    capability_id: str
    transformation_id: str
    capability_snapshot_id: str
    reachability_status: str
    source_id: str
    provenance_id: str
    uncertainty_note: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityDrivenGraphRefreshAssessment:
    """Result of an explicit capability-trajectory-driven represented-Graph refresh."""
    valid: bool
    trajectory_id: str
    matched_dependency_ids: tuple[str, ...] = ()
    refresh_request: GraphReachabilityRefreshRequest | None = None
    governance_trigger: GraphReachabilityGovernanceTrigger | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.119 — capability-formation prediction error and explicit governance dependency.
@dataclass(frozen=True)
class CapabilityFormationExpectation:
    """Explicit prior expectation for a later capability snapshot; non-scalar and identity-based."""
    expectation_id: str
    entity_id: str
    capability_id: str
    expected_at: float
    expected_snapshot_id: str
    source_id: str
    provenance_id: str
    configuration_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityFormationPredictionError:
    """Provenance-bearing mismatch between a prior capability expectation and later evidence."""
    error_id: str
    expectation_id: str
    trajectory_id: str
    entity_id: str
    capability_id: str
    expected_snapshot_id: str
    observed_snapshot_id: str
    observed_at: float
    source_id: str
    provenance_id: str
    configuration_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityPredictionArtifactDependency:
    """Explicit binding from a capability prediction expectation to a canonical artifact."""
    dependency_id: str
    expectation_id: str
    artifact_id: str
    stage: str
    provenance_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityFormationPredictionErrorAssessment:
    valid: bool
    expectation_id: str
    trajectory_id: str
    prediction_error: CapabilityFormationPredictionError | None = None
    matched_dependency_ids: tuple[str, ...] = ()
    invalidation_signals: tuple[GovernanceInvalidationSignal, ...] = ()
    reentry_assessment: GovernanceReentryAssessment | None = None
    reentry_plan: GovernanceReentryPlan | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.121 — controlled novel consequential-function admission.
# A new action/function and its first represented Graph transformation are admitted atomically.
@dataclass(frozen=True)
class NovelFunctionAdmissionRequest:
    admission_id: str
    expected_action_registry_identity: str
    expected_graph_substrate_identity: str
    action: ActionDefinition
    transformation: GraphTransformationDefinition
    configuration_version: str
    source_id: str
    provenance_id: str
    rationale: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class NovelFunctionAdmissionAssessment:
    status: str
    admission_id: str
    prior_action_registry_identity: str
    prior_graph_substrate_identity: str
    resulting_action_registry_identity: str = ""
    resulting_graph_substrate_identity: str = ""
    admitted_action_id: str = ""
    admitted_transformation_id: str = ""
    configuration_version: str = ""
    source_id: str = ""
    provenance_id: str = ""
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class NovelFunctionAdmissionGovernanceTrigger:
    valid: bool
    admission_assessment: NovelFunctionAdmissionAssessment
    invalidation_signal: GovernanceInvalidationSignal | None = None
    reentry_assessment: GovernanceReentryAssessment | None = None
    reentry_plan: Any | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.122 — controlled dynamic governing/recovery dependency admission.
@dataclass(frozen=True)
class RecoveryNecessityAdmissionRequest:
    admission_id: str
    expected_governing_substrate_identity: str
    relation: RecoveryNecessityDefinition
    configuration_version: str
    source_id: str
    provenance_id: str
    rationale: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RecoveryNecessityAdmissionAssessment:
    status: str
    admission_id: str
    prior_governing_substrate_identity: str
    resulting_governing_substrate_identity: str = ""
    admitted_relation_id: str = ""
    configuration_version: str = ""
    source_id: str = ""
    provenance_id: str = ""
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class RecoveryNecessityAdmissionGovernanceTrigger:
    valid: bool
    admission_assessment: RecoveryNecessityAdmissionAssessment
    invalidation_signal: GovernanceInvalidationSignal | None = None
    reentry_assessment: GovernanceReentryAssessment | None = None
    reentry_plan: Any | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


# v0.123 — controlled revision/removal of existing recovery-necessity topology.
@dataclass(frozen=True)
class RecoveryNecessityRevisionRequest:
    revision_id: str
    expected_governing_substrate_identity: str
    operation: str
    relation_id: str
    replacement: RecoveryNecessityDefinition | None
    configuration_version: str
    source_id: str
    provenance_id: str
    rationale: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RecoveryNecessityRevisionAssessment:
    status: str
    revision_id: str
    operation: str
    prior_governing_substrate_identity: str
    resulting_governing_substrate_identity: str = ""
    affected_relation_id: str = ""
    configuration_version: str = ""
    source_id: str = ""
    provenance_id: str = ""
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class RecoveryNecessityRevisionGovernanceTrigger:
    valid: bool
    revision_assessment: RecoveryNecessityRevisionAssessment
    invalidation_signal: GovernanceInvalidationSignal | None = None
    reentry_assessment: GovernanceReentryAssessment | None = None
    reentry_plan: Any | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.124 — dynamic control/provenance topology representation.
@dataclass(frozen=True)
class ControlProvenanceRelation:
    """Explicit current control/provenance edge supplied by the host/application."""
    relation_id: str
    subject_id: str
    object_id: str
    relation_type: str  # creates | controls | delegates | revokes | terminates | descends_from
    observed_at: float
    source_id: str
    provenance_id: str
    active: bool = True
    evidence_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class ControlProvenanceTopologyAssessment:
    """Validated snapshot of explicit dynamic control/provenance relations."""
    valid: bool
    topology_id: str
    as_of: float
    relations: tuple[ControlProvenanceRelation, ...]
    controlled_by_governed_agent: tuple[str, ...] = ()
    descendant_objects: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.125 — controlled lifecycle for dynamic control/provenance topology snapshots.
@dataclass(frozen=True)
class ControlProvenanceTopologyUpdateRequest:
    update_id: str
    prior_topology_identity: str
    topology_id: str
    as_of: float
    relations: tuple[ControlProvenanceRelation, ...]
    governed_agent_ids: tuple[str, ...]
    configuration_version: str
    source_id: str
    provenance_id: str
    rationale: str

@dataclass(frozen=True)
class ControlProvenanceTopologyUpdateAssessment:
    valid: bool
    status: str
    update_id: str
    prior_topology_identity: str
    resulting_topology_identity: str = ""
    topology_assessment: ControlProvenanceTopologyAssessment | None = None
    added_relation_ids: tuple[str, ...] = ()
    removed_relation_ids: tuple[str, ...] = ()
    changed_relation_ids: tuple[str, ...] = ()
    configuration_version: str = ""
    source_id: str = ""
    provenance_id: str = ""
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.126 — explicit control/provenance-topology to canonical-artifact dependency binding.
@dataclass(frozen=True)
class ControlProvenanceArtifactDependency:
    """Declared dependency of a canonical artifact on explicit topology relation identities."""
    dependency_id: str
    artifact_id: str
    stage: str
    relation_ids: tuple[str, ...]
    relation_types: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class ControlProvenanceGovernanceInvalidationAssessment:
    """Invalidation/re-entry result derived only from an accepted topology update and declared dependencies."""
    valid: bool
    update_id: str
    changed_relation_ids: tuple[str, ...]
    matched_dependency_ids: tuple[str, ...]
    invalidation_signals: tuple[GovernanceInvalidationSignal, ...]
    reentry: GovernanceReentryAssessment
    plan: GovernanceReentryPlan | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.128 — explicit capability-to-Graph constructibility dependency.
@dataclass(frozen=True)
class CapabilityGraphConstructibilityDependency:
    """Host-declared capability consequence that can construct one new represented Graph path.

    The runtime does not invent the path.  The application supplies a complete typed transformation
    using already-registered action/domain/instance vocabulary and binds it to a definite capability
    snapshot plus provenance/version information.
    """
    dependency_id: str
    entity_id: str
    capability_id: str
    capability_snapshot_id: str
    transformation: GraphTransformationDefinition
    configuration_version: str
    source_id: str
    provenance_id: str
    rationale: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityDrivenGraphConstructibilityAssessment:
    """Result of capability-driven controlled construction/admission of represented Graph structure."""
    valid: bool
    trajectory_id: str
    matched_dependency_id: str = ""
    admission_request: GraphTransformationAdmissionRequest | None = None
    governance_trigger: GraphStructuralAdmissionGovernanceTrigger | None = None
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

# v0.129 — cross-domain architecture-invariance/adaptation instrumentation.
@dataclass(frozen=True)
class ArchitectureInvarianceProfile:
    profile_id: str
    canonical_stage_ids: tuple[str, ...]
    required_adapter_roles: tuple[str, ...]
    prohibited_adapter_roles: tuple[str, ...] = ("selector", "canonical_operator", "sigma_override")
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class ArchitectureAdaptationAssessment:
    valid: bool
    profile_id: str
    configuration_ids: tuple[str, ...]
    invariant_stage_ids: tuple[str, ...]
    adapter_roles_by_configuration: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
