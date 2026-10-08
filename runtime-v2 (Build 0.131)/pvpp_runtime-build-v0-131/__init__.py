from .models import (
    DomainDefinition, ProductivePowerDefinition, ProductivePowerState, AccessOperabilityState, AccessOperabilityValidationAssessment, ProductiveConfigurationState, ProductiveConfigurationValidationAssessment, RecoveryResourceState, RecoveryResourceValidationAssessment, QualifiedUnitState, QualifiedUnitValidationAssessment, ExecutionBindingIdentity, NativeExecutionAuthorization, ExecutionContext, ExecutionBindingAssessment, NativeExecutionResult, NativeExecutionTelemetry, NativeExecutionControlState, CleanExecutionFailure, IndeterminateExecutionFailure, CompletedInvalidExecution, ActionDefinition,
    WorldState, ProjectionCausalStateInput, ProjectionInputLicenseAssessment, ProjectionModelAuthority, ProjectionModelAuthorityAssessment, PerceivedDecisionState, PerceivedDecisionStateValidationAssessment, ActualPersistentStateEnvelope, Layer1TransitionResult, Layer1TransitionValidationAssessment, ExecutionTransitionProvenance, ExecutionTransitionProvenanceAssessment, CrossObjectExecutionIdentityAssessment, IntegratedCycleLifecycleIntegrityAssessment, AdapterIdentity, RuntimeConfigurationProvenance, RuntimeConfigurationProvenanceAssessment, CanonicalCycleSnapshot, CanonicalIntegratedCycleResult, CanonicalCycleDirective, CanonicalCycleLedgerEntry, CanonicalCycleSequenceAssessment, MemoryStateReference, RetrievalQualityMetadata, MemoryRetrievalRequest, MemoryRetrievalPackage, ExpectationStateReference, MemoryConditionedCycleSnapshot, PredictionErrorComponent, PredictionErrorRequest, PredictionErrorAssessment, PredictionErrorValidationAssessment, PostExecutionEpistemicUpdateRequest, PostExecutionEpistemicUpdateResult, EpistemicUpdateValidationAssessment, MemoryConditionedIntegratedCycleResult, MemoryConditionedCycleDirective, MemoryConditionedCycleLedgerEntry, MemoryConditionedCycleSequenceAssessment, PressureFactors, PressureDomainResult, PressureFieldAssessment, PressureInvariantAssessment, HorizonConfiguration, HorizonDomainResult, HorizonAssessment, DomainAssessment, ActionProjection, ActionEvaluation, RecoveryAdequacyAssessment, DiscretionarySelectionAssessment, PVPPAssessment,
    RecoveryPlanDefinition, ActiveRecoveryCorridor, ExecutionResult, ExecutionLicenseEnvelope, ExecutionObservation, ExecutionTraceNode, ExecutionEpisode, EpsilonStepResult, Layer1TransitionHandoff, RecoveryActionConfirmation, Layer1ExecutionCommit, ExecutionBookkeepingAssessment, CapacityCalendar, CapacityAuthorityRequest, CapacityAuthorityEnvelope, CapacityAuthorityValidationAssessment, SelectedPolicy,
    PreliminaryPreservationObject, GraphInstanceDefinition, GraphTransformationDefinition, GraphCompositionDefinition, GraphConstructionConfig, GraphConstructionAssessment, PolicySeedDefinition, PiConstructionConfig, PiConstructionAssessment, CandidatePolicySet, CandidatePolicySpace, PiCompletenessAssessment, EpistemicSubstrateQualification, QualifiedPiCompletenessAssessment, RecoveryCorridorProjection, PolicyProjectionRecord, ProjectionInformationQualityClaim, ProjectionRequest, ProjectionConsistencyAudit, CycleArtifactIntegrityAssessment, DomainAdequacyResult, PolicyAdequacyResult, AdequacyAssessment, SigmaOrderDefinition, FallbackConfiguration, FallbackStructuralProfile, SigmaFallbackAssessment, SigmaStageAssessment, SigmaAssessment, GoverningConfiguration, RecoveryNecessityDefinition, GoverningAssessment, RegimeConfiguration, PreviousRegimeState, RegimeAssessment, ConstraintRuleDefinition, ConstraintObservation, PolicyConstraintProfile, ConstraintViolationProfile, ConstraintAssessment, ConstraintsAssessment, DomainFrameTarget, DomainFrame, DomainFramingAssessment, PolicySetEvaluation, CanonicalDecisionCycleRequest, CanonicalDecisionCycleAssessment, PolicySelectionAssessment, DomainRelationDefinition, DependencyRequirementDefinition, StructuralPolicyAssessment,
    ScheduledRecoveryStep, CorridorFeasibilityReport, JointRecoveryExecutionBindingAssessment,
)
from .registry import PVPPRegistry
from .kernel import PVPPRuntime

from .interfaces import PolicyProjectionService, Layer1TransitionService

from .testing import (
    BoundedViabilityWitness, SequenceDiagnostics, MultidomainStressClassification,
    bounded_viability_oracle, analyze_sequence, classify_multidomain_stress,
    ContaminatedSubstratePairedAssessment, compare_contaminated_substrate_cycles,
    ProjectionCausalStateConsistencyDeclaration, ProjectionCausalStateCrossCycleAssessment,
    compare_projection_causal_state_across_cycles,
    ProjectionAttributionSnapshot, ProjectionCrossCycleAttributionAssessment,
    capture_projection_attribution_snapshot, compare_projection_attribution_across_cycles,
)

from .interfaces import CapacityAuthorityService

from .interfaces import PredictionErrorService

from .interfaces import StateMeasurementAdapter, ActionStructureAdapter, ProjectionWorldModelAdapter, ConstraintEvidenceAdapter, ExecutionTransitionAdapter

from .execution import ExecutionBindingRegistry

# V2 build v0.80 execution-control bookkeeping exports
from .models import NativeExecutionControlEvent, NativeReauthorizationHandoff

# V2 build v0.81 dynamic invalidation / re-entry assessment exports
from .models import GovernanceInvalidationSignal, GovernanceReentryAssessment
from .reentry import CANONICAL_REENTRY_STAGE_ORDER, assess_governance_reentry, apply_executable_dependency_scope

# V2 build v0.82 explicit governance dependency bookkeeping exports
from .models import GovernanceArtifactDependency, GovernanceDependencyChange, GovernanceDependencyInvalidationAssessment
from .reentry import derive_dependency_invalidations

# V2 build v0.83 bounded re-entry planning exports
from .models import GovernanceReentryPlan
from .reentry import plan_governance_reentry

# V2 build v0.84 bounded automatic re-entry execution exports
from .models import GovernanceReentryExecutionResult
from .reentry import execute_governance_reentry

# V2 build v0.85 reusable-stage artifact bundle validation exports
from .models import GovernanceReusableArtifactBundle, GovernanceReusableArtifactBundleAssessment
from .reentry import validate_reusable_artifact_bundle

# V2 build v0.86 genuine standard-Sigma partial re-entry exports
from .models import SigmaReusableAdequacyArtifact
from .reentry import execute_sigma_reentry

# v0.87 bounded Adequacy-stage re-entry exports
from .models import AdequacyReusableProjectionArtifact
from .reentry import execute_adequacy_reentry
from .models import AdequacyReusableDomainFramingArtifact

from .models import JointRecoveryReentryReadinessAssessment
from .reentry import assess_joint_recovery_reentry_readiness

# v0.90 genuine Joint Recovery executable-dependency re-entry
from .reentry import execute_joint_recovery_reentry
from .models import ConstraintsReusablePiArtifact
from .reentry import execute_constraints_reentry

# v0.92 genuine Pi Completeness partial re-entry
from .reentry import execute_pi_completeness_reentry

# v0.93 genuine Pi construction partial re-entry
from .models import GraphReusableConstructionInputs, PiReusableConstructionInputs
from .reentry import execute_pi_reentry
from .reentry import execute_graph_reentry

# v0.95 genuine Regime (R) partial re-entry
from .models import RegimeReusableClassificationInputs
from .reentry import execute_regime_reentry

# v0.96 genuine Governing Domain Identification (G) partial re-entry
from .models import GoverningReusableIdentificationInputs
from .reentry import execute_governing_reentry

from .models import HorizonReusableEvaluationInputs
from .reentry import execute_horizon_reentry

# v0.98 genuine Phi partial-stage re-entry
from .models import PhiReusableEvaluationInputs
from .reentry import execute_phi_reentry

# v0.99 genuine PPP / P_i(t) partial-stage re-entry
from .models import PPPReentryInputs
from .reentry import execute_ppp_reentry

# v0.100 memory-conditioned PPP / P_i(t) re-entry
from .models import MemoryConditionedPPPReentryInputs
from .reentry import execute_memory_conditioned_ppp_reentry

# v0.101 bounded dynamic Graph reachability refresh (represented structure only)
from .models import GraphReachabilityObservation, GraphReachabilityRefreshRequest, GraphReachabilityRefreshAssessment
from .interfaces import GraphReachabilityAdapter

# v0.102 represented reachability refresh -> explicit Graph-stage governance trigger
from .models import GraphReachabilityGovernanceTrigger
from .reentry import refresh_graph_reachability_and_plan_reentry

# v0.103 represented reachability refresh -> Graph/Pi/downstream execution
from .reentry import execute_graph_reachability_refresh_reentry

# v0.104 controlled Graph structural admission
from .models import GraphTransformationAdmissionRequest, GraphTransformationAdmissionAssessment, GraphTransformationRevisionRequest, GraphTransformationRevisionAssessment, GraphStructuralRevisionGovernanceTrigger

# v0.105 controlled structural admission -> explicit Graph-stage governance trigger
from .models import GraphStructuralAdmissionGovernanceTrigger
from .reentry import admit_graph_transformation_and_plan_reentry, revise_graph_transformation_and_plan_reentry
from .reentry import execute_graph_structural_admission_reentry

# v0.107 first-class structural-coverage qualification
from .models import GraphStructuralCoverageObservation, GraphStructuralCoverageAssessment

# v0.108 structural coverage -> explicit Graph-stage governance trigger
from .models import GraphStructuralCoverageGovernanceTrigger
from .reentry import assess_graph_structural_coverage_and_plan_reentry

# v0.109 structural-coverage blocked/unsupported disposition and controlled admission handoff
from .models import GraphStructuralCoverageAdmissionHandoff, GraphStructuralCoverageDisposition
from .reentry import disposition_graph_structural_coverage

# v0.110 provenance-bearing security evidence foundation
from .models import SecurityEvidenceObservation, SecurityEvidenceAssessment
from .reentry import assess_security_evidence_observation

# v0.111 evidence-source authority/control and fact-to-source dependency tracking
from .models import EvidenceSourceAuthorityState, GovernanceEvidenceDependency, EvidenceDependencyAuthorityAssessment
from .reentry import assess_evidence_dependency_authority

# v0.112 evidence-to-canonical-artifact dependency and authority-loss invalidation
from .models import EvidenceCanonicalArtifactDependency, EvidenceAuthorityGovernanceInvalidationAssessment
from .reentry import derive_evidence_authority_governance_invalidations

# v0.113 auditable epistemic invalidation/re-entry orchestration
from .models import EpistemicInvalidationOrchestrationAssessment
from .reentry import orchestrate_epistemic_invalidation_reentry

# v0.114 controlled execution dispatch for epistemically generated re-entry plans
from .models import EpistemicReentryExecutionAssessment
from .reentry import execute_epistemic_reentry_plan

# v0.115 genuine Domain Framing partial re-entry
from .reentry import execute_domain_framing_reentry

# v0.116 provenance-bearing capability-change observation and validation
from .models import CapabilityChangeObservation, CapabilityChangeValidationAssessment
from .reentry import validate_capability_change_observation

# v0.117 cumulative capability-trajectory projection
from .models import CapabilityTrajectoryProjection, CapabilityTrajectoryProjectionAssessment
from .reentry import project_capability_trajectory

# v0.118 capability-driven represented-Graph reachability refresh
from .models import CapabilityGraphReachabilityDependency, CapabilityDrivenGraphRefreshAssessment
from .reentry import refresh_graph_from_capability_trajectory

# v0.119 capability-formation prediction error and explicit re-entry planning
from .models import (CapabilityFormationExpectation, CapabilityFormationPredictionError,
    CapabilityPredictionArtifactDependency, CapabilityFormationPredictionErrorAssessment)
from .reentry import assess_capability_formation_prediction_error

# v0.121 controlled novel consequential-function/action admission
from .models import NovelFunctionAdmissionRequest, NovelFunctionAdmissionAssessment, NovelFunctionAdmissionGovernanceTrigger
from .reentry import admit_novel_function_and_plan_reentry

# v0.122 controlled dynamic recovery-necessity topology admission
from .models import RecoveryNecessityAdmissionRequest, RecoveryNecessityAdmissionAssessment, RecoveryNecessityAdmissionGovernanceTrigger
from .reentry import admit_recovery_necessity_and_plan_reentry


# v0.123 controlled revision/removal of recovery-necessity topology
from .models import RecoveryNecessityRevisionRequest, RecoveryNecessityRevisionAssessment, RecoveryNecessityRevisionGovernanceTrigger
from .reentry import revise_recovery_necessity_and_plan_reentry

# v0.124 dynamic control/provenance topology representation and evidence-source qualification
from .models import ControlProvenanceRelation, ControlProvenanceTopologyAssessment
from .reentry import assess_control_provenance_topology, qualify_evidence_source_from_control_topology

# v0.125 controlled control/provenance topology lifecycle
from .models import ControlProvenanceTopologyUpdateRequest, ControlProvenanceTopologyUpdateAssessment
from .reentry import control_provenance_topology_identity, update_control_provenance_topology

# v0.126 explicit control/provenance topology -> canonical artifact dependencies
from .models import ControlProvenanceArtifactDependency, ControlProvenanceGovernanceInvalidationAssessment
from .reentry import derive_control_provenance_governance_invalidations

# v0.128 capability-driven Graph constructibility
from .models import CapabilityGraphConstructibilityDependency, CapabilityDrivenGraphConstructibilityAssessment
from .reentry import construct_graph_from_capability_trajectory

# v0.129 architecture-invariance instrumentation
from .models import ArchitectureInvarianceProfile, ArchitectureAdaptationAssessment
