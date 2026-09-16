from __future__ import annotations
import hashlib
import json
from dataclasses import asdict, is_dataclass, replace
from .models import DomainDefinition, ProductivePowerDefinition, ActionDefinition, RecoveryPlanDefinition, DomainRelationDefinition, DependencyRequirementDefinition, RegimeConfiguration, GoverningConfiguration, RecoveryNecessityDefinition, HorizonConfiguration, PolicySeedDefinition, SigmaOrderDefinition, ConstraintRuleDefinition, FallbackConfiguration, GraphReachabilityRefreshRequest, GraphReachabilityRefreshAssessment, GraphTransformationAdmissionRequest, GraphTransformationAdmissionAssessment, GraphTransformationRevisionRequest, GraphTransformationRevisionAssessment, GraphStructuralCoverageObservation, GraphStructuralCoverageAssessment, NovelFunctionAdmissionRequest, NovelFunctionAdmissionAssessment, RecoveryNecessityAdmissionRequest, RecoveryNecessityAdmissionAssessment, RecoveryNecessityRevisionRequest, RecoveryNecessityRevisionAssessment

class PVPPRegistry:
    def __init__(self) -> None:
        self.domains = {}
        self.powers = {}
        self.actions = {}
        self.recovery_plans = {}
        self.recovery_trigger_index = {}
        self.domain_relations = {}
        self.dependency_requirements = {}
        self.regime_configuration = None
        self.governing_configuration = None
        self.horizon_configuration = None
        self.recovery_necessities = {}
        self.policy_seeds = {}
        self.graph_instances = {}
        self.graph_transformations = {}
        self.graph_compositions = {}
        self.sigma_order = {}
        self.sigma_order_indices = {}
        self.constraint_rules = {}
        self.fallback_configuration = None
    def register_domain(self, domain):
        if domain.id in self.domains: raise ValueError(f"Domain already registered: {domain.id}")
        self.domains[domain.id]=domain
    def register_power(self, power):
        if power.id in self.powers: raise ValueError(f"Productive power already registered: {power.id}")
        if power.domain_id not in self.domains: raise ValueError(f"Productive power {power.id} references unregistered domain: {power.domain_id}")
        self.powers[power.id]=power
    def register_action(self, action):
        if action.id in self.actions: raise ValueError(f"Action already registered: {action.id}")
        unknown=[d for d in action.domains if d not in self.domains]
        if unknown: raise ValueError(f"Action {action.id} references unregistered domains: {unknown}")
        self.actions[action.id]=action
    def register_recovery_plan(self, plan: RecoveryPlanDefinition):
        if plan.id in self.recovery_plans: raise ValueError(f"Recovery plan already registered: {plan.id}")
        if plan.domain_id not in self.domains: raise ValueError(plan.domain_id)
        if plan.trigger_action not in self.actions: raise ValueError(plan.trigger_action)
        unknown=[a for a in plan.continuation_actions if a not in self.actions]
        if unknown: raise ValueError(f"Recovery plan {plan.id} references unregistered actions: {unknown}")
        self.recovery_plans[plan.id]=plan
        self.recovery_trigger_index.setdefault(plan.trigger_action, []).append(plan.id)

    def register_domain_relation(self, relation: DomainRelationDefinition):
        if relation.id in self.domain_relations:
            raise ValueError(f"Domain relation already registered: {relation.id}")
        if relation.source_domain_id not in self.domains:
            raise ValueError(relation.source_domain_id)
        if relation.target_domain_id not in self.domains:
            raise ValueError(relation.target_domain_id)
        if relation.relation_type != "dependency_floor":
            raise ValueError(f"Unsupported prototype relation type: {relation.relation_type}")
        self.domain_relations[relation.id] = relation

    def register_dependency_requirement(self, requirement: DependencyRequirementDefinition):
        if requirement.id in self.dependency_requirements:
            raise ValueError(f"Dependency requirement already registered: {requirement.id}")
        if requirement.mode not in {"all_of", "any_of"}:
            raise ValueError(f"Unsupported dependency requirement mode: {requirement.mode}")
        if not requirement.source_domain_ids:
            raise ValueError("Dependency requirement must contain at least one source domain")
        unknown=[d for d in requirement.source_domain_ids if d not in self.domains]
        if unknown:
            raise ValueError(f"Dependency requirement {requirement.id} references unregistered source domains: {unknown}")
        if requirement.target_domain_id not in self.domains:
            raise ValueError(requirement.target_domain_id)
        self.dependency_requirements[requirement.id] = requirement

    def register_governing_configuration(self, config: GoverningConfiguration):
        if self.governing_configuration is not None:
            raise ValueError("Governing configuration already registered")
        if config.epsilon_h < 0:
            raise ValueError("G epsilon_h must be nonnegative")
        self.governing_configuration=config

    def register_recovery_necessity(self, relation: RecoveryNecessityDefinition):
        if relation.id in self.recovery_necessities:
            raise ValueError(f"Recovery necessity already registered: {relation.id}")
        if relation.support_domain_id not in self.domains:
            raise ValueError(relation.support_domain_id)
        if relation.target_domain_id not in self.domains:
            raise ValueError(relation.target_domain_id)
        if relation.support_domain_id == relation.target_domain_id:
            raise ValueError("Recovery necessity must connect distinct domains")
        self.recovery_necessities[relation.id]=relation

    def register_regime_configuration(self, config: RegimeConfiguration):
        if self.regime_configuration is not None:
            raise ValueError("Regime configuration already registered")
        if not (config.tau_h_existential < config.tau_h_survival < config.tau_h_stabilization):
            raise ValueError("Regime horizon thresholds must satisfy existential < survival < stabilization")
        if not (config.tau_phi_existential > config.tau_phi_survival > config.tau_phi_stabilization):
            raise ValueError("Regime pressure thresholds must satisfy existential > survival > stabilization")
        if config.tau_m_survival < 2 or config.tau_m_stabilization < 2:
            raise ValueError("Regime multiplicity thresholds must be >= 2")
        if config.tau_m_survival < config.tau_m_stabilization:
            raise ValueError("Survival multiplicity threshold must be >= stabilization threshold")
        hms=config.tau_h_mult_survival if config.tau_h_mult_survival is not None else config.tau_h_survival
        hmst=config.tau_h_mult_stabilization if config.tau_h_mult_stabilization is not None else config.tau_h_stabilization
        if hms > config.tau_h_survival:
            raise ValueError("Survival multiplicity-compression threshold must be <= survival horizon threshold")
        if hmst > config.tau_h_stabilization:
            raise ValueError("Stabilization multiplicity-compression threshold must be <= stabilization horizon threshold")
        if config.delta_h_escalation < 0 or config.delta_h_deescalation < 0:
            raise ValueError("Regime hysteresis margins must be nonnegative")
        self.regime_configuration=config

    def regime_configuration_identity(self) -> str:
        """Deterministic integrity identity for the registered R thresholds."""
        if self.regime_configuration is None:
            return ""
        payload=asdict(self.regime_configuration)
        raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=repr).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def horizon_configuration_identity(self) -> str:
        """Deterministic integrity identity for the effective H configuration."""
        config=self.horizon_configuration or HorizonConfiguration()
        payload=asdict(config)
        raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=repr).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def register_horizon_configuration(self, config: HorizonConfiguration):
        if config.epsilon_deterioration <= 0:
            raise ValueError("H epsilon_deterioration must be positive")
        self.horizon_configuration=config

    def register_policy_seed(self, seed: PolicySeedDefinition):
        if seed.id in self.policy_seeds:
            raise ValueError(f"Policy seed already registered: {seed.id}")
        if seed.family not in {"continuation","local_adjustment","structural_shift","emergency_escape"}:
            raise ValueError(f"Unsupported canonical Pi family: {seed.family}")
        unknown_actions=[a for a in seed.action_ids if a not in self.actions]
        if unknown_actions:
            raise ValueError(f"Policy seed {seed.id} references unregistered actions: {unknown_actions}")
        unknown_domains=[d for d in seed.affected_domain_ids if d not in self.domains]
        if unknown_domains:
            raise ValueError(f"Policy seed {seed.id} references unregistered domains: {unknown_domains}")
        self.policy_seeds[seed.id]=seed

    def action_registry_identity(self) -> str:
        """Deterministic identity of registered action definitions; integrity token only."""
        def norm(value):
            if is_dataclass(value): return norm(asdict(value))
            if isinstance(value, dict): return {str(k): norm(v) for k,v in sorted(value.items(), key=lambda kv: str(kv[0]))}
            if isinstance(value, (tuple,list)): return [norm(v) for v in value]
            return value
        raw=json.dumps(norm(self.actions),sort_keys=True,separators=(",",":"),default=repr).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def graph_substrate_identity(self) -> str:
        """Deterministic identity of the registered substrate consumed by Graph.

        This is an integrity/version token, not semantic authority.  It changes
        when registered domains, graph instances, transformations, or
        compositions visible to construct_graph() change.
        """
        def norm(value):
            if is_dataclass(value):
                return norm(asdict(value))
            if isinstance(value, dict):
                return {str(k): norm(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
            if isinstance(value, (tuple, list)):
                return [norm(v) for v in value]
            if isinstance(value, set):
                return sorted(norm(v) for v in value)
            return value
        payload={
            "domains": norm(self.domains),
            "graph_instances": norm(self.graph_instances),
            "graph_transformations": norm(self.graph_transformations),
            "graph_compositions": norm(self.graph_compositions),
        }
        raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=repr).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def refresh_graph_reachability(self, request: GraphReachabilityRefreshRequest) -> GraphReachabilityRefreshAssessment:
        """Atomically refresh reachability for already-represented transformations.

        v0.101 deliberately does not perform structural admission. Unknown transformation
        ids fail closed; callers must use a separately governed admission path for novel
        structure. The expected substrate identity prevents a stale observation batch from
        silently overwriting a newer registered Graph substrate.
        """
        prior=self.graph_substrate_identity()
        violations=[]
        if not request.refresh_id.strip(): violations.append("refresh_id must be explicit")
        if not request.expected_graph_substrate_identity.strip(): violations.append("expected Graph substrate identity must be explicit")
        elif request.expected_graph_substrate_identity != prior: violations.append("registered Graph substrate identity changed before reachability refresh")
        if not request.observations: violations.append("reachability refresh requires at least one observation")
        seen=set()
        for obs in request.observations:
            if obs.transformation_id in seen: violations.append(f"duplicate reachability observation: {obs.transformation_id}")
            seen.add(obs.transformation_id)
            if obs.transformation_id not in self.graph_transformations: violations.append(f"unrepresented Graph transformation cannot be refreshed: {obs.transformation_id}")
            if obs.reachability_status not in {"reachable","unreachable","uncertain"}: violations.append(f"invalid reachability status for {obs.transformation_id}: {obs.reachability_status}")
            if obs.reachability_status == "uncertain" and not obs.uncertainty_note.strip(): violations.append(f"uncertain reachability requires uncertainty_note: {obs.transformation_id}")
            if not obs.source_id.strip(): violations.append(f"reachability source_id must be explicit: {obs.transformation_id}")
            if not obs.provenance_id.strip(): violations.append(f"reachability provenance_id must be explicit: {obs.transformation_id}")
        if violations:
            return GraphReachabilityRefreshAssessment("REJECTED",request.refresh_id,prior,violations=tuple(violations),notes=("no Graph registry mutation occurred",))
        changed=[]; unchanged=[]
        for obs in request.observations:
            old=self.graph_transformations[obs.transformation_id]
            if old.reachability_status == obs.reachability_status and old.uncertainty_note == obs.uncertainty_note:
                unchanged.append(obs.transformation_id); continue
            metadata=dict(old.metadata)
            metadata["reachability_refresh"]={"refresh_id":request.refresh_id,"observed_at":obs.observed_at,"source_id":obs.source_id,"provenance_id":obs.provenance_id,"evidence":dict(obs.evidence)}
            self.graph_transformations[obs.transformation_id]=replace(old,reachability_status=obs.reachability_status,uncertainty_note=obs.uncertainty_note if obs.reachability_status=="uncertain" else "",metadata=metadata)
            changed.append(obs.transformation_id)
        result=self.graph_substrate_identity()
        return GraphReachabilityRefreshAssessment("APPLIED",request.refresh_id,prior,result,tuple(changed),tuple(unchanged),notes=("reachability refresh changed represented state of registered Graph structure only; no structural admission occurred",))

    def admit_novel_function(self, request: NovelFunctionAdmissionRequest) -> NovelFunctionAdmissionAssessment:
        """Atomically admit one explicit new action/function and its first represented Graph transformation.

        This is configuration admission, not discovery, authorization, or execution.  The host supplies
        complete semantics and provenance; the runtime never invents a function from observed behavior.
        """
        prior_a=self.action_registry_identity(); prior_g=self.graph_substrate_identity(); violations=[]
        a=request.action; tr=request.transformation
        if not request.admission_id.strip(): violations.append("admission_id must be explicit")
        if request.expected_action_registry_identity != prior_a: violations.append("registered action identity changed before novel-function admission")
        if request.expected_graph_substrate_identity != prior_g: violations.append("registered Graph substrate identity changed before novel-function admission")
        for name,value in (("configuration_version",request.configuration_version),("source_id",request.source_id),("provenance_id",request.provenance_id),("rationale",request.rationale)):
            if not value.strip(): violations.append(f"{name} must be explicit")
        if not a.id.strip(): violations.append("action id must be explicit")
        if a.id in self.actions: violations.append(f"Action already registered: {a.id}")
        unknown=[d for d in a.domains if d not in self.domains]
        if unknown: violations.append(f"Action {a.id} references unregistered domains: {unknown}")
        if tr.action_id != a.id: violations.append("novel transformation must reference the action admitted in the same request")
        if tr.id in self.graph_transformations: violations.append(f"Graph transformation already represented: {tr.id}")
        if tr.family not in {"continuation","maintenance_local_adjustment","corrective_repair","structural_reconfiguration","exit_transfer_liquidation","substitution","release_restructuring","escape_emergency"}: violations.append(f"unsupported graph transformation family: {tr.family}")
        if tr.reachability_status not in {"reachable","unreachable","uncertain"}: violations.append("reachability_status must be reachable, unreachable, or uncertain")
        if tr.reachability_status == "uncertain" and not tr.uncertainty_note.strip(): violations.append("uncertain graph reachability requires an explicit uncertainty_note")
        if tr.source_instance_id not in self.graph_instances or tr.destination_instance_id not in self.graph_instances: violations.append(f"Graph transformation {tr.id} references unregistered instances")
        unknown_tr=[d for d in tr.affected_domain_ids if d not in self.domains]
        if unknown_tr: violations.append(f"Graph transformation {tr.id} references unregistered domains: {unknown_tr}")
        if violations:
            return NovelFunctionAdmissionAssessment("REJECTED",request.admission_id,prior_a,prior_g,violations=tuple(violations),notes=("atomic admission rejected; neither action nor Graph transformation was mutated",))
        stamp={"admission_id":request.admission_id,"configuration_version":request.configuration_version,"source_id":request.source_id,"provenance_id":request.provenance_id,"rationale":request.rationale,"evidence":dict(request.evidence)}
        am=dict(a.metadata); am["novel_function_admission"]=stamp
        tm=dict(tr.metadata); tm["novel_function_admission"]=stamp
        self.actions[a.id]=replace(a,metadata=am)
        self.graph_transformations[tr.id]=replace(tr,metadata=tm)
        return NovelFunctionAdmissionAssessment("ADMITTED",request.admission_id,prior_a,prior_g,self.action_registry_identity(),self.graph_substrate_identity(),a.id,tr.id,request.configuration_version,request.source_id,request.provenance_id,notes=("explicit atomic configuration admission only; no Sigma, epsilon, or execution authority is implied",))

    def admit_recovery_necessity(self, request: RecoveryNecessityAdmissionRequest) -> RecoveryNecessityAdmissionAssessment:
        """Atomically admit one explicit recovery-necessity relation as a governed configuration change."""
        prior=self.governing_substrate_identity(); violations=[]; rel=request.relation
        if not request.admission_id.strip(): violations.append("admission_id must be explicit")
        if request.expected_governing_substrate_identity != prior: violations.append("governing substrate identity changed before recovery-necessity admission")
        for name,value in (("configuration_version",request.configuration_version),("source_id",request.source_id),("provenance_id",request.provenance_id),("rationale",request.rationale)):
            if not value.strip(): violations.append(f"{name} must be explicit")
        if not rel.id.strip(): violations.append("recovery necessity id must be explicit")
        if rel.id in self.recovery_necessities: violations.append(f"Recovery necessity already registered: {rel.id}")
        if rel.support_domain_id not in self.domains: violations.append(f"unregistered support domain: {rel.support_domain_id}")
        if rel.target_domain_id not in self.domains: violations.append(f"unregistered target domain: {rel.target_domain_id}")
        if rel.support_domain_id == rel.target_domain_id: violations.append("recovery necessity must connect distinct domains")
        if not rel.basis.strip(): violations.append("recovery necessity basis must be explicit")
        if violations:
            return RecoveryNecessityAdmissionAssessment("REJECTED",request.admission_id,prior,violations=tuple(violations),notes=("admission rejected; governing dependency topology was not mutated",))
        stamp=(f"admission_id={request.admission_id}",f"configuration_version={request.configuration_version}",f"source_id={request.source_id}",f"provenance_id={request.provenance_id}",f"rationale={request.rationale}")
        self.recovery_necessities[rel.id]=replace(rel,notes=tuple(rel.notes)+stamp)
        return RecoveryNecessityAdmissionAssessment("ADMITTED",request.admission_id,prior,self.governing_substrate_identity(),rel.id,request.configuration_version,request.source_id,request.provenance_id,notes=("explicit add-only governing dependency admission; no selection or execution authority is implied",))

    def revise_recovery_necessity(self, request: RecoveryNecessityRevisionRequest) -> RecoveryNecessityRevisionAssessment:
        """Atomically replace or remove one existing recovery-necessity relation.

        Revision is explicit governed configuration change, never inference.  A replacement keeps
        the same relation identity so revision cannot silently substitute a different structural object.
        """
        prior=self.governing_substrate_identity(); violations=[]
        if not request.revision_id.strip(): violations.append("revision_id must be explicit")
        if request.expected_governing_substrate_identity != prior: violations.append("governing substrate identity changed before recovery-necessity revision")
        if request.operation not in {"replace","remove"}: violations.append("operation must be replace or remove")
        for name,value in (("relation_id",request.relation_id),("configuration_version",request.configuration_version),("source_id",request.source_id),("provenance_id",request.provenance_id),("rationale",request.rationale)):
            if not value.strip(): violations.append(f"{name} must be explicit")
        if request.relation_id not in self.recovery_necessities: violations.append(f"Recovery necessity not registered: {request.relation_id}")
        repl=request.replacement
        if request.operation == "remove" and repl is not None: violations.append("remove operation must not provide a replacement")
        if request.operation == "replace":
            if repl is None: violations.append("replace operation requires a replacement")
            else:
                if repl.id != request.relation_id: violations.append("replacement must preserve the registered recovery-necessity id")
                if repl.support_domain_id not in self.domains: violations.append(f"unregistered support domain: {repl.support_domain_id}")
                if repl.target_domain_id not in self.domains: violations.append(f"unregistered target domain: {repl.target_domain_id}")
                if repl.support_domain_id == repl.target_domain_id: violations.append("recovery necessity must connect distinct domains")
                if not repl.basis.strip(): violations.append("recovery necessity basis must be explicit")
        if violations:
            return RecoveryNecessityRevisionAssessment("REJECTED",request.revision_id,request.operation,prior,violations=tuple(violations),notes=("revision rejected; governing dependency topology was not mutated",))
        if request.operation == "remove":
            del self.recovery_necessities[request.relation_id]
        else:
            stamp=(f"revision_id={request.revision_id}",f"configuration_version={request.configuration_version}",f"source_id={request.source_id}",f"provenance_id={request.provenance_id}",f"rationale={request.rationale}")
            self.recovery_necessities[request.relation_id]=replace(repl,notes=tuple(repl.notes)+stamp)
        return RecoveryNecessityRevisionAssessment("REVISED",request.revision_id,request.operation,prior,self.governing_substrate_identity(),request.relation_id,request.configuration_version,request.source_id,request.provenance_id,notes=("explicit governed topology revision only; no selection or execution authority is implied",))

    def admit_graph_transformation(self, request: GraphTransformationAdmissionRequest) -> GraphTransformationAdmissionAssessment:
        """Explicitly admit one new Graph transformation as a versioned configuration change.

        This is not discovery and not authorization to execute the consequential function.
        The caller must provide the complete typed definition, provenance, rationale, and an
        exact expected substrate identity. Existing registration validation remains authoritative.
        """
        prior=self.graph_substrate_identity()
        violations=[]
        tr=request.transformation
        if not request.admission_id.strip(): violations.append("admission_id must be explicit")
        if not request.expected_graph_substrate_identity.strip(): violations.append("expected Graph substrate identity must be explicit")
        elif request.expected_graph_substrate_identity != prior: violations.append("registered Graph substrate identity changed before structural admission")
        if not request.configuration_version.strip(): violations.append("configuration_version must be explicit")
        if not request.source_id.strip(): violations.append("admission source_id must be explicit")
        if not request.provenance_id.strip(): violations.append("admission provenance_id must be explicit")
        if not request.rationale.strip(): violations.append("admission rationale must be explicit")
        if tr.id in self.graph_transformations: violations.append(f"Graph transformation already represented: {tr.id}")
        if tr.family not in {"continuation","maintenance_local_adjustment","corrective_repair","structural_reconfiguration","exit_transfer_liquidation","substitution","release_restructuring","escape_emergency"}: violations.append(f"unsupported graph transformation family: {tr.family}")
        if tr.reachability_status not in {"reachable","unreachable","uncertain"}: violations.append("reachability_status must be reachable, unreachable, or uncertain")
        if tr.reachability_status == "uncertain" and not tr.uncertainty_note.strip(): violations.append("uncertain graph reachability requires an explicit uncertainty_note")
        if tr.source_instance_id not in self.graph_instances or tr.destination_instance_id not in self.graph_instances: violations.append(f"Graph transformation {tr.id} references unregistered instances")
        if tr.action_id not in self.actions: violations.append(f"Graph transformation {tr.id} references unregistered action {tr.action_id}")
        unknown=[d for d in tr.affected_domain_ids if d not in self.domains]
        if unknown: violations.append(f"Graph transformation {tr.id} references unregistered domains: {unknown}")
        if violations:
            return GraphTransformationAdmissionAssessment("REJECTED",request.admission_id,prior,violations=tuple(violations),notes=("no Graph registry mutation occurred",))
        metadata=dict(tr.metadata)
        metadata["structural_admission"]={"admission_id":request.admission_id,"configuration_version":request.configuration_version,"source_id":request.source_id,"provenance_id":request.provenance_id,"rationale":request.rationale,"evidence":dict(request.evidence)}
        admitted=replace(tr,metadata=metadata)
        self.graph_transformations[admitted.id]=admitted
        result=self.graph_substrate_identity()
        return GraphTransformationAdmissionAssessment("ADMITTED",request.admission_id,prior,result,admitted.id,request.configuration_version,request.source_id,request.provenance_id,notes=("explicit structural admission only; no execution authority or Sigma selection is implied",))

    def revise_graph_transformation(self, request: GraphTransformationRevisionRequest) -> GraphTransformationRevisionAssessment:
        """Atomically replace or remove one already-represented Graph transformation.

        This is governed configuration lifecycle, not reachability refresh, semantic discovery,
        selection, or execution. A replacement must preserve the registered transformation id.
        """
        prior=self.graph_substrate_identity(); violations=[]
        if not request.revision_id.strip(): violations.append("revision_id must be explicit")
        if request.expected_graph_substrate_identity != prior: violations.append("registered Graph substrate identity changed before structural revision")
        if request.operation not in {"replace","remove"}: violations.append("operation must be replace or remove")
        for name,value in (("transformation_id",request.transformation_id),("configuration_version",request.configuration_version),("source_id",request.source_id),("provenance_id",request.provenance_id),("rationale",request.rationale)):
            if not value.strip(): violations.append(f"{name} must be explicit")
        if request.transformation_id not in self.graph_transformations: violations.append(f"Graph transformation not represented: {request.transformation_id}")
        repl=request.replacement
        if request.operation == "remove" and repl is not None: violations.append("remove operation must not provide a replacement")
        if request.operation == "replace":
            if repl is None: violations.append("replace operation requires a replacement")
            else:
                if repl.id != request.transformation_id: violations.append("replacement must preserve the registered Graph transformation id")
                if repl.family not in {"continuation","maintenance_local_adjustment","corrective_repair","structural_reconfiguration","exit_transfer_liquidation","substitution","release_restructuring","escape_emergency"}: violations.append(f"unsupported graph transformation family: {repl.family}")
                if repl.reachability_status not in {"reachable","unreachable","uncertain"}: violations.append("reachability_status must be reachable, unreachable, or uncertain")
                if repl.reachability_status == "uncertain" and not repl.uncertainty_note.strip(): violations.append("uncertain graph reachability requires an explicit uncertainty_note")
                if repl.source_instance_id not in self.graph_instances or repl.destination_instance_id not in self.graph_instances: violations.append(f"Graph transformation {repl.id} references unregistered instances")
                if repl.action_id not in self.actions: violations.append(f"Graph transformation {repl.id} references unregistered action {repl.action_id}")
                unknown=[d for d in repl.affected_domain_ids if d not in self.domains]
                if unknown: violations.append(f"Graph transformation {repl.id} references unregistered domains: {unknown}")
        if violations:
            return GraphTransformationRevisionAssessment("REJECTED",request.revision_id,request.operation,prior,violations=tuple(violations),notes=("revision rejected; represented Graph structure was not mutated",))
        if request.operation == "remove":
            del self.graph_transformations[request.transformation_id]
        else:
            metadata=dict(repl.metadata)
            metadata["structural_revision"]={"revision_id":request.revision_id,"configuration_version":request.configuration_version,"source_id":request.source_id,"provenance_id":request.provenance_id,"rationale":request.rationale,"evidence":dict(request.evidence)}
            self.graph_transformations[request.transformation_id]=replace(repl,metadata=metadata)
        return GraphTransformationRevisionAssessment("REVISED",request.revision_id,request.operation,prior,self.graph_substrate_identity(),request.transformation_id,request.configuration_version,request.source_id,request.provenance_id,notes=("explicit represented-Graph lifecycle change only; no selection or execution authority is implied",))

    def register_graph_instance(self, instance: GraphInstanceDefinition):
        if instance.id in self.graph_instances:
            raise ValueError(f"Graph instance already registered: {instance.id}")
        unknown=[d for d in instance.domain_ids if d not in self.domains]
        if unknown:
            raise ValueError(f"Graph instance {instance.id} references unregistered domains: {unknown}")
        self.graph_instances[instance.id]=instance

    def register_graph_transformation(self, transformation: GraphTransformationDefinition):
        if transformation.id in self.graph_transformations:
            raise ValueError(f"Graph transformation already registered: {transformation.id}")
        if transformation.family not in {"continuation","maintenance_local_adjustment","corrective_repair","structural_reconfiguration","exit_transfer_liquidation","substitution","release_restructuring","escape_emergency"}:
            raise ValueError(f"Unsupported graph transformation family: {transformation.family}")
        if transformation.reachability_status not in {"reachable","unreachable","uncertain"}:
            raise ValueError("reachability_status must be reachable, unreachable, or uncertain")
        if transformation.reachability_status == "uncertain" and not transformation.uncertainty_note.strip():
            raise ValueError("uncertain graph reachability requires an explicit uncertainty_note")
        if transformation.source_instance_id not in self.graph_instances or transformation.destination_instance_id not in self.graph_instances:
            raise ValueError(f"Graph transformation {transformation.id} references unregistered instances")
        if transformation.action_id not in self.actions:
            raise ValueError(f"Graph transformation {transformation.id} references unregistered action {transformation.action_id}")
        unknown=[d for d in transformation.affected_domain_ids if d not in self.domains]
        if unknown:
            raise ValueError(f"Graph transformation {transformation.id} references unregistered domains: {unknown}")
        self.graph_transformations[transformation.id]=transformation

    def register_graph_composition(self, composition: GraphCompositionDefinition):
        if composition.id in self.graph_compositions:
            raise ValueError(f"Graph composition already registered: {composition.id}")
        unknown=[t for t in composition.transformation_ids if t not in self.graph_transformations]
        if unknown:
            raise ValueError(f"Graph composition {composition.id} references unregistered transformations: {unknown}")
        self.graph_compositions[composition.id]=composition

    def register_fallback_configuration(self, config: FallbackConfiguration):
        if self.fallback_configuration is not None:
            raise ValueError("Fallback configuration already registered")
        if not (0.0 < float(config.alpha_base) < 1.0):
            raise ValueError("fallback alpha_base must lie strictly in (0,1)")
        self.fallback_configuration=config

    def register_sigma_order(self, definition: SigmaOrderDefinition):
        if definition.policy_id in self.sigma_order:
            raise ValueError(f"Sigma order already registered for policy: {definition.policy_id}")
        if definition.order_index in self.sigma_order_indices:
            raise ValueError(f"Sigma order index already registered: {definition.order_index}")
        self.sigma_order[definition.policy_id]=definition
        self.sigma_order_indices[definition.order_index]=definition.policy_id

    def register_constraint_rule(self, rule: ConstraintRuleDefinition):
        if rule.id in self.constraint_rules:
            raise ValueError(f"Constraint rule already registered: {rule.id}")
        if rule.constraint_class not in {"hard","conditional","soft"}:
            raise ValueError(f"Unsupported constraint class: {rule.constraint_class}")
        if rule.constraint_class == "conditional" and not rule.conditional_class.strip():
            raise ValueError("Conditional constraint rules require conditional_class")
        if rule.constraint_class != "conditional" and rule.conditional_class:
            raise ValueError("Only conditional constraints may declare conditional_class")
        self.constraint_rules[rule.id]=rule

    def governing_substrate_identity(self) -> str:
        """Deterministic integrity identity for the registered structural facts consumed by G."""
        payload={
            "domains": [asdict(self.domains[k]) if is_dataclass(self.domains[k]) else repr(self.domains[k]) for k in sorted(self.domains)],
            "governing_configuration": asdict(self.governing_configuration) if self.governing_configuration is not None else asdict(GoverningConfiguration()),
            "recovery_necessities": [asdict(self.recovery_necessities[k]) if is_dataclass(self.recovery_necessities[k]) else repr(self.recovery_necessities[k]) for k in sorted(self.recovery_necessities)],
        }
        raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=repr).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def phi_substrate_identity(self) -> str:
        """Deterministic integrity identity for registered domain definitions consumed by Phi."""
        payload=[]
        for did,d in sorted(self.domains.items()):
            payload.append((did,asdict(d) if is_dataclass(d) else repr(d)))
        raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=repr).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def assess_graph_structural_coverage(self, observation: GraphStructuralCoverageObservation) -> GraphStructuralCoverageAssessment:
        """Qualify explicit structural-coverage evidence against the exact current Graph substrate.

        This method neither infers missing semantics nor mutates/admit Graph structure.  It keeps
        model-coverage uncertainty distinct from ordinary reachability/projection uncertainty.
        """
        current=self.graph_substrate_identity()
        violations=[]
        if not observation.observation_id.strip(): violations.append("structural coverage observation_id must be explicit")
        if not observation.expected_graph_substrate_identity.strip(): violations.append("expected Graph substrate identity must be explicit")
        elif observation.expected_graph_substrate_identity != current: violations.append("registered Graph substrate identity changed before structural coverage assessment")
        if observation.coverage_status not in {"sufficient","incomplete","uncertain"}: violations.append("coverage_status must be sufficient, incomplete, or uncertain")
        if not observation.source_id.strip(): violations.append("structural coverage source_id must be explicit")
        if not observation.provenance_id.strip(): violations.append("structural coverage provenance_id must be explicit")
        groups=(observation.missing_family_ids,observation.missing_path_class_ids,observation.missing_composition_ids,observation.uncertainty_markers)
        if any(len(x)!=len(set(x)) for x in groups): violations.append("structural coverage evidence identities must be unique within each category")
        gaps=bool(observation.missing_family_ids or observation.missing_path_class_ids or observation.missing_composition_ids)
        uncertain=bool(observation.uncertainty_markers)
        if observation.coverage_status=="sufficient" and (gaps or uncertain): violations.append("sufficient structural coverage cannot declare material gaps or uncertainty markers")
        if observation.coverage_status=="incomplete" and not gaps: violations.append("incomplete structural coverage requires at least one explicit missing family, path class, or composition")
        if observation.coverage_status=="uncertain" and not uncertain: violations.append("uncertain structural coverage requires at least one explicit uncertainty marker")
        if observation.coverage_status=="uncertain" and gaps: violations.append("known missing structure must be reported as incomplete rather than only uncertain")
        if violations:
            return GraphStructuralCoverageAssessment(False,observation.observation_id,current,observation.coverage_status,False,False,False,violations=tuple(violations),notes=("no Graph registry mutation or governance authority was created",))
        return GraphStructuralCoverageAssessment(
            True,observation.observation_id,current,observation.coverage_status,
            observation.coverage_status=="sufficient",observation.coverage_status=="incomplete",observation.coverage_status=="uncertain",
            tuple(observation.missing_family_ids),tuple(observation.missing_path_class_ids),tuple(observation.missing_composition_ids),tuple(observation.uncertainty_markers),
            observation.source_id,observation.provenance_id,(),
            ("structural coverage is qualified separately from ordinary projection/reachability uncertainty",
             "assessment performs no discovery, structural admission, Graph mutation, or governance re-entry")
        )
