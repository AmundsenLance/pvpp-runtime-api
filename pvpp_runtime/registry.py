from __future__ import annotations
from .models import DomainDefinition, ProductivePowerDefinition, ActionDefinition, RecoveryPlanDefinition, DomainRelationDefinition, DependencyRequirementDefinition, RegimeConfiguration, GoverningConfiguration, RecoveryNecessityDefinition, HorizonConfiguration, PolicySeedDefinition, SigmaOrderDefinition, ConstraintRuleDefinition, FallbackConfiguration

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
