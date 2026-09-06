from __future__ import annotations
import math
from dataclasses import replace
from itertools import combinations
from collections import deque
from .models import (PVPPAssessment, PressureFactors, PressureDomainResult, PressureFieldAssessment, PressureInvariantAssessment, HorizonConfiguration, HorizonDomainResult, HorizonAssessment, DomainAssessment, ActionEvaluation, WorldState, ActiveRecoveryCorridor, ExecutionResult,
    CapacityCalendar, CorridorFeasibilityReport, JointRecoveryFeasibilityAssessment, JointRecoveryExecutionBindingAssessment, RecoveryAdequacyAssessment, SelectedPolicy, DiscretionarySelectionAssessment,
    PreliminaryPreservationObject, GraphInstanceDefinition, GraphTransformationDefinition, GraphCompositionDefinition, GraphConstructionConfig, GraphConstructionAssessment, PolicySeedDefinition, PiConstructionConfig, PiConstructionAssessment, CandidatePolicySet, CandidatePolicySpace, PiCompletenessAssessment, EpistemicSubstrateQualification, QualifiedPiCompletenessAssessment, RecoveryCorridorProjection, PolicyProjectionRecord, ProjectionInformationQualityClaim, ProjectionRequest, ProjectionConsistencyAudit, CycleArtifactIntegrityAssessment, ProjectionCausalStateInput, ProjectionInputLicenseAssessment, ProjectionModelAuthority, ProjectionModelAuthorityAssessment, DomainAdequacyResult, PolicyAdequacyResult, AdequacyAssessment, FallbackConfiguration, FallbackStructuralProfile, SigmaFallbackAssessment, SigmaStageAssessment, SigmaAssessment, SigmaTerminalAssessment, GoverningConfiguration, GoverningAssessment, RegimeAssessment, PreviousRegimeState, ConstraintRuleDefinition, ConstraintObservation, PolicyConstraintProfile, ConstraintViolationProfile, ConstraintAssessment, ConstraintsAssessment, DomainFrame, DomainFramingAssessment, PolicySetEvaluation, CanonicalDecisionCycleRequest, CanonicalDecisionCycleAssessment, PolicySelectionAssessment, StructuralPolicyAssessment, ActionProjection, ExecutionLicenseEnvelope, ExecutionObservation, ExecutionTraceNode, ExecutionEpisode, EpsilonStepResult, Layer1TransitionHandoff, RecoveryActionConfirmation, Layer1ExecutionCommit, ExecutionBookkeepingAssessment, ActualPersistentStateEnvelope, Layer1TransitionResult, Layer1TransitionValidationAssessment, ExecutionTransitionProvenance, ExecutionTransitionProvenanceAssessment, CanonicalCycleSnapshot, CanonicalIntegratedCycleResult, CanonicalCycleDirective, CanonicalCycleLedgerEntry, CanonicalCycleSequenceAssessment, MemoryStateReference, RetrievalQualityMetadata, MemoryRetrievalRequest, MemoryRetrievalPackage, ExpectationStateReference, MemoryConditionedCycleSnapshot, PostExecutionEpistemicUpdateRequest, PostExecutionEpistemicUpdateResult, EpistemicUpdateValidationAssessment, MemoryConditionedIntegratedCycleResult, MemoryConditionedCycleDirective, MemoryConditionedCycleLedgerEntry, MemoryConditionedCycleSequenceAssessment, CapacityAuthorityRequest, CapacityAuthorityEnvelope, CapacityAuthorityValidationAssessment, PredictionErrorComponent, PredictionErrorRequest, PredictionErrorAssessment, PredictionErrorValidationAssessment, PerceivedDecisionState, PerceivedDecisionStateValidationAssessment, CrossObjectExecutionIdentityAssessment, IntegratedCycleLifecycleIntegrityAssessment)
from .registry import PVPPRegistry
from .interfaces import WorldAdapter, PolicyProjectionService, Layer1TransitionService, MemoryRetrievalService, EpistemicUpdateService, CapacityAuthorityService, PredictionErrorService
from .operators.prototype import pressure_from_margin, collapse_horizon, governing_from_horizon, dependency_close, regime_label
from .feasibility import assess_joint_feasibility

PIPELINE=("PPP","Phi","H","G","R","Graph/Seed","Pi","Pi Completeness","Constraints","Domain Framing","Adequacy","Sigma","epsilon")

class PVPPRuntime:
    def __init__(self, registry: PVPPRegistry, world: WorldAdapter, projection_service: PolicyProjectionService | None = None, layer1_transition_service: Layer1TransitionService | None = None, memory_retrieval_service: MemoryRetrievalService | None = None, epistemic_update_service: EpistemicUpdateService | None = None, capacity_authority_service: CapacityAuthorityService | None = None, prediction_error_service: PredictionErrorService | None = None):
        self.registry=registry; self.world=world; self.projection_service=projection_service; self.layer1_transition_service=layer1_transition_service; self.memory_retrieval_service=memory_retrieval_service; self.epistemic_update_service=epistemic_update_service; self.capacity_authority_service=capacity_authority_service; self.prediction_error_service=prediction_error_service; self.active_corridors={}
        if "steady" not in registry.actions: raise ValueError("registered steady action required")
    def _baseline_drift(self,state,did):
        p=self.world.project(state,self.registry.actions["steady"])
        if not p.feasible: raise RuntimeError("steady must be projectable")
        return self.world.domain_value(p.next_state,did)-self.world.domain_value(state,did)
    def _strict_phi_h_available(self):
        return all(callable(getattr(self.world,name,None)) for name in (
            "pressure_factors","pressure_value","expected_deterioration"
        ))

    def _baseline_continuation(self, perceived):
        baseline=self.world.project(perceived,self.registry.actions["steady"])
        if not baseline.feasible:
            raise RuntimeError("steady must be projectable")
        return baseline.next_state

    def _evaluate_phi_from_perceived(self, perceived, baseline_state):
        results=[]
        for did,d in self.registry.domains.items():
            value=float(self.world.domain_value(perceived,did))
            drift=float(self.world.domain_value(baseline_state,did))-value
            factors=self.world.pressure_factors(perceived,did,drift)
            if factors.domain_id != did:
                raise ValueError(f"Phi factors domain mismatch: expected {did}, got {factors.domain_id}")
            expected_margin=value-float(d.threshold)
            if not math.isclose(float(factors.margin),expected_margin,rel_tol=1e-12,abs_tol=1e-12):
                raise ValueError(
                    f"Phi margin for {did} must equal perceived value minus viability boundary"
                )
            pressure=float(self.world.pressure_value(did,factors))
            if math.isnan(pressure):
                raise ValueError(f"Phi pressure for {did} may not be NaN")
            results.append(PressureDomainResult(
                did,factors,pressure,
                ("pressure is represented corrective demand, not governing force",)
            ))
        return PressureFieldAssessment(
            tuple(results),
            ("Phi remains domain-structured and non-scalar",
             "the host/domain mapping supplies f_k; the runtime does not invent fixed coefficients",
             "Phi performs no horizon, governing-set, regime, adequacy, or selection logic")
        )

    def evaluate_pressure_field(self, state) -> PressureFieldAssessment:
        """Strict Phi using host/domain-sensitive f_k semantics."""
        if not all(callable(getattr(self.world,name,None)) for name in ("pressure_factors","pressure_value")):
            raise ValueError("strict Phi requires host pressure_factors() and pressure_value()")
        perceived=self.world.perceive(state)
        baseline_state=self._baseline_continuation(perceived)
        return self._evaluate_phi_from_perceived(perceived,baseline_state)

    def validate_pressure_invariants(self, domain_id: str, reference_factors: PressureFactors,
                                     margins) -> PressureInvariantAssessment:
        """Probe monotonic compression while all non-margin Phi inputs are held fixed.

        The caller supplies meaningful domain-scale margins. This avoids inventing
        a universal probe scale for domain-sensitive pressure mappings.
        """
        if domain_id not in self.registry.domains:
            raise ValueError(f"unknown domain: {domain_id}")
        if reference_factors.domain_id != domain_id:
            raise ValueError("reference pressure factors domain mismatch")
        mapper=getattr(self.world,"pressure_value",None)
        if not callable(mapper):
            raise ValueError("pressure invariant validation requires host pressure_value()")
        ms=tuple(float(m) for m in margins)
        if len(ms)<2:
            raise ValueError("pressure invariant validation requires at least two margins")
        if any(math.isnan(m) for m in ms):
            raise ValueError("pressure invariant margins may not contain NaN")
        # Evaluate farther -> nearer so canonical monotonic compression means
        # pressure must be non-decreasing along the ordered probe sequence.
        ordered=tuple(sorted(ms,reverse=True))
        ps=[]
        violations=[]
        for m in ordered:
            p=float(mapper(domain_id,replace(reference_factors,margin=m)))
            if math.isnan(p):
                violations.append(f"NaN pressure at margin {m}")
            ps.append(p)
        for (m_far,p_far),(m_near,p_near) in zip(zip(ordered,ps),zip(ordered[1:],ps[1:])):
            if p_near < p_far:
                violations.append(
                    f"monotonic compression violated: margin {m_near} produced {p_near} < {p_far} at farther margin {m_far}"
                )
        positives=[(m,p) for m,p in zip(ordered,ps) if m>0]
        if len(positives)>=2:
            # Because positive margins are already farther -> nearer, the last
            # pair is the closest supplied approach to 0+.
            (m_far,p_far),(m_near,p_near)=positives[-2],positives[-1]
            if p_near < p_far:
                violations.append("near-threshold non-decreasing approach violated")
        return PressureInvariantAssessment(
            domain_id,not violations,ordered,tuple(ps),tuple(violations),
            ("only margin varies across probes; trajectory, shock, persistence, propagation, and context are held fixed",
             "probe margins are supplied by the integration because Phi is domain-sensitive")
        )

    def _evaluate_h_from_perceived(self, perceived, baseline_state, phi: PressureFieldAssessment):
        cfg=self.registry.horizon_configuration or HorizonConfiguration()
        if cfg.epsilon_deterioration <= 0:
            raise ValueError("H epsilon_deterioration must be positive")
        pressure_by={r.domain_id:r for r in phi.domain_results}
        results=[]
        for did,d in self.registry.domains.items():
            value=float(self.world.domain_value(perceived,did))
            margin=value-float(d.threshold)
            baseline_drift=float(self.world.domain_value(baseline_state,did))-value
            if did not in pressure_by:
                raise ValueError(f"H requires Phi result for every active domain; missing {did}")
            pr=pressure_by[did]
            expected=float(self.world.expected_deterioration(
                perceived,did,baseline_drift,pr.pressure,pr.factors
            ))
            if math.isnan(expected):
                raise ValueError(f"H expected deterioration for {did} may not be NaN")
            if margin <= 0:
                horizon=0.0
            else:
                horizon=margin/max(cfg.epsilon_deterioration,-expected)
            results.append(HorizonDomainResult(did,margin,expected,float(horizon)))
        return HorizonAssessment(
            tuple(results),
            ("H consumes Phi through expected deterioration rather than modifying perceived state",
             "H outputs baseline time-to-failure only",
             "H performs no governing-set, regime, adequacy, or policy-selection logic")
        )

    def evaluate_collapse_horizons(self, state, pressure_field: PressureFieldAssessment | None = None) -> HorizonAssessment:
        """Strict canonical H over baseline continuation."""
        if not callable(getattr(self.world,"expected_deterioration",None)):
            raise ValueError("strict H requires host expected_deterioration()")
        perceived=self.world.perceive(state)
        baseline_state=self._baseline_continuation(perceived)
        phi=pressure_field or self._evaluate_phi_from_perceived(perceived,baseline_state)
        return self._evaluate_h_from_perceived(perceived,baseline_state,phi)

    def _assess_domains(self,state):
        perceived=self.world.perceive(state); hs={}; init=set(); out={}
        baseline_state=self._baseline_continuation(perceived)

        if self._strict_phi_h_available():
            cfg=self.registry.horizon_configuration or HorizonConfiguration()
            pressures={}
            values={}
            # Streaming Φ -> H evaluation avoids materializing two full typed
            # intermediate vectors on the hot ordinary assessment path. Public
            # evaluate_pressure_field/evaluate_collapse_horizons still expose them.
            for did,d in self.registry.domains.items():
                v=float(self.world.domain_value(perceived,did)); values[did]=v
                drift=float(self.world.domain_value(baseline_state,did))-v
                factors=self.world.pressure_factors(perceived,did,drift)
                if factors.domain_id != did:
                    raise ValueError(f"Phi factors domain mismatch: expected {did}, got {factors.domain_id}")
                margin=v-float(d.threshold)
                if not math.isclose(float(factors.margin),margin,rel_tol=1e-12,abs_tol=1e-12):
                    raise ValueError(f"Phi margin for {did} must equal perceived value minus viability boundary")
                pressure=float(self.world.pressure_value(did,factors))
                if math.isnan(pressure):
                    raise ValueError(f"Phi pressure for {did} may not be NaN")
                pressures[did]=pressure
                expected=float(self.world.expected_deterioration(
                    perceived,did,drift,pressure,factors
                ))
                if math.isnan(expected):
                    raise ValueError(f"H expected deterioration for {did} may not be NaN")
                hs[did]=0.0 if margin <= 0 else margin/max(cfg.epsilon_deterioration,-expected)
            if self.registry.governing_configuration is not None or self.registry.recovery_necessities:
                gov=set(self.identify_governing_domains(hs).governing_domain_ids)
            else:
                for did,d in self.registry.domains.items():
                    if governing_from_horizon(hs[did],d):
                        init.add(did)
                gov=dependency_close(init,self.registry.domains)
            for did,d in self.registry.domains.items():
                out[did]=DomainAssessment(did,values[did],pressures[did],hs[did],did in gov,d.threshold)
            return perceived,out,hs,gov

        # Compatibility-only pre-v0.28 Phi/H path. It preserves historical
        # examples/tests but does not claim canonical pressure integration.
        for did,d in self.registry.domains.items():
            v=float(self.world.domain_value(perceived,did))
            drift=float(self.world.domain_value(baseline_state,did))-v
            h=collapse_horizon(v,d.threshold,drift); hs[did]=h
            if governing_from_horizon(h,d): init.add(did)
        if self.registry.governing_configuration is not None or self.registry.recovery_necessities:
            gov=set(self.identify_governing_domains(hs).governing_domain_ids)
        else:
            gov=dependency_close(init,self.registry.domains)
        for did,d in self.registry.domains.items():
            v=float(self.world.domain_value(perceived,did))
            out[did]=DomainAssessment(
                did,v,pressure_from_margin(v,d.threshold),hs[did],did in gov,d.threshold
            )
        return perceived,out,hs,gov

    def identify_governing_domains(self, horizons) -> GoverningAssessment:
        """Canonical G: horizon seed followed by minimal recovery-necessity closure.

        Recovery necessity is consumed only from explicit registered structural
        facts. Phi/pressure, policy ranking, registration order, and domain labels
        cannot alter membership.
        """
        if not self.registry.domains:
            raise ValueError("G requires at least one registered domain")
        cfg=self.registry.governing_configuration or GoverningConfiguration()
        missing=[d for d in self.registry.domains if d not in horizons]
        if missing:
            raise ValueError(f"G horizon structure omits registered domains: {missing}")
        hvals={d:float(horizons[d]) for d in self.registry.domains}
        if any(math.isnan(v) for v in hvals.values()):
            raise ValueError("G horizon structure may not contain NaN")
        hmin=min(hvals.values())
        seed=tuple(d for d in self.registry.domains if hvals[d] <= hmin + cfg.epsilon_h)
        if not seed:
            raise RuntimeError("G invariant violated: horizon seed is empty")

        # Index strict necessities by target once, then perform transitive BFS.
        by_target={}
        for rel in self.registry.recovery_necessities.values():
            by_target.setdefault(rel.target_domain_id,[]).append(rel)
        governing=set(seed)
        queue=deque(seed)
        added=[]; used=[]; provenance={}
        while queue:
            target=queue.popleft()
            for rel in by_target.get(target,()):
                support=rel.support_domain_id
                if support not in governing:
                    governing.add(support)
                    queue.append(support)
                    added.append(support)
                    provenance[support]=(rel.id,target)
                used.append(rel.id)

        # Minimality follows from necessity-only inclusion: every non-seed member
        # has a strict recovery-necessity witness from a member already in closure.
        ordered=tuple(d for d in self.registry.domains if d in governing)
        return GoverningAssessment(
            tuple(seed),ordered,tuple(added),tuple(dict.fromkeys(used)),provenance,
            cfg.epsilon_h,hmin,
            ("G membership is horizon-anchored and recovery-necessity closed",
             "Phi/pressure does not alter G membership",
             "non-seed members require an explicit strict recovery-necessity witness",
             "G is non-empty by minimum-horizon inclusion")
        )

    def classify_regime(self, domains, horizons, governing, *,
                        contextual_interruption=False,
                        previous: PreviousRegimeState | None = None) -> RegimeAssessment:
        """Classify behavioral posture from Phi/H/G without evaluating policies.

        G is consumed exactly as supplied by the upstream governing-domain stage.
        Thresholds are architecture-visible registry configuration. Prior state is
        supplied explicitly so hysteresis does not create hidden runtime persistence.
        """
        cfg=self.registry.regime_configuration
        if cfg is None:
            raise ValueError("registered regime configuration required for canonical regime classification")
        gov=tuple(sorted(governing))
        if not gov:
            raise ValueError("canonical regime classification requires a non-empty governing set")
        hmin=min(float(horizons[d]) for d in gov)
        pmax=max(float(domains[d].pressure) for d in gov)
        m=len(gov)
        hms=cfg.tau_h_mult_survival if cfg.tau_h_mult_survival is not None else cfg.tau_h_survival
        hmst=cfg.tau_h_mult_stabilization if cfg.tau_h_mult_stabilization is not None else cfg.tau_h_stabilization

        if contextual_interruption:
            base="Existential"; trigger="contextual_interruption"
        elif hmin <= cfg.tau_h_existential:
            base="Existential"; trigger="governing_min_horizon_existential"
        elif pmax >= cfg.tau_phi_existential:
            base="Existential"; trigger="governing_max_pressure_existential"
        elif hmin <= cfg.tau_h_survival:
            base="Survival"; trigger="governing_min_horizon_survival"
        elif pmax >= cfg.tau_phi_survival:
            base="Survival"; trigger="governing_max_pressure_survival"
        elif m >= cfg.tau_m_survival and hmin <= hms:
            base="Survival"; trigger="governing_multiplicity_survival"
        elif hmin <= cfg.tau_h_stabilization:
            base="Stabilization"; trigger="governing_min_horizon_stabilization"
        elif pmax >= cfg.tau_phi_stabilization:
            base="Stabilization"; trigger="governing_max_pressure_stabilization"
        elif m >= cfg.tau_m_stabilization and hmin <= hmst:
            base="Stabilization"; trigger="governing_multiplicity_stabilization"
        else:
            base="Mission"; trigger="mission_default"

        severity={"Mission":0,"Stabilization":1,"Survival":2,"Existential":3}
        final=base; hysteresis=False
        if previous is not None:
            if previous.regime not in severity:
                raise ValueError(f"Unknown previous regime: {previous.regime}")
            prev_sev=severity[previous.regime]
            base_sev=severity[base]
            # A materially worsening governing horizon may never de-escalate posture.
            if hmin < previous.governing_min_horizon - cfg.delta_h_escalation and base_sev < prev_sev:
                final=previous.regime; hysteresis=True; trigger="hysteresis_escalation_monotonicity"
            # Recovery de-escalation requires architecture-visible improvement margin.
            elif base_sev < prev_sev and hmin < previous.governing_min_horizon + cfg.delta_h_deescalation:
                final=previous.regime; hysteresis=True; trigger="hysteresis_deescalation_hold"
            # No hysteresis rule may suppress an independently valid Existential trigger.
            if base == "Existential":
                final=base; hysteresis=False

        return RegimeAssessment(
            final,gov,hmin,pmax,m,bool(contextual_interruption),base,hysteresis,trigger,
            ("regime is behavioral posture only; it does not evaluate feasibility, adequacy, or selection",
             "governing-domain membership is consumed from G and is not modified by R")
        )

    def _plan_for_trigger(self, aid):
        return next((p for p in self.registry.recovery_plans.values() if p.trigger_action==aid),None)
    def _project_sequence(self, state, action_ids):
        s=state
        for aid in action_ids:
            pr=self.world.project(s,self.registry.actions[aid])
            if not pr.feasible: return None, pr.reasons
            s=pr.next_state
        return s,()

    def _project_policy_set(self, state, action_ids):
        """Project one same-period policy. Prefer host policy projection when supplied."""
        projector=getattr(self.world, "project_policy", None)
        if callable(projector):
            pr=projector(state, tuple(action_ids))
            if not pr.feasible:
                return None, pr.reasons
            return pr.next_state, ()
        # Compatibility fallback only. Sequential projection is not assumed equivalent
        # to simultaneous execution and is identified in policy-selection notes.
        return self._project_sequence(state, action_ids)

    def _apply_registered_policy_structure(self, viable):
        """Apply registered prerequisite relations and grouped requirements.

        Legacy ``dependency_floor`` relations behave as singleton ``all_of``
        requirements. Grouped requirements add explicit ``all_of`` and ``any_of``
        semantics. A target's unavailability can then propagate downstream.
        Selection never depends on graph centrality, path count, or registration
        order; the graph only determines structural admissibility.
        """
        relations=tuple(self.registry.domain_relations.values())
        grouped=tuple(getattr(self.registry, "dependency_requirements", {}).values())
        if not relations and not grouped:
            return list(viable), StructuralPolicyAssessment(
                "no_registered_policy_structure", (), (), tuple(e.policy_id for e in viable),
                (), {}, {}, True, {}
            )

        # Internal normalized requirements: id, mode, sources, target, floor.
        requirements=[]
        for rel in relations:
            requirements.append((rel.id, "all_of", (rel.source_domain_id,),
                                 rel.target_domain_id, rel.minimum_source_horizon))
        for req in grouped:
            requirements.append((req.id, req.mode, tuple(req.source_domain_ids),
                                 req.target_domain_id, req.minimum_source_horizon))

        by_source={}
        for idx,(_,_,sources,_,_) in enumerate(requirements):
            for source in sources:
                by_source.setdefault(source, []).append(idx)

        survivors=[]
        excluded=[]
        reasons=[]
        provenance={}
        provenance_causes={}
        requirement_failures={}

        for ev in viable:
            unavailable={}
            causes={}
            req_failed_sources=[set() for _ in requirements]
            req_triggered=[False for _ in requirements]
            queue=deque()

            # Initialize source failures from the policy's own projected horizons.
            for idx,(rid,mode,sources,target,floor) in enumerate(requirements):
                failed={src for src in sources if ev.projected_horizons.get(src,-math.inf) < floor}
                req_failed_sources[idx].update(failed)

            def requirement_failed(idx):
                _,mode,sources,_,_=requirements[idx]
                n=len(req_failed_sources[idx])
                return n > 0 if mode == "all_of" else n == len(sources)

            def trigger_requirement(idx):
                if req_triggered[idx] or not requirement_failed(idx):
                    return
                req_triggered[idx]=True
                rid,mode,sources,target,floor=requirements[idx]
                failed=tuple(src for src in sources if src in req_failed_sources[idx])

                # Preserve all immediate grouped causes. Direct horizon failures use
                # parent None; closure-propagated failures retain their source.
                target_causes=causes.setdefault(target, [])
                for src in failed:
                    parent=src if src in unavailable else None
                    cause=(rid,parent)
                    if cause not in target_causes:
                        target_causes.append(cause)

                if target not in unavailable:
                    # One predecessor is enough for lazy witness reconstruction.
                    witness_source=next((src for src in failed if src in unavailable), None)
                    unavailable[target]=(rid,witness_source)
                    queue.append(target)
                    if mode == "any_of":
                        reasons.append(
                            f"{ev.policy_id}: {rid}: all substitutes {', '.join(failed)} failed; "
                            f"{target} structurally unavailable"
                        )
                    elif len(sources) > 1:
                        reasons.append(
                            f"{ev.policy_id}: {rid}: required source(s) {', '.join(failed)} failed; "
                            f"{target} structurally unavailable"
                        )
                    else:
                        src=sources[0]
                        source_h=ev.projected_horizons.get(src,-math.inf)
                        if src in unavailable:
                            reasons.append(
                                f"{ev.policy_id}: {target} structurally unavailable through dependency closure "
                                f"from unavailable prerequisite {src} via {rid}"
                            )
                        else:
                            reasons.append(
                                f"{ev.policy_id}: {rid}: {src} horizon {source_h:.6g} "
                                f"< registered prerequisite floor {floor:.6g} for {target}"
                            )

            # Trigger requirements already failed from horizon consequences.
            for idx in range(len(requirements)):
                trigger_requirement(idx)

            # Propagate newly unavailable domains into every requirement that uses
            # them as a source. For any_of, propagation waits until all substitutes
            # are failed; for all_of, the first failed required source is enough.
            while queue:
                source=queue.popleft()
                for idx in by_source.get(source, ()):
                    if source not in req_failed_sources[idx]:
                        req_failed_sources[idx].add(source)
                    trigger_requirement(idx)

            if unavailable:
                excluded.append(ev.policy_id)
                provenance[ev.policy_id]=dict(unavailable)
                provenance_causes[ev.policy_id]={
                    d: tuple(cs) for d,cs in causes.items() if d in unavailable
                }
                rf={}
                for idx,(rid,_,sources,target,_) in enumerate(requirements):
                    if req_triggered[idx]:
                        rf.setdefault(target,{})[rid]=tuple(
                            src for src in sources if src in req_failed_sources[idx]
                        )
                requirement_failures[ev.policy_id]=rf
            else:
                survivors.append(ev)

        status="registered_structure_filtered_policy_sets" if excluded else "registered_structure_nonbinding"
        all_ids=tuple([r.id for r in relations]+[r.id for r in grouped])
        return survivors, StructuralPolicyAssessment(
            status, all_ids, tuple(excluded), tuple(e.policy_id for e in survivors),
            tuple(reasons), provenance, provenance_causes, False, requirement_failures
        )

    @staticmethod
    def _sigma_horizon_key(value, right_censored: bool):
        """Order-preserving key for canonical censor-aware horizon comparison.

        Exact values compare numerically. Every right-censored observation at the
        common L_P is comparison-equivalent and strictly better than every exact
        observation within that window. No order beyond L_P is represented.
        """
        return (1, 0.0) if right_censored else (0, float(value))

    @classmethod
    def _pareto_frontier(cls, policy_ids, consequences, domain_ids, censoring=None):
        """Exact non-dominated skyline under Sigma's per-domain comparison relation."""
        dims=tuple(domain_ids)
        censoring=censoring or {}
        vectors={
            pid:tuple(cls._sigma_horizon_key(
                consequences[pid][d], d in censoring.get(pid,())
            ) for d in dims)
            for pid in policy_ids
        }

        def dominates(a,b):
            weak=True; strict=False
            for x,y in zip(a,b):
                if x < y:
                    weak=False
                    break
                if x > y:
                    strict=True
            return weak and strict

        ids=tuple(policy_ids)
        if len(dims)==1:
            best=max(vectors[pid][0] for pid in ids)
            return tuple(pid for pid in ids if vectors[pid][0]==best)

        if len(dims)==2:
            groups={}
            for pid in ids:
                x,y=vectors[pid]
                groups.setdefault(x,[]).append((pid,y))
            survivor_set=set(); max_y_from_greater_x=None
            for x in sorted(groups,reverse=True):
                group=groups[x]; group_max=max(y for _,y in group)
                if max_y_from_greater_x is None or group_max > max_y_from_greater_x:
                    for pid,y in group:
                        if y==group_max:
                            survivor_set.add(pid)
                if max_y_from_greater_x is None or group_max > max_y_from_greater_x:
                    max_y_from_greater_x=group_max
            return tuple(pid for pid in ids if pid in survivor_set)

        frontier=[]
        for pid in ids:
            pv=vectors[pid]; rejected=False; retained=[]
            for qid in frontier:
                qv=vectors[qid]
                if dominates(qv,pv):
                    rejected=True; break
                if not dominates(pv,qv):
                    retained.append(qid)
            if not rejected:
                retained.append(pid); frontier=retained
        return tuple(frontier)

    def evaluate_sigma_fallback(self, evaluations, governing_domain_ids, structural_profiles=None):
        """Recovery-unavailable Sigma fallback under canonical V2 + v0.1 parameter addendum.

        Scope is deliberately strict: the runtime implements full fallback comparison
        for singleton maximal sets and for pairwise non-dominated conflicts. Multiway
        Stage-2 override composition is not specified tightly enough in the current
        authority and therefore fails closed rather than inventing a tournament rule.
        """
        valid=tuple(e for e in evaluations if e.feasible)
        if not valid:
            raise ValueError("fallback Sigma requires non-empty Pi_valid")
        if any(e.adequate for e in valid):
            raise ValueError("fallback Sigma may not run while an adequate policy exists")
        gov=tuple(governing_domain_ids)
        if not gov:
            raise ValueError("fallback Sigma requires non-empty G")
        consequences={e.policy_id:dict(e.projected_horizons) for e in valid}
        missing={pid:[d for d in gov if d not in vals] for pid,vals in consequences.items()}
        missing={pid:v for pid,v in missing.items() if v}
        if missing:
            raise ValueError(f"fallback Sigma consequence representation omits governing domains: {missing}")
        censoring={e.policy_id:frozenset(e.right_censored_domain_ids) for e in valid}
        censored=any(censoring.values())
        if censored:
            lps={e.projection_horizon for e in valid}
            if None in lps or len(lps)!=1:
                raise ValueError("censor-aware fallback requires one common licensed projection horizon L_P")
            lp=float(next(iter(lps)))
            if not math.isfinite(lp) or lp<=0:
                raise ValueError("fallback projection horizon L_P must be finite and positive")
            for e in valid:
                for d in gov:
                    v=float(consequences[e.policy_id][d])
                    if d in censoring[e.policy_id]:
                        if not math.isclose(v,lp,rel_tol=1e-12,abs_tol=1e-12):
                            raise ValueError(f"right-censored fallback horizon must store L_P bound: {e.policy_id}/{d}")
                    elif v>lp:
                        raise ValueError(f"exact fallback horizon cannot exceed common L_P: {e.policy_id}/{d}")

        ids=tuple(e.policy_id for e in valid)
        maximal=self._pareto_frontier(ids,consequences,gov,censoring)
        if len(maximal)==1:
            selected=maximal[0]
            order=self.registry.sigma_order.get(selected)
            return SigmaFallbackAssessment(
                "recovery_unavailable_fallback",ids,maximal,maximal,None,maximal,selected,
                order.order_index if order else None,"fallback_singleton_maximal_selected",
                ("fallback Pareto maximal set was singleton; completion stages were unnecessary",)
            )

        def ordered_vector(pid):
            vals=[]
            for d in gov:
                vals.append((self._sigma_horizon_key(consequences[pid][d],d in censoring.get(pid,())),d,float(consequences[pid][d]),d in censoring.get(pid,())))
            vals.sort(key=lambda x:x[0])
            return tuple(vals)
        vectors={pid:ordered_vector(pid) for pid in maximal}
        best=max(tuple(x[0] for x in vectors[pid]) for pid in maximal)
        stage1=tuple(pid for pid in maximal if tuple(x[0] for x in vectors[pid])==best)
        profiles={p.policy_id:p for p in (structural_profiles or ())}

        # Stage 2 is operationally unambiguous for a pairwise maximal conflict.
        if len(maximal)==2 and len(stage1)==1:
            winner=stage1[0]; loser=maximal[0] if maximal[1]==winner else maximal[1]
            if winner not in profiles or loser not in profiles:
                raise ValueError("fallback Stage 2 requires upstream FallbackStructuralProfile for both pairwise survivors")
            vw=vectors[winner]; vl=vectors[loser]
            j=next(i for i,(a,b) in enumerate(zip(vw,vl)) if a[0]!=b[0])
            # Bounded override requires a known numeric margin. A censored winner
            # only establishes T>L_P, so the actual advantage is unknown and may
            # not be treated as marginal.
            override=None
            if not vw[j][3] and not vl[j][3]:
                delta=vw[j][2]-vl[j][2]
                cfg=self.registry.fallback_configuration or FallbackConfiguration()
                epsilon=float(cfg.alpha_base)*vl[j][2]
                pw=profiles[winner]; pl=profiles[loser]
                worse_damage=bool((set(pw.critical_damage_structure_ids)-set(pl.critical_damage_structure_ids)) or
                                  (set(pw.critical_maneuver_structure_ids)-set(pl.critical_maneuver_structure_ids)))
                if 0.0 < delta <= epsilon and worse_damage:
                    override=loser
            if override is not None:
                return SigmaFallbackAssessment(
                    "recovery_unavailable_fallback",ids,maximal,stage1,override,(override,),override,
                    self.registry.sigma_order.get(override).order_index if override in self.registry.sigma_order else None,
                    "fallback_stage2_override_selected",
                    ("Stage-2 bounded override applied only to a marginal exact-horizon advantage and categorical upstream governing-critical damage difference",)
                )
            # No Stage-2 override: Stage-1 winner remains selected. Stage 3 cannot
            # reverse a governing-collapse advantage.
            selected=winner
            return SigmaFallbackAssessment(
                "recovery_unavailable_fallback",ids,maximal,stage1,None,(winner,),selected,
                self.registry.sigma_order.get(selected).order_index if selected in self.registry.sigma_order else None,
                "fallback_stage1_selected",
                ("Stage-1 governing collapse ordering prevailed; no permitted Stage-2 override applied",)
            )

        if len(maximal)>2 and len(stage1)==1:
            return SigmaFallbackAssessment(
                "recovery_unavailable_fallback",ids,maximal,stage1,None,(),None,None,
                "fallback_multiway_override_not_formalized",
                ("current authority does not specify a safe multiway composition rule for pairwise bounded Stage-2 overrides; runtime fails closed",)
            )

        # Stage-1 ties are eligible for Stage-3 lexicographic structural refinement.
        missing_profiles=[pid for pid in stage1 if pid not in profiles]
        if missing_profiles:
            raise ValueError(f"fallback Stage 3 requires upstream FallbackStructuralProfile for tied Stage-1 survivors: {missing_profiles}")
        def s3key(pid):
            p=profiles[pid]
            if min(p.irreversible_damage_rank,p.noncritical_maneuver_rank,p.spillover_damage_rank)<0:
                raise ValueError("fallback Stage-3 ranks must be nonnegative explicit ordinals")
            return (-p.irreversible_damage_rank,p.noncritical_maneuver_rank,-p.spillover_damage_rank)
        best3=max(s3key(pid) for pid in stage1)
        stage3=tuple(pid for pid in stage1 if s3key(pid)==best3)
        if len(stage3)==1:
            selected=stage3[0]
            return SigmaFallbackAssessment(
                "recovery_unavailable_fallback",ids,maximal,stage1,None,stage3,selected,
                self.registry.sigma_order.get(selected).order_index if selected in self.registry.sigma_order else None,
                "fallback_stage3_selected",
                ("Stage-3 applied lexicographically over explicit upstream ordinal structural attributes; no weighting or addition was used",)
            )
        missing_order=[pid for pid in stage3 if pid not in self.registry.sigma_order]
        if missing_order:
            raise ValueError(f"fallback Stage 4 requires explicit deterministic order for residual survivors: {missing_order}")
        selected=min(stage3,key=lambda pid:self.registry.sigma_order[pid].order_index)
        return SigmaFallbackAssessment(
            "recovery_unavailable_fallback",ids,maximal,stage1,None,stage3,selected,
            self.registry.sigma_order[selected].order_index,"fallback_stage4_tie_selected",
            ("Stage-4 residual tie used only explicit fixed deterministic order after all substantive fallback structure was exhausted",)
        )

    def _terminal_compare_pair(self, a, pa, b, pb, classes):
        """Lexicographic structured terminal comparison through a class prefix.

        A lower class is consulted only when every higher class is comparison-
        equivalent. Incomparability at a higher class stops comparison; it is not
        a license for lower-priority compensation.
        """
        compare=getattr(self.world,"compare_constraint_violation_severity",None)
        if not callable(compare):
            raise ValueError("terminal Sigma requires host compare_constraint_violation_severity()")
        for constraint_class in classes:
            rel=compare(a,pa,b,pb,constraint_class)
            if rel not in (-1,0,1,None):
                raise ValueError("terminal severity comparator must return -1, 0, 1, or None")
            rev=compare(b,pb,a,pa,constraint_class)
            if rev not in (-1,0,1,None):
                raise ValueError("terminal severity comparator must return -1, 0, 1, or None")
            if (rel is None) != (rev is None):
                raise ValueError("terminal severity comparator must be symmetric about incomparability")
            if rel is not None and rev != -rel:
                raise ValueError("terminal severity comparator must be antisymmetric")
            if rel is None:
                return None
            if rel != 0:
                return rel
        return 0

    def _terminal_prefix_frontier(self, policy_ids, profiles_by_id, classes):
        """Incremental maximal set under coherent terminal lexicographic dominance."""
        frontier=[]
        for pid in policy_ids:
            p=profiles_by_id[pid]
            dominated=False; survivors=[]
            for qid in frontier:
                q=profiles_by_id[qid]
                rel=self._terminal_compare_pair(pid,p,qid,q,classes)
                if rel == 1:
                    dominated=True
                    break
                if rel == -1:
                    continue
                survivors.append(qid)
            if not dominated:
                survivors.append(pid)
                frontier=survivors
        return tuple(frontier)

    def evaluate_sigma_terminal(self, constraint_results) -> SigmaTerminalAssessment:
        """Canonical terminal infeasibility selection without a universal severity score.

        Sigma owns strict class priority: hard, then conditional, then soft.
        Within-class structured severity comparison is supplied upstream because
        the canonical source intentionally leaves universal severity representation
        underformalized. Lower-priority improvement can never compensate for a
        higher-priority worsening.
        """
        if not constraint_results:
            raise ValueError("terminal Sigma requires at least one candidate constraint result")
        ids=[]; profiles={}
        for result in constraint_results:
            if result.policy_id in profiles:
                raise ValueError(f"duplicate terminal policy result: {result.policy_id}")
            if result.violation_profile is None:
                raise ValueError(f"terminal Sigma requires structured violation profile for {result.policy_id}")
            ids.append(result.policy_id); profiles[result.policy_id]=result.violation_profile
        hard=self._terminal_prefix_frontier(tuple(ids),profiles,("hard",))
        conditional=self._terminal_prefix_frontier(hard,profiles,("hard","conditional"))
        soft=self._terminal_prefix_frontier(conditional,profiles,("hard","conditional","soft"))
        final=soft
        selected=None; selected_index=None
        if len(final)==1:
            selected=final[0]
        elif final:
            missing=[pid for pid in final if pid not in self.registry.sigma_order]
            if missing:
                raise ValueError(f"terminal Sigma residual tie requires explicit OrderIndex for: {missing}")
            selected=min(final,key=lambda pid:self.registry.sigma_order[pid].order_index)
            selected_index=self.registry.sigma_order[selected].order_index
        return SigmaTerminalAssessment(
            "terminal_infeasibility",tuple(ids),hard,conditional,soft,final,selected,selected_index,
            ("terminal Sigma compares structured violation severity by strict class priority: hard -> conditional -> soft",
             "within-class severity is supplied by the integration boundary; Sigma does not invent scalar severity",
             "lower-priority classes are consulted only after higher-priority comparison equivalence; higher-class incomparability is preserved through residual tie resolution")
        )

    def evaluate_sigma_standard(self, evaluations, governing_domain_ids):
        """Canonical Sigma v1.13: censor-aware A1, global A2, fixed Stage-3 order."""
        adequate=tuple(e for e in evaluations if e.feasible and e.adequate)
        if not adequate:
            raise ValueError("standard Sigma requires a non-empty adequate set")
        gov=tuple(governing_domain_ids)
        if not gov:
            raise ValueError("standard Sigma requires non-empty G")
        consequences={e.policy_id:dict(e.projected_horizons) for e in adequate}
        keysets={tuple(sorted(v)) for v in consequences.values()}
        if len(keysets)!=1:
            raise ValueError("Sigma consequence representation must be aligned across policies")
        active=next(iter(keysets))
        missing=[d for d in gov if d not in active]
        if missing:
            raise ValueError(f"Sigma consequence representation omits governing domains: {missing}")

        censoring={e.policy_id:frozenset(e.right_censored_domain_ids) for e in adequate}
        all_domains=set(active)
        for e in adequate:
            unknown=set(e.right_censored_domain_ids)-all_domains
            if unknown:
                raise ValueError(f"Sigma censoring flags reference unknown domains for {e.policy_id}: {sorted(unknown)}")
        censored=any(censoring.values())
        if censored:
            lps={e.projection_horizon for e in adequate}
            if None in lps or len(lps)!=1:
                raise ValueError("censor-aware Sigma requires one common licensed projection horizon L_P")
            lp=float(next(iter(lps)))
            if not math.isfinite(lp) or lp<=0:
                raise ValueError("Sigma projection horizon L_P must be finite and positive")
            for e in adequate:
                for d,v in consequences[e.policy_id].items():
                    fv=float(v)
                    if math.isnan(fv):
                        raise ValueError(f"Sigma horizon may not be NaN: {e.policy_id}/{d}")
                    if d in censoring[e.policy_id]:
                        if not math.isclose(fv,lp,rel_tol=1e-12,abs_tol=1e-12):
                            raise ValueError(f"right-censored Sigma horizon must store L_P bound: {e.policy_id}/{d}")
                    elif fv>lp:
                        raise ValueError(f"exact Sigma horizon cannot exceed common L_P: {e.policy_id}/{d}")
        else:
            for pid,vals in consequences.items():
                if any(math.isnan(float(v)) for v in vals.values()):
                    raise ValueError(f"Sigma horizon may not be NaN: {pid}")

        ids=tuple(e.policy_id for e in adequate)
        a1=self._pareto_frontier(ids,consequences,gov,censoring)
        # Canonically Stage 2 is global dominance over all active domains inside
        # A1. A policy in A1 can be globally dominated only by another A1 policy
        # that is comparison-equivalent on every governing coordinate; otherwise
        # the dominator would already have removed it at Stage 1. We exploit that
        # identity as an exact optimization, including censor-equivalence at L_P.
        if set(active)==set(gov):
            a2=a1
        else:
            fibers={}
            for pid in a1:
                key=tuple(self._sigma_horizon_key(
                    consequences[pid][d], d in censoring.get(pid,())
                ) for d in gov)
                fibers.setdefault(key,[]).append(pid)
            survivor=set()
            for members in fibers.values():
                if len(members)==1:
                    survivor.update(members)
                else:
                    survivor.update(self._pareto_frontier(tuple(members),consequences,active,censoring))
            a2=tuple(pid for pid in a1 if pid in survivor)
        stage1=SigmaStageAssessment(
            "A1_governing_frontier",ids,gov,a1,
            ("Stage 1 uses only governing domains and the canonical censor-aware comparison relation",)
        )
        stage2=SigmaStageAssessment(
            "A2_global_refinement",a1,active,a2,
            ("Stage 2 applies censor-aware global dominance across all active domains within A1",)
        )
        if len(a2)==1:
            selected=a2[0]
            order_index=self.registry.sigma_order.get(selected)
            selected_index=order_index.order_index if order_index is not None else None
            tie_note="A2 singleton selected directly; Stage-3 order index not required"
        else:
            missing_order=[pid for pid in a2 if pid not in self.registry.sigma_order]
            if missing_order:
                raise ValueError(
                    "Sigma Stage 3 requires explicit state-independent OrderIndex for every A2 survivor; "
                    f"missing: {missing_order}"
                )
            selected=min(a2,key=lambda pid:self.registry.sigma_order[pid].order_index)
            selected_index=self.registry.sigma_order[selected].order_index
            tie_note="A2 tie resolved only by explicit fixed state-independent OrderIndex"
        notes=[tie_note,
               "candidate iteration order, policy ID lexical order, registration order, and consequence scoring are not Stage-3 rules"]
        if censored:
            notes.append("right-censored horizons are comparison-equivalent at common L_P; Sigma infers no order beyond L_P")
        return SigmaAssessment("standard",stage1,stage2,a2,selected,selected_index,tuple(notes))

    def _evaluate_policy_sets_after_completeness(self, state, candidates, pi_completeness=None, domain_framing=None, constraints=None, projected_terminals=None, adequacy=None, projection_records=None):
        """Evaluate policy sets after the Pi-completeness boundary has been handled."""
        perceived,_,base_horizons,governing=self._assess_domains(state)
        evaluations=[]
        for candidate in candidates:
            if projected_terminals is not None:
                terminal=projected_terminals.get(candidate.id)
                record=(projection_records or {}).get(candidate.id)
                if terminal is None and not (record is not None and record.feasible and record.projected_horizons):
                    reason=next((r.reasons for r in constraints.candidate_results if r.policy_id==candidate.id),("host constraint rejected policy",))
                    evaluations.append(PolicySetEvaluation(candidate.id,candidate.action_ids,False,False,{},tuple(reason)))
                    continue
                reasons=()
            else:
                record=None
                terminal,reasons=self._project_policy_set(perceived,candidate.action_ids)
                if terminal is None:
                    evaluations.append(PolicySetEvaluation(candidate.id,candidate.action_ids,False,False,{},tuple(reasons)))
                    continue
            record=(projection_records or {}).get(candidate.id) if record is None else record
            if record is not None and record.projected_horizons:
                ph=dict(record.projected_horizons)
                projection_horizon=record.projection_horizon
                right_censored=tuple(record.right_censored_domain_ids)
            else:
                _,_,ph,_=self._assess_domains(terminal)
                projection_horizon=None
                right_censored=()
            if adequacy is not None:
                adequate=candidate.id in adequacy.adequate_policy_ids
                pa=next((x for x in adequacy.policy_results if x.policy_id==candidate.id),None)
                reasons=() if adequate else (pa.reasons if pa is not None else ("policy is not recovery-corridor adequate",))
            else:
                # Compatibility-only heuristic retained for pre-v0.23 integrations.
                # Full canonical adequacy requires authoritative Q_t(pi).
                adequate=all(ph[d]>0 and (self.registry.domains[d].governing_horizon is None or ph[d]>self.registry.domains[d].governing_horizon or ph[d]>=base_horizons[d]) for d in governing)
                reasons=() if adequate else ("compatibility horizon heuristic does not establish a full recovery corridor",)
            evaluations.append(PolicySetEvaluation(
                candidate.id,candidate.action_ids,True,adequate,ph,tuple(reasons),
                projection_horizon,right_censored
            ))
        # The authoritative v0.24 path uses canonical staged Sigma only after
        # upstream Adequacy has classified Pi_adequate. Compatibility paths retain
        # the historical comparator below.
        if adequacy is not None and adequacy.adequate_policy_ids:
            sigma=self.evaluate_sigma_standard(evaluations,tuple(sorted(governing)))
            a2=set(sigma.final_policy_ids)
            final=tuple(e for e in evaluations if e.policy_id in a2)
            conflicting=()
            if len(final)>1:
                differing=[]
                for d in sigma.stage2.domain_ids:
                    vals={e.projected_horizons[d] for e in final}
                    if len(vals)>1:
                        differing.append(d)
                conflicting=tuple(differing)
            status="sigma_standard_policy_selected"
            return PolicySelectionAssessment(
                status,tuple(candidates),tuple(evaluations),sigma.final_policy_ids,
                sigma.selected_policy_id,conflicting,None,pi_completeness,
                domain_framing,constraints,adequacy,sigma,
                ("canonical standard Sigma executed as A1 governing frontier then A2 global refinement",
                 "Sigma did not re-test feasibility or adequacy")
            )

        viable=[e for e in evaluations if e.feasible and e.adequate]
        viable, structural = self._apply_registered_policy_structure(viable)
        def dominates(a,b):
            if not governing:
                return False
            av=[a.projected_horizons.get(d,-math.inf) for d in sorted(governing)]
            bv=[b.projected_horizons.get(d,-math.inf) for d in sorted(governing)]
            return all(x>=y for x,y in zip(av,bv)) and any(x>y for x,y in zip(av,bv))
        undominated=[e for e in viable if not any(dominates(other,e) for other in viable if other.policy_id!=e.policy_id)]
        selected_id=undominated[0].policy_id if len(undominated)==1 else None
        conflicting_domains=()
        if selected_id and len(viable) == 1:
            status="unique_structurally_admissible_policy_set" if structural.excluded_policy_ids else "unique_feasible_adequate_policy_set"
        elif selected_id:
            status="unique_governing_consequence_dominance"
        elif not viable:
            status="no_structurally_admissible_policy_set" if structural.excluded_policy_ids else "no_adequate_policy_set"
        else:
            gov_order=tuple(sorted(governing))
            differing=[]
            for d in gov_order:
                vals={e.projected_horizons.get(d,-math.inf) for e in undominated}
                if len(vals)>1:
                    differing.append(d)
            conflicting_domains=tuple(differing)
            vectors=[tuple(e.projected_horizons.get(d,-math.inf) for d in gov_order) for e in undominated]
            if len(set(vectors))<=1:
                status="equivalent_governing_consequences_unresolved"
            else:
                crossing=False
                for i,a in enumerate(undominated):
                    for b in undominated[i+1:]:
                        av=[a.projected_horizons.get(d,-math.inf) for d in gov_order]
                        bv=[b.projected_horizons.get(d,-math.inf) for d in gov_order]
                        if any(x>y for x,y in zip(av,bv)) and any(x<y for x,y in zip(av,bv)):
                            crossing=True
                            break
                    if crossing:
                        break
                status="crossing_governing_consequences_unresolved" if crossing else "governing_consequences_unresolved"
        notes=(
            "policy sets are compared only by represented consequences on current governing domains; no scalar aggregation is used",
            "componentwise governing-horizon dominance is a conservative prototype comparator, not asserted canonical Sigma mathematics",
            "registered structural relations may exclude a policy only through explicit prerequisite semantics; they do not rank surviving policies",
        )
        if conflicting_domains:
            notes += ("undominated policies differ on governing domains: " + ", ".join(conflicting_domains),)
        if not callable(getattr(self.world, "project_policy", None)):
            notes += ("host did not provide project_policy(); compatibility sequential projection was used",)
        return PolicySelectionAssessment(
            status, tuple(candidates), tuple(evaluations), tuple(e.policy_id for e in undominated),
            selected_id, conflicting_domains, structural, pi_completeness, domain_framing, constraints, adequacy, None, notes
        )

    @staticmethod
    def _graph_family_to_pi_family(family: str) -> str:
        mapping={
            "continuation":"continuation",
            "maintenance_local_adjustment":"local_adjustment",
            "corrective_repair":"local_adjustment",
            "structural_reconfiguration":"structural_shift",
            "exit_transfer_liquidation":"structural_shift",
            "substitution":"structural_shift",
            "release_restructuring":"structural_shift",
            "escape_emergency":"emergency_escape",
        }
        return mapping[family]

    def construct_graph(self, preservation_object: PreliminaryPreservationObject, regime: str,
                        governing_domain_ids, required_family_ids=(), required_path_class_ids=(),
                        *, config: GraphConstructionConfig | None = None) -> GraphConstructionAssessment:
        """Execute the bounded Graph Construction Protocol through Graph -> Pi handoff.

        This operator validates explicitly registered structural inputs. It does
        not search arbitrary future state, project policies, evaluate viability,
        or infer material requirements from topology.
        """
        cfg=config or GraphConstructionConfig()
        if cfg.max_seeds <= 0:
            raise ValueError("Graph max_seeds must be positive")
        if not preservation_object.id or not preservation_object.function_statement.strip():
            return GraphConstructionAssessment(
                "FAIL",preservation_object.id,regime,tuple(sorted(governing_domain_ids)),
                failure_codes=("G-010",),
                notes=("preliminary structural preservation object is not explicitly declared",)
            )
        gov=tuple(sorted(set(governing_domain_ids)))
        unknown_g=[d for d in gov if d not in self.registry.domains]
        if unknown_g:
            return GraphConstructionAssessment(
                "FAIL",preservation_object.id,regime,gov,failure_codes=("G-010",),
                notes=(f"governing/domain declaration contains unknown domains: {unknown_g}",)
            )
        if not self.registry.graph_instances:
            return GraphConstructionAssessment(
                "FAIL",preservation_object.id,regime,gov,failure_codes=("G-010",),
                notes=("no relevant graph instances are enumerated",)
            )

        taxonomy={"continuation","maintenance_local_adjustment","corrective_repair",
                  "structural_reconfiguration","exit_transfer_liquidation","substitution",
                  "release_restructuring","escape_emergency"}
        required_families=tuple(dict.fromkeys(required_family_ids))
        bad_required=[f for f in required_families if f not in taxonomy]
        if bad_required:
            raise ValueError(f"unknown required graph families: {bad_required}")

        reachable=[]; excluded=[]; uncertain=[]; failures=[]
        for tr in self.registry.graph_transformations.values():
            if tr.family not in taxonomy:
                failures.append("G-001")
                continue
            if tr.reachability_status=="reachable":
                reachable.append(tr)
            elif tr.reachability_status=="unreachable":
                excluded.append(tr)
            else:
                uncertain.append(tr)

        reachable_by_id={t.id:t for t in reachable}
        valid_compositions=[]; invalid_compositions=[]
        represented_path_classes=set()
        for comp in self.registry.graph_compositions.values():
            # Composition is explicitly multi-step. A one-step "composition"
            # would falsely satisfy a staged-path requirement that the source
            # assigns to composition construction.
            ids=tuple(comp.transformation_ids)
            valid=len(ids) >= 2
            trs=[]
            if valid:
                for tid in ids:
                    tr=self.registry.graph_transformations.get(tid)
                    if tr is None:
                        valid=False
                        break
                    trs.append(tr)
            if valid and any(t.reachability_status!="reachable" for t in trs):
                valid=False
            if valid:
                for a,b in zip(trs,trs[1:]):
                    if a.destination_instance_id != b.source_instance_id:
                        valid=False
                        break
            # The Graph Construction Protocol requires recovery relevance and
            # distinctness justification in every composition output record.
            if valid and (not comp.recovery_relevance.strip() or
                          not comp.distinctness_justification.strip()):
                valid=False
            if valid:
                valid_compositions.append(comp)
                represented_path_classes.update(comp.policy_class_ids)
            else:
                invalid_compositions.append(comp)

        required_path_classes=tuple(dict.fromkeys(required_path_class_ids))
        missing_paths=tuple(c for c in required_path_classes if c not in represented_path_classes)
        if missing_paths:
            failures.append("G-005")

        represented_families=set(t.family for t in reachable)
        represented_families.update(c.represented_family for c in valid_compositions)
        missing_families=tuple(f for f in required_families if f not in represented_families)
        if missing_families:
            failures.append("G-002")

        # Seed reduction happens only after reachability, composition, and coverage.
        # Build compact structural descriptors first. This lets the graph detect
        # boundedness overflow before allocating a large handoff object population.
        specs={}
        for tr in reachable:
            classes=tuple(dict.fromkeys((tr.family,)+tuple(tr.policy_class_ids)))
            actions=(tr.action_id,)
            pi_family=self._graph_family_to_pi_family(tr.family)
            affected=tuple(tr.affected_domain_ids)
            key=(actions,pi_family,tuple(sorted(affected)),tuple(sorted(classes)),"single_step")
            required_seed=bool(tr.structurally_required or tr.family in required_families)
            specs.setdefault(key,(
                "graph:"+tr.id,actions,pi_family,affected,classes,required_seed,
                tr.family,"single_step",(tr.id,),tr.structural_effect
            ))
            if len(specs) > cfg.max_seeds:
                break
        if len(specs) <= cfg.max_seeds:
            composition_seed_source=valid_compositions
        else:
            composition_seed_source=()
        for comp in composition_seed_source:
            trs=[reachable_by_id[t] for t in comp.transformation_ids]
            actions=tuple(t.action_id for t in trs)
            classes=tuple(dict.fromkeys((comp.represented_family,)+tuple(comp.policy_class_ids)))
            pi_family=self._graph_family_to_pi_family(comp.represented_family)
            affected=tuple(comp.affected_domain_ids)
            key=(actions,pi_family,tuple(sorted(affected)),tuple(sorted(classes)),"staged")
            required_seed=bool(
                comp.structurally_required
                or comp.represented_family in required_families
                or set(comp.policy_class_ids).intersection(required_path_classes)
            )
            specs.setdefault(key,(
                "graphpath:"+comp.id,actions,pi_family,affected,classes,required_seed,
                comp.represented_family,"staged",comp.transformation_ids,
                comp.distinctness_justification
            ))
            if len(specs) > cfg.max_seeds:
                break

        seeds=[]
        if len(specs) <= cfg.max_seeds:
            for spec in specs.values():
                sid,actions,pi_family,affected,classes,required,source_family,path_type,source_ids,distinctness=spec
                seeds.append(PolicySeedDefinition(
                    sid,actions,pi_family,affected,classes,required,True,True,
                    None,source_family,path_type,source_ids,distinctness
                ))

        if len(specs)>cfg.max_seeds:
            failures.append("G-007")

        # Graph Protocol 14.4: uncertainty can support CONDITIONAL PASS only
        # when it does not alter known family presence and does not determine
        # the existence of the only viable path. Unknown is therefore neither
        # silently present nor silently absent.
        reachable_families={x.family for x in reachable}
        uncertain_family_presence=tuple(sorted({
            x.family for x in uncertain if x.family not in reachable_families
        }))
        uncertain_only_viable=tuple(sorted(
            x.id for x in uncertain if x.only_viable_path_candidate
        ))
        uncertain_required=any(
            x.structurally_required or
            (x.family in required_families and x.family not in reachable_families)
            for x in uncertain
        )
        if uncertain_required:
            failures.append("G-003")
        if uncertain_family_presence or uncertain_only_viable:
            failures.append("G-004")

        if invalid_compositions:
            failures.append("G-005")

        failures=tuple(dict.fromkeys(failures))
        if failures:
            status="FAIL"
            handed=()
        elif uncertain:
            status="CONDITIONAL PASS"
            handed=tuple(seeds)
        else:
            status="PASS"
            handed=tuple(seeds)

        notes=[
            "graph construction order enforced: scope -> domains -> instances -> taxonomy -> reachability -> composition -> coverage -> reduction -> validity -> handoff",
            "unreachable transformations are recorded but never admitted to the graph substrate",
            "graph construction performs no policy projection, adequacy evaluation, or selection",
            "graph validity does not guarantee Pi completeness",
            "multi-step composition is explicit and bounded by registered paths; the runtime does not invent a general path-depth limit or search arbitrary graph futures",
            "required staged path classes are supplied upstream and checked after composition, before seed reduction",
            "explicitly required graph families/path classes propagate required status into the Graph -> Pi seed handoff",
        ]
        if len(specs)>cfg.max_seeds:
            notes.append("boundedness overflow blocks handoff rather than truncating by registration order")
            handed=()
        open_uncertainty=tuple(
            f"{x.id}: {x.uncertainty_note}" for x in uncertain
        )
        safe_to_handoff=status in {"PASS","CONDITIONAL PASS"} and bool(handed)
        if uncertain_family_presence:
            notes.append("uncertain reachability changes family-presence determination; conditional pass is prohibited")
        if uncertain_only_viable:
            notes.append("uncertain reachability bears an explicitly identified only-viable-path candidate; conditional pass is prohibited")
        return GraphConstructionAssessment(
            status,preservation_object.id,regime,gov,
            tuple(x.id for x in reachable),tuple(x.id for x in excluded),
            tuple(x.id for x in uncertain),tuple(c.id for c in valid_compositions),
            tuple(sorted(represented_families)),missing_families,
            tuple(s.id for s in handed),failures,handed,tuple(notes),
            tuple(c.id for c in invalid_compositions),missing_paths,
            open_uncertainty,uncertain_family_presence,uncertain_only_viable,safe_to_handoff
        )

    def construct_pi(self, regime: str, governing_domain_ids, materially_required_class_ids, *, config: PiConstructionConfig | None = None) -> PiConstructionAssessment:
        """Construct bounded Pi from graph-layer seeds without feasibility or ranking."""
        cfg=config or PiConstructionConfig()
        if cfg.max_candidates <= 0:
            raise ValueError("Pi max_candidates must be positive")
        if regime not in {"Mission","Stabilization","Survival","Existential"}:
            raise ValueError(f"Unsupported regime for Pi construction: {regime}")
        gov=set(governing_domain_ids)
        seeds=tuple(self.registry.policy_seeds.values())
        visible=[x for x in seeds if x.visible]
        malformed=[x for x in visible if (not x.coherent or not x.action_ids)]
        candidates0=[x for x in visible if x.coherent and x.action_ids]
        # Regime shaping is family activation only. Structural requirement overrides suppression.
        active={
            "Mission":{"continuation","local_adjustment"},
            "Stabilization":{"continuation","local_adjustment","structural_shift"},
            "Survival":{"continuation","local_adjustment","structural_shift","emergency_escape"},
            "Existential":{"continuation","local_adjustment","structural_shift","emergency_escape"},
        }[regime]
        eligible=[]; suppressed=[]
        required_classes=set(materially_required_class_ids)
        for seed in candidates0:
            governing_relevant=bool(gov.intersection(seed.affected_domain_ids)) if gov else False
            required_by_class=bool(required_classes.intersection(seed.policy_class_ids))
            required_seed=bool(seed.structurally_required or required_by_class)
            if seed.family in active or required_seed:
                # Governing-domain bias may suppress unrelated optional policies only under elevated pressure.
                if regime in {"Survival","Existential"} and gov and not governing_relevant and not required_seed and seed.family != "continuation":
                    suppressed.append(seed)
                else:
                    eligible.append(seed)
            else:
                suppressed.append(seed)
        if not any(x.family=="continuation" for x in eligible):
            return PiConstructionAssessment(
                "pi_missing_mandatory_continuation",regime,tuple(sorted(gov)),tuple(x.id for x in visible),tuple(x.id for x in eligible),(),tuple(x.id for x in suppressed),tuple(x.id for x in malformed),(),0,None,
                ("continuation is mandatory in canonical Pi",))
        # Exact generative redundancy only; no projection/dominance/adequacy comparison.
        seen={}; unique=[]; duplicates=[]
        for seed in eligible:
            key=(seed.action_ids,seed.family,tuple(sorted(seed.policy_class_ids)),tuple(sorted(seed.affected_domain_ids)))
            if key in seen:
                duplicates.append(seed)
            else:
                seen[key]=seed.id; unique.append(seed)
        if len(unique) > cfg.max_candidates:
            return PiConstructionAssessment(
                "pi_boundedness_overflow",regime,tuple(sorted(gov)),tuple(x.id for x in visible),tuple(x.id for x in eligible),(),tuple(x.id for x in suppressed),tuple(x.id for x in malformed),tuple(x.id for x in duplicates),len(unique)-cfg.max_candidates,None,
                ("Pi refuses registration-order truncation; upstream graph/attention must provide a smaller bounded visible seed set",))
        emitted=tuple(CandidatePolicySet(x.id,x.action_ids,metadata={"pi_family":x.family,"source":"graph_seed",**dict(x.metadata or {})},policy_class_ids=x.policy_class_ids) for x in unique)
        space=CandidatePolicySpace(emitted,tuple(materially_required_class_ids),(
            "constructed by bounded regime-shaped Pi from graph-layer seeds",
            "materially required classes are supplied upstream and validated separately",
        ))
        return PiConstructionAssessment(
            "pi_constructed",regime,tuple(sorted(gov)),tuple(x.id for x in visible),tuple(x.id for x in eligible),tuple(x.id for x in unique),tuple(x.id for x in suppressed),tuple(x.id for x in malformed),tuple(x.id for x in duplicates),0,space,
            ("Pi performed no feasibility, projection, adequacy, or selection logic",
             "Mission/elevated-regime family shaping cannot suppress an upstream-declared materially required policy class",))

    def construct_pi_from_graph(self, graph: GraphConstructionAssessment, materially_required_class_ids,
                                *, config: PiConstructionConfig | None = None) -> PiConstructionAssessment:
        """Construct Pi only from a graph that passed its own validity boundary."""
        if graph.status not in {"PASS","CONDITIONAL PASS"} or not graph.policy_seeds:
            return PiConstructionAssessment(
                "pi_blocked_by_graph_invalidity",graph.regime,graph.governing_domain_ids,
                (),(),(),(),(),(),0,None,
                ("Pi cannot repair or bypass an invalid Graph Layer handoff",)
            )
        cfg=config or PiConstructionConfig()
        if cfg.max_candidates <= 0:
            raise ValueError("Pi max_candidates must be positive")
        regime=graph.regime
        if regime not in {"Mission","Stabilization","Survival","Existential"}:
            raise ValueError(f"Unsupported regime for Pi construction: {regime}")
        gov=set(graph.governing_domain_ids)
        visible=[x for x in graph.policy_seeds if x.visible]
        malformed=[x for x in visible if (not x.coherent or not x.action_ids)]
        candidates0=[x for x in visible if x.coherent and x.action_ids]
        active={
            "Mission":{"continuation","local_adjustment"},
            "Stabilization":{"continuation","local_adjustment","structural_shift"},
            "Survival":{"continuation","local_adjustment","structural_shift","emergency_escape"},
            "Existential":{"continuation","local_adjustment","structural_shift","emergency_escape"},
        }[regime]
        eligible=[]; suppressed=[]
        required_classes=set(materially_required_class_ids)
        for seed in candidates0:
            governing_relevant=bool(gov.intersection(seed.affected_domain_ids)) if gov else False
            required_by_class=bool(required_classes.intersection(seed.policy_class_ids))
            required_seed=bool(seed.structurally_required or required_by_class)
            if seed.family in active or required_seed:
                if regime in {"Survival","Existential"} and gov and not governing_relevant and not required_seed and seed.family!="continuation":
                    suppressed.append(seed)
                else:
                    eligible.append(seed)
            else:
                suppressed.append(seed)
        if not any(x.family=="continuation" for x in eligible):
            return PiConstructionAssessment(
                "pi_missing_mandatory_continuation",regime,tuple(sorted(gov)),
                tuple(x.id for x in visible),tuple(x.id for x in eligible),(),
                tuple(x.id for x in suppressed),tuple(x.id for x in malformed),(),0,None,
                ("continuation is mandatory in canonical Pi",)
            )
        seen={}; unique=[]; duplicates=[]
        for seed in eligible:
            key=(seed.action_ids,seed.family,tuple(sorted(seed.policy_class_ids)),tuple(sorted(seed.affected_domain_ids)))
            if key in seen:
                duplicates.append(seed)
            else:
                seen[key]=seed.id; unique.append(seed)
        if len(unique)>cfg.max_candidates:
            return PiConstructionAssessment(
                "pi_boundedness_overflow",regime,tuple(sorted(gov)),
                tuple(x.id for x in visible),tuple(x.id for x in eligible),(),
                tuple(x.id for x in suppressed),tuple(x.id for x in malformed),
                tuple(x.id for x in duplicates),len(unique)-cfg.max_candidates,None,
                ("Pi refuses order-based truncation of a valid graph handoff",)
            )
        emitted=tuple(CandidatePolicySet(
            x.id,x.action_ids,
            metadata={"pi_family":x.family,"source":"validated_graph_handoff",
                      "graph_family":x.source_family,"path_type":x.path_type,
                      "source_ids":x.source_ids,
                      "structural_distinctness_note":x.structural_distinctness_note,
                      **dict(x.metadata or {})},
            policy_class_ids=x.policy_class_ids
        ) for x in unique)
        space=CandidatePolicySpace(
            emitted,tuple(materially_required_class_ids),
            ("constructed by Pi from a structurally validated graph substrate",
             "graph validity does not guarantee Pi completeness")
        )
        return PiConstructionAssessment(
            "pi_constructed",regime,tuple(sorted(gov)),tuple(x.id for x in visible),
            tuple(x.id for x in eligible),tuple(x.id for x in unique),
            tuple(x.id for x in suppressed),tuple(x.id for x in malformed),
            tuple(x.id for x in duplicates),0,space,
            ("Pi consumed graph seeds without changing graph reachability status",)
        )

    def validate_pi_completeness(self, policy_space: CandidatePolicySpace) -> PiCompletenessAssessment:
        """Validate explicit regime-relative policy-class coverage before Constraints.

        This gate does not discover policy classes, test host feasibility, evaluate
        adequacy, frame domains, or rank policies. The upstream constructor/graph
        layer must declare the materially required classes for the current decision
        problem; this gate verifies that Pi actually represented them.
        """
        required=tuple(dict.fromkeys(policy_space.materially_required_class_ids))
        represented_set=set()
        for candidate in policy_space.candidates:
            represented_set.update(candidate.policy_class_ids)
        represented=tuple(sorted(represented_set))
        missing=tuple(cid for cid in required if cid not in represented_set)
        if missing:
            status="pi_completeness_failed_missing_material_policy_classes"
            complete=False
            notes=(
                "downstream Constraints, Domain Framing, Adequacy, and Sigma are blocked by Pi completeness failure",
                "the runtime reports declared omissions but does not invent missing policy structure",
            )
        else:
            status="pi_completeness_passed"
            complete=True
            notes=(
                "all upstream-declared materially required policy classes are represented",
                "completeness is regime-relative structural coverage, not exhaustive enumeration",
            )
        return PiCompletenessAssessment(
            status, complete, required, represented, missing,
            tuple(c.id for c in policy_space.candidates), tuple(policy_space.notes)+notes
        )

    def qualify_pi_completeness_for_substrate(
            self, local: PiCompletenessAssessment,
            qualification: EpistemicSubstrateQualification
            ) -> QualifiedPiCompletenessAssessment:
        """Apply the supporting contaminated-substrate protocol without repairing Pi.

        This method is intentionally not invoked by the canonical decision cycle in
        v0.54. It hardens and tests the supporting protocol before any promotion.
        """
        if qualification.status not in {"clean","uncertain","epistemically_contaminated"}:
            raise ValueError("substrate qualification status must be clean, uncertain, or epistemically_contaminated")
        if not qualification.basis.strip():
            raise ValueError("substrate qualification requires explicit basis")

        local_complete=bool(local.complete)
        if qualification.status=="clean":
            if local_complete:
                status="qualified_pi_pass"
                full=True
                layered=()
            else:
                status="qualified_pi_fail"
                full=False
                layered=("Pi completeness failure on clean substrate",)
        else:
            full=False
            if local_complete:
                status="qualified_pi_conditional_warning"
                layered=(f"substrate qualification: {qualification.status}",)
            else:
                status="qualified_pi_fail_with_layered_attribution"
                layered=(
                    f"substrate qualification: {qualification.status}",
                    "local Pi completeness failure",
                )

        return QualifiedPiCompletenessAssessment(
            status,local,qualification,local_complete,full,full,layered,
            (
                "a pass relative to an epistemically qualified substrate is not an unqualified structural-validity certificate",
                "this supporting boundary does not restore graph classes that were never built",
                "no downstream operator is invoked or repaired by this qualification method",
                "v0.54 does not automatically insert this supporting protocol into the canonical cycle",
            )
        )


    def validate_projection_model_authority(self, authority: ProjectionModelAuthority | None, projection_horizon) -> ProjectionModelAuthorityAssessment:
        """Validate explicit Theta_P/model-version authority without interpreting the model.

        L_P(t) remains externally supplied. This method checks only that a declared
        model authority is well-formed and licenses exactly the horizon used by Q.
        Absence remains backward-compatible; it does not synthesize model identity.
        """
        if authority is None:
            return ProjectionModelAuthorityAssessment(
                True, notes=(
                    "no explicit projection model authority supplied; legacy model_version validation remains active",
                    "runtime did not infer model identity, configuration, parameter semantics, or L_P derivation",
                )
            )
        violations=[]
        for name,value in (("model_id",authority.model_id),("model_version",authority.model_version),("configuration_id",authority.configuration_id),("parameter_set_id",authority.parameter_set_id),("license_basis",authority.license_basis)):
            if not str(value).strip(): violations.append(f"projection model authority requires non-blank {name}")
        try:
            lp=float(authority.licensed_projection_horizon)
            if not math.isfinite(lp) or lp <= 0: violations.append("projection model authority licensed horizon must be finite and positive")
        except (TypeError,ValueError):
            lp=None; violations.append("projection model authority licensed horizon must be numeric")
        try:
            requested=float(projection_horizon)
            if lp is not None and (not math.isfinite(requested) or not math.isclose(lp,requested,rel_tol=1e-12,abs_tol=1e-12)):
                violations.append("projection model authority licensed horizon must match the requested L_P exactly")
        except (TypeError,ValueError):
            violations.append("requested projection horizon is unavailable for model-authority validation")
        return ProjectionModelAuthorityAssessment(
            not violations, authority.model_id, authority.model_version, authority.configuration_id,
            authority.parameter_set_id, lp, tuple(violations), (
                "predictive-model identity and fixed configuration are trace authority, not selection inputs",
                "runtime does not inspect Theta_P contents or compare competing predictive models",
                "L_P remains externally supplied; matching here is licensing validation, not derivation",
            )
        )


    def validate_projection_causal_inputs(self, perceived: PerceivedDecisionState | None, required_input_ids=()) -> ProjectionInputLicenseAssessment:
        """Validate explicitly licensed represented causal inputs for S_I^proj(t).

        Requirements are supplied by the host/model boundary. The runtime never infers
        a missing commitment, environmental fact, capacity, or expectation from Graph,
        Layer-1 actual state, policy identity, or unrelated metadata.
        """
        required=tuple(required_input_ids or ())
        violations=[]
        if len(required) != len(set(required)):
            violations.append("projection required causal input ids must be unique")
        if any(not str(x).strip() for x in required):
            violations.append("projection required causal input ids may not be blank")
        inputs=tuple(perceived.projection_causal_inputs) if perceived is not None else ()
        ids=[]
        decision_time=float(perceived.time) if perceived is not None else None
        for item in inputs:
            if not isinstance(item,ProjectionCausalStateInput):
                violations.append("projection causal inputs must be ProjectionCausalStateInput objects")
                continue
            iid=str(item.input_id)
            ids.append(iid)
            if not iid.strip(): violations.append("projection causal input_id may not be blank")
            if not str(item.kind).strip(): violations.append(f"projection causal input {iid!r} requires a non-empty kind")
            if not str(item.license_basis).strip(): violations.append(f"projection causal input {iid!r} requires an explicit license_basis")
            try: rt=float(item.represented_time)
            except Exception:
                violations.append(f"projection causal input {iid!r} represented_time must be numeric"); continue
            if not math.isfinite(rt): violations.append(f"projection causal input {iid!r} represented_time must be finite")
            if decision_time is not None and rt > decision_time + 1e-12:
                violations.append(f"projection causal input {iid!r} is future/hindsight information unavailable at decision time")
            if len(item.source_ids) != len(set(item.source_ids)):
                violations.append(f"projection causal input {iid!r} source_ids must be unique")
            if any(not str(x).strip() for x in item.source_ids):
                violations.append(f"projection causal input {iid!r} source_ids may not be blank")
        if len(ids) != len(set(ids)):
            violations.append("projection causal input ids must be unique")
        licensed=tuple(ids)
        missing=tuple(x for x in required if x not in set(ids))
        if missing:
            violations.append("required projection causal inputs are missing: " + ", ".join(missing))
        return ProjectionInputLicenseAssessment(
            not violations,licensed,required,missing,tuple(violations),(
                "only explicitly represented decision-time causal inputs are exposed to Q",
                "license_basis is provenance/authority metadata, not a utility or confidence weight",
                "required inputs are host/model-declared; the runtime does not infer them",
            )
        )

    def _projection_trace_from_perceived(self, perceived: PerceivedDecisionState | None, base=None):
        """Build non-semantic provenance for S_I^proj(t) without scalarizing its contents."""
        trace=dict(base or {})
        if perceived is None:
            return trace
        trace.update({
            "perceived_state_id":perceived.state_id,
            "perceived_state_time":float(perceived.time),
            "ppp_interface_present":perceived.ppp is not None,
            "spv_hat_interface_present":perceived.spv_hat is not None,
            "pvs_interface_present":perceived.pvs is not None,
            "x_hat_interface_present":perceived.x_hat is not None,
            "retrieval_id":perceived.retrieval.retrieval_id if perceived.retrieval is not None else None,
            "expectation_state_id":perceived.expectation_state.expectation_state_id if perceived.expectation_state is not None else None,
            "confidence_interface_present":perceived.confidence is not None,
            "uncertainty_interface_present":perceived.uncertainty is not None,
            "licensed_causal_input_ids":tuple(i.input_id for i in perceived.projection_causal_inputs),
        })
        return trace

    @staticmethod
    def _freeze_execution_evidence(value):
        """Canonicalize nested execution evidence for in-process integrity comparison.

        This is not a cryptographic digest or semantic interpretation. It only
        provides a deterministic structural identity for mappings/sequences so
        downstream audit surfaces can detect splicing or mutation.
        """
        if isinstance(value, dict):
            return tuple(sorted(((repr(k), PVPPRuntime._freeze_execution_evidence(v)) for k,v in value.items()), key=lambda x:x[0]))
        if isinstance(value, (tuple, list)):
            return tuple(PVPPRuntime._freeze_execution_evidence(v) for v in value)
        if isinstance(value, set):
            return tuple(sorted((PVPPRuntime._freeze_execution_evidence(v) for v in value), key=repr))
        return value

    @classmethod
    def _execution_evidence_signature(cls, value):
        return repr(cls._freeze_execution_evidence(value))

    @staticmethod
    def _projection_record_signature(record: PolicyProjectionRecord):
        # repr observes nested mutable mappings too; this is an in-cycle mutation guard,
        # not a persistent cryptographic identity.
        return repr(record)

    def validate_projection_record(self, request: ProjectionRequest, record: PolicyProjectionRecord) -> PolicyProjectionRecord:
        """Validate canonical Q_t(pi) identity, horizon, censoring, and trace invariants.

        Projection supplies facts only. This validator does not classify feasibility,
        adequacy, dominance, or preference; it merely protects the shared-record
        information boundary before downstream consumers see it.
        """
        if record.policy_id != request.policy_id:
            raise ValueError(f"projection record policy_id mismatch: expected {request.policy_id}, got {record.policy_id}")
        lp=float(request.projection_horizon)
        if not math.isfinite(lp) or lp <= 0:
            raise ValueError("projection_horizon L_P must be finite and positive")
        if record.projection_horizon is None or not math.isclose(float(record.projection_horizon),lp,rel_tol=1e-12,abs_tol=1e-12):
            raise ValueError("Q_t(pi) must record the licensed projection_horizon L_P exactly")
        if record.state_time is None or not math.isclose(float(record.state_time),float(request.represented_state.time),rel_tol=1e-12,abs_tol=1e-12):
            raise ValueError("Q_t(pi) state_time must identify the represented decision-time state")
        if request.state_id is not None and record.state_id != request.state_id:
            raise ValueError("Q_t(pi) state_id does not match the supplied represented state identity")
        if request.perceived_decision_state is not None:
            pds=request.perceived_decision_state
            if pds.represented_state is not request.represented_state and pds.represented_state != request.represented_state:
                raise ValueError("projection perceived decision state does not wrap the supplied represented_state")
            if request.state_id is not None and pds.state_id != request.state_id:
                raise ValueError("projection perceived decision state identity mismatch")
            if not math.isclose(float(pds.time),float(request.represented_state.time),rel_tol=0.0,abs_tol=1e-12):
                raise ValueError("projection perceived decision state time mismatch")
        if record.candidate_mode != request.candidate_mode:
            raise ValueError("Q_t(pi) candidate_mode does not match the licensed candidate subset")
        if not str(record.model_version).strip():
            raise ValueError("Q_t(pi) requires a non-empty predictive model_version")
        if request.model_authority is not None:
            auth=request.model_authority
            assessment=request.model_authority_assessment
            if assessment is None or not assessment.valid:
                raise ValueError("Q_t(pi) may not run with invalid projection model authority")
            if record.model_version != auth.model_version:
                raise ValueError("Q_t(pi) model_version must match the licensed predictive-model authority")
            if record.model_id != auth.model_id:
                raise ValueError("Q_t(pi) model_id must match the licensed predictive-model authority")
            if record.model_configuration_id != auth.configuration_id:
                raise ValueError("Q_t(pi) model configuration must match the licensed predictive-model authority")
            if record.model_parameter_set_id != auth.parameter_set_id:
                raise ValueError("Q_t(pi) model parameter-set identity must match the licensed predictive-model authority")
        if not record.projection_input_trace:
            raise ValueError("Q_t(pi) requires a projection_input_trace for reproduction/audit")
        if request.input_license_assessment is not None:
            lic=request.input_license_assessment
            if not lic.valid:
                raise ValueError("Q_t(pi) may not run with an invalid projection causal-input license assessment")
            expected=tuple(lic.licensed_input_ids)
            got=tuple(record.projection_input_trace.get("licensed_causal_input_ids",()))
            if got != expected:
                raise ValueError("Q_t(pi) projection_input_trace must preserve licensed causal input identities exactly")

        claims=tuple(record.information_quality_claims)
        seen_claims=set()
        allowed_subject_kinds={"reachability","closure","reopening","trajectory","recovery_corridor","horizon"}
        for claim in claims:
            if not isinstance(claim,ProjectionInformationQualityClaim):
                raise ValueError("Q_t(pi) information_quality_claims must contain typed ProjectionInformationQualityClaim records")
            if claim.subject_kind not in allowed_subject_kinds:
                raise ValueError(f"unsupported projection information-quality subject_kind: {claim.subject_kind}")
            if not str(claim.subject_id).strip():
                raise ValueError("projection information-quality claim requires subject_id")
            if not str(claim.basis).strip():
                raise ValueError("projection information-quality claim requires an explicit basis")
            if claim.confidence is None:
                raise ValueError("projection information-quality claim requires explicit confidence metadata")
            key=(claim.subject_kind,claim.subject_id)
            if key in seen_claims:
                raise ValueError(f"duplicate projection information-quality claim: {key}")
            seen_claims.add(key)
            if claim.uncertainty_note and not claim.uncertainty_note.strip():
                raise ValueError("projection information-quality uncertainty_note may not be whitespace-only")
            if len(claim.source_ids) != len(set(claim.source_ids)):
                raise ValueError("projection information-quality source_ids must be unique")
            if any(not str(s).strip() for s in claim.source_ids):
                raise ValueError("projection information-quality source_ids may not be blank")

        cens=tuple(record.right_censored_domain_ids)
        if len(cens) != len(set(cens)):
            raise ValueError("Q_t(pi) right_censored_domain_ids must be unique")
        known=set(self.registry.domains)
        horizon_domains=set(record.projected_horizons)
        if horizon_domains != known:
            missing=known-horizon_domains; extra=horizon_domains-known
            raise ValueError(f"Q_t(pi) projected_horizons must cover exactly registered domains; missing={sorted(missing)}, extra={sorted(extra)}")
        if not set(cens) <= known:
            raise ValueError("Q_t(pi) contains right-censoring for an unknown domain")
        for did,value in record.projected_horizons.items():
            v=float(value)
            if math.isnan(v):
                raise ValueError(f"Q_t(pi) horizon for {did} may not be NaN")
            if did in cens:
                if not math.isclose(v,lp,rel_tol=1e-12,abs_tol=1e-12):
                    raise ValueError(f"right-censored Q_t(pi) horizon for {did} must store the censoring bound L_P")
            else:
                if not math.isfinite(v) or v < 0 or v > lp:
                    raise ValueError(f"exact Q_t(pi) horizon for {did} must lie within [0, L_P]")
        corridor_keys=[]
        for c in record.recovery_corridors:
            if c.domain_id not in known:
                raise ValueError(f"Q_t(pi) recovery corridor references unknown domain {c.domain_id}")
            key=(c.domain_id,c.function_id)
            corridor_keys.append(key)
            for name,val in (("recovery_entry_time",c.recovery_entry_time),("projected_extinction_time",c.projected_extinction_time)):
                if val is not None and (not math.isfinite(float(val)) or float(val) < 0 or float(val) > lp):
                    raise ValueError(f"Q_t(pi) {name} for {c.domain_id}/{c.function_id} must lie within [0, L_P]")
        if len(corridor_keys) != len(set(corridor_keys)):
            raise ValueError("Q_t(pi) may contain at most one recovery-corridor fact per domain/function target")
        return record

    def _project_policy_record(self, state, candidate, *, candidate_mode="ordinary_adequacy", projection_horizon=None, graph_assessment=None, projection_input_trace=None, perceived_decision_state: PerceivedDecisionState | None = None, projection_input_license_assessment: ProjectionInputLicenseAssessment | None = None, projection_model_authority: ProjectionModelAuthority | None = None, projection_model_authority_assessment: ProjectionModelAuthorityAssessment | None = None):
        """Return one authoritative Q_t(pi), preferring the canonical typed service.

        The legacy world.project_policy_record() hook is retained for historical
        integrations. New canonical integrations should attach PolicyProjectionService.
        """
        if self.projection_service is not None:
            if projection_horizon is None:
                raise ValueError("canonical PolicyProjectionService requires an externally supplied finite L_P")
            state_id=state.metadata.get("state_id") if isinstance(state.metadata,dict) else None
            base_trace=projection_input_trace or {"state_time":state.time,"policy_id":candidate.id}
            input_trace=self._projection_trace_from_perceived(perceived_decision_state,base_trace)
            req=ProjectionRequest(state,candidate.id,tuple(candidate.action_ids),candidate_mode,float(projection_horizon),graph_assessment,state_id,input_trace,perceived_decision_state,projection_input_license_assessment,projection_model_authority,projection_model_authority_assessment)
            record=self.projection_service.project(req)
            return self.validate_projection_record(req,record)
        projector=getattr(self.world,"project_policy_record",None)
        if not callable(projector):
            return None
        record=projector(state,candidate.id,tuple(candidate.action_ids))
        if record.policy_id != candidate.id:
            raise ValueError(f"projection record policy_id mismatch: expected {candidate.id}, got {record.policy_id}")
        return record

    def evaluate_restoration_adequacy(self, frame: DomainFrame, governing, records) -> AdequacyAssessment:
        """Evaluate full framed recovery corridors from authoritative Q_t(pi) records.

        No trajectory, recovery region, substitution, closure, reopening, or
        extinction structure is invented locally. Adequacy is conjunctive over G.
        """
        # Domain order is presentation-only. Preserve the already-validated frame
        # order and compare sets so Adequacy remains O(G) rather than sorting G.
        gov=tuple(t.domain_id for t in frame.targets)
        framed={t.domain_id:t.function_id for t in frame.targets}
        if set(framed) != set(governing) or len(gov) != len(framed):
            raise ValueError("adequacy requires an already-validated frame exactly covering G")
        policy_results=[]
        adequate_ids=[]
        inadequate_ids=[]
        for record in records:
            index={(c.domain_id,c.function_id):c for c in record.recovery_corridors}
            domain_results=[]
            policy_reasons=[]
            for d in gov:
                fid=framed[d]
                c=index.get((d,fid))
                if c is None:
                    reasons=("Q_t(pi) lacks a recovery-corridor fact for the exact framed target",)
                    dr=DomainAdequacyResult(d,fid,False,False,False,False,None,reasons)
                else:
                    adequate=(c.pre_recovery_viability_preserved and
                              c.recovery_capable_region_reached and
                              c.joint_sustainment_supported)
                    reasons=[]
                    if not c.pre_recovery_viability_preserved:
                        reasons.append("framed viability is not preserved until recovery entry")
                    if not c.recovery_capable_region_reached:
                        reasons.append("no recovery-capable region is reached")
                    if not c.joint_sustainment_supported:
                        reasons.append("joint sustainment across governing domains is unsupported")
                    dr=DomainAdequacyResult(
                        d,fid,adequate,c.pre_recovery_viability_preserved,
                        c.recovery_capable_region_reached,c.joint_sustainment_supported,
                        c.recovery_entry_time,tuple(reasons)+tuple(c.notes)
                    )
                domain_results.append(dr)
                if not dr.adequate:
                    policy_reasons.append(f"{d}/{fid}: " + "; ".join(dr.reasons))
            # Constraints owns present-time feasibility. Adequacy receives only
            # the already-valid subset and therefore classifies recovery corridors
            # without re-reading the legacy Q.feasible compatibility field.
            adequate=all(r.adequate for r in domain_results)
            if adequate: adequate_ids.append(record.policy_id)
            else: inadequate_ids.append(record.policy_id)
            policy_results.append(PolicyAdequacyResult(
                record.policy_id,adequate,tuple(domain_results),tuple(policy_reasons)
            ))
        status=("adequacy_passed_some_policies" if adequate_ids else
                "adequacy_no_recovery_capable_policy")
        return AdequacyAssessment(
            status,tuple(policy_results),tuple(adequate_ids),tuple(inadequate_ids),
            ("adequacy is recovery-corridor elimination, not ranking",
             "all governing domains are conjunctive; no cross-domain compensation is permitted",
             "terminal horizon extension alone is not treated as recovery")
        )

    def _classify_constraint_profile(self, profile: PolicyConstraintProfile) -> ConstraintAssessment:
        """Apply the canonical hard/conditional/soft hierarchy to one typed profile."""
        if profile.policy_id == "":
            raise ValueError("constraint profile requires policy_id")
        seen=set(); hard=[]; conditional=[]; relaxed=[]; soft=[]; reasons=[]
        for obs in profile.observations:
            if obs.rule_id in seen:
                raise ValueError(f"duplicate constraint observation: {obs.rule_id}")
            seen.add(obs.rule_id)
            rule=self.registry.constraint_rules.get(obs.rule_id)
            if rule is None:
                raise ValueError(f"constraint profile references unregistered rule: {obs.rule_id}")
            if not obs.active or not obs.violated:
                continue
            if rule.constraint_class == "hard":
                if obs.regime_relaxable or obs.necessity_authorized:
                    raise ValueError(f"hard constraint {rule.id} may not carry relaxation authorization")
                hard.append(rule.id); reasons.extend(obs.reasons or (f"hard constraint violated: {rule.id}",))
            elif rule.constraint_class == "conditional":
                if obs.regime_relaxable and obs.necessity_authorized:
                    relaxed.append(rule.id)
                else:
                    conditional.append(rule.id); reasons.extend(obs.reasons or (f"active conditional constraint violated: {rule.id}",))
            else:
                if obs.regime_relaxable or obs.necessity_authorized:
                    raise ValueError(f"soft constraint {rule.id} may not carry feasibility relaxation authorization")
                soft.append(rule.id)
        feasible=not hard and not conditional
        vp=ConstraintViolationProfile(tuple(hard),tuple(conditional),tuple(relaxed),tuple(soft))
        return ConstraintAssessment(
            profile.policy_id,feasible,tuple(reasons),vp,"canonical_typed_constraint_profile"
        )

    def evaluate_constraint_system(self, state, candidates, *, regime: str, governing_domain_ids) -> ConstraintsAssessment:
        """Canonical decision-stage feasibility over authorized perceived evidence.

        The host supplies policy/rule observations from feasibility-relevant perceived
        state only. The runtime owns hierarchy enforcement. Conditional relaxation is
        accepted only when both regime permission and explicit necessity authorization
        are present; this operator never fabricates the downstream adequacy evidence
        required to justify necessity.
        """
        profiler=getattr(self.world,"constraint_profile",None)
        if not callable(profiler):
            raise ValueError("canonical Constraint System requires host constraint_profile()")
        if not self.registry.constraint_rules:
            raise ValueError("canonical Constraint System requires registered constraint rules")
        perceived=self.world.perceive(state)
        gov=tuple(governing_domain_ids)
        results=[]; feasible=[]; infeasible=[]
        for candidate in candidates:
            profile=profiler(perceived,candidate.id,candidate.action_ids,regime,gov)
            if not isinstance(profile,PolicyConstraintProfile):
                raise ValueError("constraint_profile() must return PolicyConstraintProfile")
            if profile.policy_id != candidate.id:
                raise ValueError(f"constraint profile policy mismatch: expected {candidate.id}, got {profile.policy_id}")
            result=self._classify_constraint_profile(profile)
            results.append(result)
            (feasible if result.feasible else infeasible).append(candidate.id)
        status="constraints_passed_all_candidates" if not infeasible else (
            "constraints_filtered_candidates" if feasible else "constraints_no_feasible_candidates"
        )
        return ConstraintsAssessment(
            status,tuple(results),tuple(feasible),tuple(infeasible),
            ("Constraints is the authoritative decision-stage feasibility boundary",
             "hard constraints are non-relaxable and regime-invariant",
             "conditional relaxation requires regime permission AND explicit necessity authorization",
             "soft constraints never remove a policy from Pi_valid",
             "authorized perceived evidence may differ from actual execution conditions")
        )

    def _evaluate_constraints_with_terminals(self, state, candidates):
        """Run the explicit host-authoritative Constraints gate.

        Projection feasibility is evaluated exactly once per candidate and retained
        separately from structural admissibility, Domain Framing, and Adequacy.
        """
        perceived=self.world.perceive(state)
        results=[]
        terminals={}
        feasible=[]
        infeasible=[]
        for candidate in candidates:
            terminal,reasons=self._project_policy_set(perceived,candidate.action_ids)
            ok=terminal is not None
            if ok: terminals[candidate.id]=terminal
            results.append(ConstraintAssessment(candidate.id,ok,tuple(reasons)))
            (feasible if ok else infeasible).append(candidate.id)
        status="constraints_passed_all_candidates" if not infeasible else (
            "constraints_filtered_candidates" if feasible else "constraints_no_feasible_candidates"
        )
        assessment=ConstraintsAssessment(
            status,tuple(results),tuple(feasible),tuple(infeasible),
            ("feasibility is host-authoritative and is not an adequacy or preference judgment",)
        )
        return assessment, terminals

    def _evaluate_constraints_with_projection_records(self, state, candidates):
        """Run Constraints and obtain Q_t(pi) records without duplicating ownership.

        When the host implements the typed Constraint System, decision-stage
        feasibility comes from that operator and Q is requested only for policies
        that survive Pi_valid. Legacy integrations continue to consume Q.feasible
        as a compatibility boundary.
        """
        profiler=getattr(self.world,"constraint_profile",None)
        typed=callable(profiler) and bool(self.registry.constraint_rules)
        perceived=self.world.perceive(state)
        terminals={}; records={}
        if typed:
            if self.registry.regime_configuration is None:
                raise ValueError("typed Constraint System integration requires canonical regime configuration")
            _,domains,horizons,governing=self._assess_domains(state)
            regime=self.classify_regime(domains,horizons,governing).regime
            assessment=self.evaluate_constraint_system(
                state,candidates,regime=regime,governing_domain_ids=tuple(sorted(governing))
            )
            for candidate in candidates:
                if candidate.id not in assessment.feasible_policy_ids:
                    continue
                record=self._project_policy_record(perceived,candidate)
                if record is None:
                    raise ValueError(
                        "strict recovery adequacy requires host project_policy_record() / authoritative Q_t(pi)"
                    )
                if self.projection_service is None and not record.feasible:
                    raise ValueError(
                        f"legacy Q_t(pi) contradicts canonical Constraints for executable policy {candidate.id}"
                    )
                records[candidate.id]=record
                if record.terminal_state is not None:
                    terminals[candidate.id]=record.terminal_state
            return assessment,terminals,records

        if self.projection_service is not None:
            raise ValueError("canonical PolicyProjectionService cannot substitute for the Constraint System; register typed constraint rules/profile")
        results=[]; feasible=[]; infeasible=[]
        for candidate in candidates:
            record=self._project_policy_record(perceived,candidate)
            if record is None:
                raise ValueError(
                    "strict recovery adequacy requires host project_policy_record() / authoritative Q_t(pi)"
                )
            records[candidate.id]=record
            ok=bool(record.feasible)
            if ok and record.terminal_state is not None:
                terminals[candidate.id]=record.terminal_state
            results.append(ConstraintAssessment(candidate.id,ok,tuple(record.reasons)))
            (feasible if ok else infeasible).append(candidate.id)
        status="constraints_passed_all_candidates" if not infeasible else (
            "constraints_filtered_candidates" if feasible else "constraints_no_feasible_candidates"
        )
        return ConstraintsAssessment(
            status,tuple(results),tuple(feasible),tuple(infeasible),
            ("compatibility path consumes feasibility from authoritative Q_t(pi)",
             "new integrations should implement typed constraint_profile()")
        ),terminals,records

    def evaluate_constraints(self, state, candidates) -> ConstraintsAssessment:
        assessment,_=self._evaluate_constraints_with_terminals(state,candidates)
        return assessment

    def validate_domain_framing(self, state, frame: DomainFrame) -> DomainFramingAssessment:
        """Validate the explicit preservation-target contract before Adequacy.

        Domain Framing is semantic and upstream-informed. This gate therefore does
        not infer function identity, substitutability, reachability, or sustainability
        from names. It enforces explicit, locked, one-target-per-governing-domain
        framing so downstream Adequacy cannot silently choose its own target.
        """
        _,_,_,governing=self._assess_domains(state)
        gov=tuple(sorted(governing))
        counts={}
        invalid=[]
        for target in frame.targets:
            counts[target.domain_id]=counts.get(target.domain_id,0)+1
            if (target.domain_id not in self.registry.domains or
                not target.function_id.strip() or
                target.basis not in ("function","non_substitutable_mechanism") or
                not target.locked):
                invalid.append(target.domain_id)
        framed=tuple(sorted(counts))
        missing=tuple(d for d in gov if d not in counts)
        duplicates=tuple(sorted(d for d,n in counts.items() if n != 1))
        extras=tuple(sorted(d for d in counts if d not in governing))
        invalid_ids=tuple(sorted(set(invalid).union(extras)))
        valid=not missing and not duplicates and not invalid_ids
        status="domain_framing_passed" if valid else "domain_framing_failed"
        notes=tuple(frame.notes)+(
            "framing is an explicit preservation-target declaration, not an adequacy or preference judgment",
            "the runtime validates framing structure but does not infer viability-preserving substitution from labels",
        )
        return DomainFramingAssessment(
            status, valid, gov, framed, missing, duplicates, invalid_ids, notes
        )

    def _validate_domain_framing_against_governing(self, frame: DomainFrame, governing) -> DomainFramingAssessment:
        """Validate Domain Framing against already-computed G without recomputing PPP/Phi/H/G."""
        gov=tuple(sorted(governing))
        counts={}; invalid=[]
        for target in frame.targets:
            counts[target.domain_id]=counts.get(target.domain_id,0)+1
            if (target.domain_id not in self.registry.domains or
                not target.function_id.strip() or
                target.basis not in ("function","non_substitutable_mechanism") or
                not target.locked):
                invalid.append(target.domain_id)
        framed=tuple(sorted(counts))
        missing=tuple(d for d in gov if d not in counts)
        duplicates=tuple(sorted(d for d,n in counts.items() if n != 1))
        extras=tuple(sorted(d for d in counts if d not in set(gov)))
        invalid_ids=tuple(sorted(set(invalid).union(extras)))
        valid=not missing and not duplicates and not invalid_ids
        return DomainFramingAssessment(
            "domain_framing_passed" if valid else "domain_framing_failed",valid,gov,framed,
            missing,duplicates,invalid_ids,tuple(frame.notes)+(
                "framing validated against the already-computed governing set",
                "no upstream operator was recomputed by Domain Framing",
            )
        )

    def _constraint_system_from_perceived(self, perceived, candidates, *, regime, governing_domain_ids):
        """Canonical Constraints using the cycle's already-authorized perceived state."""
        profiler=getattr(self.world,"constraint_profile",None)
        if not callable(profiler):
            raise ValueError("canonical decision cycle requires host constraint_profile()")
        if not self.registry.constraint_rules:
            raise ValueError("canonical decision cycle requires registered constraint rules")
        results=[]; feasible=[]; infeasible=[]; gov=tuple(governing_domain_ids)
        for candidate in candidates:
            profile=profiler(perceived,candidate.id,candidate.action_ids,regime,gov)
            if not isinstance(profile,PolicyConstraintProfile):
                raise ValueError("constraint_profile() must return PolicyConstraintProfile")
            if profile.policy_id != candidate.id:
                raise ValueError(f"constraint profile policy mismatch: expected {candidate.id}, got {profile.policy_id}")
            result=self._classify_constraint_profile(profile)
            results.append(result); (feasible if result.feasible else infeasible).append(candidate.id)
        status="constraints_passed_all_candidates" if not infeasible else (
            "constraints_filtered_candidates" if feasible else "constraints_no_feasible_candidates")
        return ConstraintsAssessment(status,tuple(results),tuple(feasible),tuple(infeasible),(
            "canonical cycle reused one perceived-state snapshot for Constraints",
            "hard/conditional/soft hierarchy remains authoritative before Q projection",
        ))

    def _standard_selection_from_cycle_records(self, candidates, completeness, framing, constraints,
                                               adequacy, records, governing):
        """Build standard-mode Sigma input from the cycle's single immutable Q record per feasible policy."""
        adequate_ids=set(adequacy.adequate_policy_ids)
        feasible_ids=set(constraints.feasible_policy_ids)
        evaluations=[]
        constraint_by_id={x.policy_id:x for x in constraints.candidate_results}
        adequacy_by_id={x.policy_id:x for x in adequacy.policy_results}
        for candidate in candidates:
            record=records.get(candidate.id)
            if candidate.id not in feasible_ids:
                ca=constraint_by_id[candidate.id]
                evaluations.append(PolicySetEvaluation(candidate.id,candidate.action_ids,False,False,{},ca.reasons))
                continue
            if record is None:
                raise ValueError(f"missing authoritative Q_t(pi) record for feasible policy {candidate.id}")
            pa=adequacy_by_id.get(candidate.id)
            adequate=candidate.id in adequate_ids
            evaluations.append(PolicySetEvaluation(
                candidate.id,candidate.action_ids,True,adequate,dict(record.projected_horizons),
                () if adequate else (pa.reasons if pa else ("policy is not recovery-corridor adequate",)),
                record.projection_horizon,tuple(record.right_censored_domain_ids)
            ))
        if not adequacy.adequate_policy_ids:
            return PolicySelectionAssessment(
                "no_adequate_policy_set",tuple(candidates),tuple(evaluations),(),None,(),None,
                completeness,framing,constraints,adequacy,None,
                ("standard Sigma not entered because Pi_adequate is empty",)
            )
        sigma=self.evaluate_sigma_standard(evaluations,tuple(sorted(governing)))
        return PolicySelectionAssessment(
            "sigma_standard_policy_selected",tuple(candidates),tuple(evaluations),sigma.final_policy_ids,
            sigma.selected_policy_id,(),None,completeness,framing,constraints,adequacy,sigma,
            ("standard Sigma consumed the cycle's existing Q_t(pi) records without reprojection",
             "epsilon remains a separate execution-side call")
        )

    def validate_memory_state_reference(self, memory_state: MemoryStateReference,
                                        actual_state: ActualPersistentStateEnvelope | None = None):
        violations=[]
        if not isinstance(memory_state,MemoryStateReference):
            raise ValueError("memory state must be MemoryStateReference")
        if not memory_state.actor_id:
            violations.append("memory state actor_id required")
        if not memory_state.memory_state_id:
            violations.append("memory_state_id required")
        try:
            mt=float(memory_state.time)
            if not math.isfinite(mt):
                violations.append("memory state time must be finite")
        except Exception:
            violations.append("memory state time must be numeric")
            mt=None
        if actual_state is not None:
            if memory_state.actor_id != actual_state.actor_id:
                violations.append("memory state actor_id must match actual state actor_id")
            if mt is not None and mt > float(actual_state.time)+1e-12:
                violations.append("retained memory state may not originate in the future relative to current actual state")
        return tuple(violations)

    def validate_memory_retrieval_package(self, request: MemoryRetrievalRequest,
                                          package: MemoryRetrievalPackage,
                                          actual_state: ActualPersistentStateEnvelope | None = None):
        violations=[]
        if not isinstance(package,MemoryRetrievalPackage):
            raise ValueError("memory retrieval service must return MemoryRetrievalPackage")
        if package.actor_id != request.actor_id:
            violations.append("retrieval actor_id does not match request")
        if package.memory_state_id != request.memory_state.memory_state_id:
            violations.append("retrieval memory_state_id does not match retained-memory reference")
        if not package.retrieval_id:
            violations.append("retrieval_id required")
        if not isinstance(package.quality,RetrievalQualityMetadata):
            violations.append("retrieval must carry RetrievalQualityMetadata")
        try:
            pt=float(package.time)
            if not math.isfinite(pt):
                violations.append("retrieval time must be finite")
        except Exception:
            pt=None
            violations.append("retrieval time must be numeric")
        expected_time=request.current_time
        if expected_time is None and actual_state is not None:
            expected_time=actual_state.time
        if pt is not None and expected_time is not None and not math.isclose(
            pt,float(expected_time),rel_tol=0.0,abs_tol=1e-12
        ):
            violations.append("retrieval output time must align with the current decision-cycle time")
        return tuple(violations)

    def validate_perceived_decision_state(
            self, perceived: PerceivedDecisionState,
            actual_state: ActualPersistentStateEnvelope, *,
            expected_retrieval: MemoryRetrievalPackage | None = None,
            expected_expectation: ExpectationStateReference | None = None
            ) -> PerceivedDecisionStateValidationAssessment:
        """Validate only P_i(t) interface attribution and routing invariants."""
        violations=[]
        if not isinstance(perceived,PerceivedDecisionState):
            raise ValueError("perception adapter must return PerceivedDecisionState")
        if perceived.actor_id != actual_state.actor_id:
            violations.append("perceived decision state actor_id mismatch")
        if perceived.state_id != actual_state.state_id:
            violations.append("perceived decision state state_id mismatch")
        try:
            pt=float(perceived.time)
            if not math.isfinite(pt):
                violations.append("perceived decision state time must be finite")
            elif not math.isclose(pt,float(actual_state.time),rel_tol=0.0,abs_tol=1e-12):
                violations.append("perceived decision state time mismatch")
        except Exception:
            violations.append("perceived decision state time must be numeric")
        represented=perceived.represented_state
        if not isinstance(represented,WorldState):
            violations.append("perceived decision state requires projection-compatible WorldState payload")
        else:
            if not math.isfinite(float(represented.time)):
                violations.append("represented projection payload time must be finite")
            elif not math.isclose(float(represented.time),float(actual_state.time),rel_tol=0.0,abs_tol=1e-12):
                violations.append("represented decision-state time must align with actual Layer 1 state time")
            sid=represented.metadata.get("state_id") if hasattr(represented.metadata,"get") else None
            if sid is not None and str(sid) != actual_state.state_id:
                violations.append("represented decision-state state_id does not match actual Layer 1 state_id")
        if perceived.ppp is None:
            violations.append("perceived decision state requires explicit PPP component")
        if expected_retrieval is not None:
            if perceived.retrieval is None:
                violations.append("memory-conditioned perceived decision state must expose current retrieval interface")
            elif perceived.retrieval is not expected_retrieval and perceived.retrieval.retrieval_id != expected_retrieval.retrieval_id:
                violations.append("perceived decision state retrieval does not match licensed current retrieval")
        elif perceived.retrieval is not None:
            violations.append("non-memory canonical snapshot may not inject retrieval without licensed retrieval boundary")
        if expected_expectation is not None:
            if perceived.expectation_state is None:
                violations.append("perceived decision state omitted supplied expectation-state interface")
            elif perceived.expectation_state.expectation_state_id != expected_expectation.expectation_state_id:
                violations.append("perceived decision state expectation-state mismatch")
        elif perceived.expectation_state is not None:
            violations.append("perceived decision state may not inject expectation state without explicit upstream input")
        return PerceivedDecisionStateValidationAssessment(
            not violations,actual_state.actor_id,actual_state.state_id,tuple(violations),
            (
                "P_i(t) is a perception-supplied interface object, not a Layer-1 state primitive",
                "PPP remains distinct from SPV-hat, PVS, X-hat, retrieval, K, confidence, and uncertainty",
                "runtime validates attribution/routing only and does not derive perceived semantics from actual PP/SPV/AVS/X",
                "represented_state is a compatibility projection payload for the existing Layer-2 implementation",
            )
        )

    def _legacy_perceived_decision_state(
            self, actual_state: ActualPersistentStateEnvelope, represented: WorldState, *,
            retrieval: MemoryRetrievalPackage | None = None,
            expectation_state: ExpectationStateReference | None = None
            ) -> PerceivedDecisionState:
        """Compatibility wrapper for pre-v0.56 adapters; does not infer SPV-hat/PVS/X-hat."""
        return PerceivedDecisionState(
            actual_state.actor_id,actual_state.state_id,float(actual_state.time),represented,
            ppp=represented,retrieval=retrieval,expectation_state=expectation_state,
            metadata={"compatibility_mode":"legacy_world_state_as_ppp_interface"}
        )

    def prepare_memory_conditioned_cycle_snapshot(self,
                                                   actual_state: ActualPersistentStateEnvelope,
                                                   memory_state: MemoryStateReference, *,
                                                   query=None, context=None,
                                                   governing_concerns=(),
                                                   expectation_state: ExpectationStateReference | None = None,
                                                   request_trace=None) -> MemoryConditionedCycleSnapshot:
        """Construct one perception-side snapshot through licensed retrieval only.

        M_i(t) is supplied only to the MemoryRetrievalService. The downstream
        perception adapter receives R^M_i(t,q) and optional K_i(t), never raw M_i(t).
        """
        actual_validation=self.validate_actual_persistent_state(actual_state)
        if not actual_validation.valid:
            raise ValueError(f"invalid actual persistent state: {actual_validation.violations}")
        mv=self.validate_memory_state_reference(memory_state,actual_state)
        if mv:
            raise ValueError(f"invalid retained memory state: {mv}")
        if expectation_state is not None:
            if not isinstance(expectation_state,ExpectationStateReference):
                raise ValueError("expectation state must be ExpectationStateReference")
            if expectation_state.actor_id != actual_state.actor_id:
                raise ValueError("expectation state actor_id must match actual state actor_id")
            try:
                kt=float(expectation_state.time)
            except Exception as exc:
                raise ValueError("expectation state time must be numeric") from exc
            if not math.isfinite(kt):
                raise ValueError("expectation state time must be finite")
            if kt > float(actual_state.time)+1e-12:
                raise ValueError("expectation state may not originate in the future relative to current actual state")
        if self.memory_retrieval_service is None:
            raise ValueError("no MemoryRetrievalService is attached")
        request=MemoryRetrievalRequest(
            actual_state.actor_id,memory_state,query,context,tuple(governing_concerns),
            float(actual_state.time),dict(request_trace or {})
        )
        retrieval=self.memory_retrieval_service.retrieve(request)
        rv=self.validate_memory_retrieval_package(request,retrieval,actual_state)
        if rv:
            raise ValueError(f"invalid memory retrieval package: {rv}")
        pds_mapper=getattr(self.world,"perceived_decision_state_from_perception_inputs",None)
        legacy_mapper=getattr(self.world,"represented_state_from_perception_inputs",None)
        if callable(pds_mapper):
            perceived=pds_mapper(actual_state,retrieval,expectation_state)
        elif callable(legacy_mapper):
            represented=legacy_mapper(actual_state,retrieval,expectation_state)
            if not isinstance(represented,WorldState):
                raise ValueError("represented_state_from_perception_inputs() must return WorldState")
            perceived=self._legacy_perceived_decision_state(
                actual_state,represented,retrieval=retrieval,expectation_state=expectation_state
            )
        else:
            raise ValueError("memory-conditioned cycle requires perceived_decision_state_from_perception_inputs() or legacy represented_state_from_perception_inputs()")
        pv=self.validate_perceived_decision_state(
            perceived,actual_state,expected_retrieval=retrieval,expected_expectation=expectation_state
        )
        if not pv.valid:
            raise ValueError(f"invalid perceived decision state: {pv.violations}")
        represented=perceived.represented_state
        return MemoryConditionedCycleSnapshot(
            actual_state,memory_state,retrieval,expectation_state,represented,
            (
                "stored M_i(t) was visible only to the host retrieval service",
                "perception consumed current retrieval R^M_i(t,q), not unrestricted raw memory",
                "K_i(t), when present, remained a distinct opaque expectation-state input",
                "retrieval quality metadata was preserved as object-local information, not truth or a global scalar",
                "typed P_i(t) preserved PPP as one component rather than the container for every perceived condition",
            ),
            perceived
        )

    def evaluate_memory_conditioned_decision_cycle(self,
                                                    actual_state: ActualPersistentStateEnvelope,
                                                    memory_state: MemoryStateReference,
                                                    request: CanonicalDecisionCycleRequest, *,
                                                    query=None, context=None,
                                                    governing_concerns=(),
                                                    expectation_state: ExpectationStateReference | None = None,
                                                    request_trace=None):
        """Run the existing canonical Layer-2 cycle from a licensed memory-conditioned perception snapshot."""
        snapshot=self.prepare_memory_conditioned_cycle_snapshot(
            actual_state,memory_state,query=query,context=context,
            governing_concerns=governing_concerns,expectation_state=expectation_state,
            request_trace=request_trace
        )
        decision=self.evaluate_canonical_decision_cycle(
            snapshot.represented_state,request,
            perceived_decision_state=snapshot.perceived_decision_state
        )
        return snapshot,decision

    def build_prediction_error_request(
            self, prior_actual_state: ActualPersistentStateEnvelope,
            epsilon_result: EpsilonStepResult,
            transition_result: Layer1TransitionResult,
            prior_expectation_state: ExpectationStateReference | None = None,
            selected_projection_record: PolicyProjectionRecord | None = None,
            *, metadata=None) -> PredictionErrorRequest:
        """Build typed mismatch request against the appropriate realized stage."""
        if not epsilon_result.terminal:
            raise ValueError("prediction error requires terminal epsilon result")
        handoff=self.build_layer1_transition_handoff(epsilon_result)
        tv=self.validate_layer1_transition_result(prior_actual_state,handoff,transition_result)
        if not tv.valid:
            raise ValueError(f"prediction error requires validated Layer 1 transition: {tv.violations}")
        if prior_expectation_state is not None:
            if prior_expectation_state.actor_id != prior_actual_state.actor_id:
                raise ValueError("prediction error expectation actor mismatch")
            if float(prior_expectation_state.time) > float(prior_actual_state.time)+1e-12:
                raise ValueError("prediction error prior expectation may not be future-dated")
        pid=epsilon_result.episode.license.selected_policy_id
        if selected_projection_record is not None and selected_projection_record.policy_id != pid:
            raise ValueError("prediction error projection record policy mismatch")
        provenance=self.build_execution_transition_provenance(prior_actual_state,handoff,transition_result,tv)
        return PredictionErrorRequest(
            prior_actual_state.actor_id,epsilon_result.episode.episode_id,pid,
            prior_actual_state.state_id,transition_result.next_state.state_id,
            float(transition_result.next_state.time),epsilon_result.status,
            prior_expectation_state,selected_projection_record,
            tuple(epsilon_result.execution_path),
            tuple(dict(x) for x in epsilon_result.realized_pv_bundles),
            tuple(dict(x) for x in epsilon_result.information_events),
            bool(epsilon_result.return_upstream),tuple(transition_result.notes),
            dict(metadata or {}), execution_transition_provenance=provenance
        )

    def validate_prediction_error_assessment(
            self, request: PredictionErrorRequest,
            assessment: PredictionErrorAssessment) -> PredictionErrorValidationAssessment:
        allowed={"transition","source","policy_outcome","timing","interaction_response"}
        violations=[]
        if not isinstance(assessment,PredictionErrorAssessment):
            raise ValueError("PredictionErrorService must return PredictionErrorAssessment")
        if assessment.actor_id != request.actor_id:
            violations.append("prediction error actor_id mismatch")
        if assessment.episode_id != request.episode_id:
            violations.append("prediction error episode_id mismatch")
        if assessment.selected_policy_id != request.selected_policy_id:
            violations.append("prediction error selected_policy_id mismatch")
        prov=request.execution_transition_provenance
        if prov is None:
            violations.append("prediction error requires execution-transition provenance")
        else:
            if prov.actor_id != request.actor_id or prov.episode_id != request.episode_id:
                violations.append("prediction error provenance attribution mismatch")
            if prov.selected_policy_id != request.selected_policy_id:
                violations.append("prediction error provenance policy mismatch")
            if prov.prior_state_id != request.prior_actual_state_id or prov.next_state_id != request.next_actual_state_id:
                violations.append("prediction error provenance state identity mismatch")
            if prov.execution_status != request.execution_status or tuple(prov.execution_path) != tuple(request.execution_path):
                violations.append("prediction error provenance execution outcome mismatch")
            if prov.realized_pv_evidence_signature is not None and prov.realized_pv_evidence_signature != self._execution_evidence_signature(tuple(request.realized_pv_bundles)):
                violations.append("prediction error realized-PV evidence does not match execution provenance")
            if prov.execution_information_signature is not None and prov.execution_information_signature != self._execution_evidence_signature(tuple(request.execution_information)):
                violations.append("prediction error execution-information evidence does not match execution provenance")
            if prov.return_upstream is not None and bool(prov.return_upstream) != bool(request.return_upstream):
                violations.append("prediction error return-upstream posture does not match execution provenance")
        seen=[]
        for c in assessment.components:
            if not isinstance(c,PredictionErrorComponent):
                violations.append("prediction error components must be PredictionErrorComponent")
                continue
            if c.error_class not in allowed:
                violations.append(f"unsupported prediction error class: {c.error_class}")
            seen.append(c)
        expected_material=any(c.material for c in seen)
        if bool(assessment.material_mismatch) != bool(expected_material):
            violations.append("prediction error material_mismatch must equal presence of material typed component")
        return PredictionErrorValidationAssessment(
            not violations,request.actor_id,request.episode_id,request.selected_policy_id,
            tuple(violations),
            (
                "prediction error is typed and stage-attributed; no generic scalar surprise score is imposed",
                "transition/source/policy-outcome/timing/interaction-response mismatches remain distinct",
            )
        )

    def apply_prediction_error(
            self, prior_actual_state: ActualPersistentStateEnvelope,
            epsilon_result: EpsilonStepResult,
            transition_result: Layer1TransitionResult,
            prior_expectation_state: ExpectationStateReference | None = None,
            selected_projection_record: PolicyProjectionRecord | None = None,
            *, metadata=None):
        if self.prediction_error_service is None:
            raise ValueError("no PredictionErrorService is attached")
        request=self.build_prediction_error_request(
            prior_actual_state,epsilon_result,transition_result,
            prior_expectation_state,selected_projection_record,metadata=metadata
        )
        assessment=self.prediction_error_service.evaluate(request)
        validation=self.validate_prediction_error_assessment(request,assessment)
        if not validation.valid:
            raise ValueError(f"invalid prediction error assessment: {validation.violations}")
        return request,assessment,validation

    def build_post_execution_epistemic_update_request(
            self, prior_actual_state: ActualPersistentStateEnvelope,
            epsilon_result: EpsilonStepResult,
            transition_result: Layer1TransitionResult,
            prior_memory_state: MemoryStateReference,
            prior_expectation_state: ExpectationStateReference | None = None,
            *, metadata=None, prediction_error: PredictionErrorAssessment | None = None) -> PostExecutionEpistemicUpdateRequest:
        """Build an explicit realized-outcome handoff for host-owned M/K updating.

        A valid Layer-1 transition is required first. This prevents execution-side
        information from being treated as an ontological state update or as a
        silently committed memory update before the realized transition is known.
        """
        if not epsilon_result.terminal:
            raise ValueError("epistemic update handoff requires terminal epsilon result")
        handoff=self.build_layer1_transition_handoff(epsilon_result)
        transition_validation=self.validate_layer1_transition_result(
            prior_actual_state,handoff,transition_result
        )
        if not transition_validation.valid:
            raise ValueError(
                f"epistemic update requires validated Layer 1 transition: {transition_validation.violations}"
            )
        mv=self.validate_memory_state_reference(prior_memory_state,prior_actual_state)
        if mv:
            raise ValueError(f"invalid prior memory state: {mv}")
        if prior_expectation_state is not None:
            if not isinstance(prior_expectation_state,ExpectationStateReference):
                raise ValueError("prior expectation state must be ExpectationStateReference")
            if prior_expectation_state.actor_id != prior_actual_state.actor_id:
                raise ValueError("prior expectation state actor_id must match actual state")
            try:
                kt=float(prior_expectation_state.time)
            except Exception as exc:
                raise ValueError("prior expectation state time must be numeric") from exc
            if not math.isfinite(kt) or kt > float(prior_actual_state.time)+1e-12:
                raise ValueError("prior expectation state must be finite and not future-dated")
        provenance=self.build_execution_transition_provenance(
            prior_actual_state,handoff,transition_result,transition_validation
        )
        return PostExecutionEpistemicUpdateRequest(
            prior_actual_state.actor_id,
            epsilon_result.episode.episode_id,
            epsilon_result.episode.license.selected_policy_id,
            epsilon_result.status,
            prior_actual_state.state_id,
            transition_result.next_state.state_id,
            float(transition_result.next_state.time),
            prior_memory_state,
            prior_expectation_state,
            tuple(epsilon_result.execution_path),
            tuple(dict(x) for x in epsilon_result.realized_pv_bundles),
            tuple(dict(x) for x in epsilon_result.information_events),
            bool(epsilon_result.return_upstream),
            tuple(transition_result.notes),
            dict(metadata or {}),
            prediction_error,
            execution_transition_provenance=provenance
        )

    def validate_post_execution_epistemic_update_result(
            self, request: PostExecutionEpistemicUpdateRequest,
            result: PostExecutionEpistemicUpdateResult) -> EpistemicUpdateValidationAssessment:
        """Validate attribution and time continuity without defining learning semantics."""
        violations=[]
        if not isinstance(result,PostExecutionEpistemicUpdateResult):
            raise ValueError("EpistemicUpdateService must return PostExecutionEpistemicUpdateResult")
        if result.actor_id != request.actor_id:
            violations.append("epistemic update actor_id does not match request")
        if result.episode_id != request.episode_id:
            violations.append("epistemic update episode_id does not match request")

        prov=request.execution_transition_provenance
        if prov is None:
            violations.append("epistemic update requires execution-transition provenance")
        else:
            if prov.actor_id != request.actor_id or prov.episode_id != request.episode_id:
                violations.append("epistemic update provenance attribution mismatch")
            if prov.selected_policy_id != request.selected_policy_id:
                violations.append("epistemic update provenance policy mismatch")
            if prov.prior_state_id != request.prior_actual_state_id or prov.next_state_id != request.next_actual_state_id:
                violations.append("epistemic update provenance state identity mismatch")
            if prov.execution_status != request.execution_status or tuple(prov.execution_path) != tuple(request.execution_path):
                violations.append("epistemic update provenance execution outcome mismatch")
            if prov.realized_pv_evidence_signature is not None and prov.realized_pv_evidence_signature != self._execution_evidence_signature(tuple(request.realized_pv_bundles)):
                violations.append("epistemic update realized-PV evidence does not match execution provenance")
            if prov.execution_information_signature is not None and prov.execution_information_signature != self._execution_evidence_signature(tuple(request.execution_information)):
                violations.append("epistemic update execution-information evidence does not match execution provenance")
            if prov.return_upstream is not None and bool(prov.return_upstream) != bool(request.return_upstream):
                violations.append("epistemic update return-upstream posture does not match execution provenance")
        if request.prediction_error is not None and prov is not None:
            if (request.prediction_error.actor_id, request.prediction_error.episode_id, request.prediction_error.selected_policy_id) != (prov.actor_id, prov.episode_id, prov.selected_policy_id):
                violations.append("prediction error attribution does not match epistemic-update provenance")
        nm=result.next_memory_state
        if not isinstance(nm,MemoryStateReference):
            violations.append("next_memory_state must be MemoryStateReference")
        else:
            if nm.actor_id != request.actor_id:
                violations.append("next memory actor_id does not match request actor")
            try:
                nmt=float(nm.time)
                if not math.isfinite(nmt):
                    violations.append("next memory time must be finite")
            except Exception:
                nmt=None
                violations.append("next memory time must be numeric")
            if result.memory_updated:
                if nm.memory_state_id == request.prior_memory_state.memory_state_id:
                    violations.append("memory_updated=True requires a new memory_state_id")
                if nmt is not None and not math.isclose(
                    nmt,float(request.next_actual_time),rel_tol=0.0,abs_tol=1e-12
                ):
                    violations.append("updated memory state time must align with next actual-state time")
            else:
                if nm != request.prior_memory_state:
                    violations.append("memory_updated=False may not silently alter retained memory")

        nk=result.next_expectation_state
        pk=request.prior_expectation_state
        if result.expectation_updated:
            if nk is None:
                violations.append("expectation_updated=True requires next_expectation_state")
            elif not isinstance(nk,ExpectationStateReference):
                violations.append("next_expectation_state must be ExpectationStateReference")
            else:
                if nk.actor_id != request.actor_id:
                    violations.append("next expectation actor_id does not match request actor")
                if pk is not None and nk.expectation_state_id == pk.expectation_state_id:
                    violations.append("expectation_updated=True requires a new expectation_state_id")
                try:
                    nkt=float(nk.time)
                    if not math.isfinite(nkt) or not math.isclose(
                        nkt,float(request.next_actual_time),rel_tol=0.0,abs_tol=1e-12
                    ):
                        violations.append("updated expectation state time must align with next actual-state time")
                except Exception:
                    violations.append("next expectation state time must be numeric")
        else:
            if nk != pk:
                violations.append("expectation_updated=False may not silently alter expectation state")

        return EpistemicUpdateValidationAssessment(
            not violations,request.actor_id,request.episode_id,
            nm.memory_state_id if isinstance(nm,MemoryStateReference) else None,
            nk.expectation_state_id if isinstance(nk,ExpectationStateReference) else None,
            tuple(violations),
            (
                "runtime validated update attribution and temporal continuity only",
                "memory selection/consolidation/forgetting and expectation-learning semantics remain host-owned",
                "memory and expectation updates remain distinct and may occur independently",
            )
        )

    def apply_post_execution_epistemic_update(
            self, prior_actual_state: ActualPersistentStateEnvelope,
            epsilon_result: EpsilonStepResult,
            transition_result: Layer1TransitionResult,
            prior_memory_state: MemoryStateReference,
            prior_expectation_state: ExpectationStateReference | None = None,
            *, metadata=None, prediction_error: PredictionErrorAssessment | None = None):
        """Explicitly invoke host-owned M/K update, optionally carrying typed prediction error."""
        if self.epistemic_update_service is None:
            raise ValueError("no EpistemicUpdateService is attached")
        request=self.build_post_execution_epistemic_update_request(
            prior_actual_state,epsilon_result,transition_result,prior_memory_state,
            prior_expectation_state,metadata=metadata,prediction_error=prediction_error
        )
        result=self.epistemic_update_service.update(request)
        validation=self.validate_post_execution_epistemic_update_result(request,result)
        if not validation.valid:
            raise ValueError(f"invalid epistemic update result: {validation.violations}")
        return request,result,validation

    def evaluate_memory_conditioned_integrated_cycle(
            self, actual_state: ActualPersistentStateEnvelope,
            memory_state: MemoryStateReference,
            request: CanonicalDecisionCycleRequest, *,
            query=None, retrieval_context=None, governing_concerns=(),
            expectation_state: ExpectationStateReference | None = None,
            request_trace=None, execute: bool = False,
            update_epistemic_state: bool = False,
            episode_id: str = "memory-conditioned-cycle",
            max_execution_steps: int = 1,
            execution_observations=()) -> MemoryConditionedIntegratedCycleResult:
        """Run one explicit retrieval-conditioned cycle through optional M/K update.

        This method composes existing boundaries. It does not add memory semantics,
        operator semantics, automatic learning, persistence, or autonomous cycling.
        """
        snapshot,decision=self.evaluate_memory_conditioned_decision_cycle(
            actual_state,memory_state,request,query=query,context=retrieval_context,
            governing_concerns=governing_concerns,expectation_state=expectation_state,
            request_trace=request_trace
        )
        base_notes=(
            "retained memory entered only through MemoryRetrievalService",
            "represented decision state was formed before the canonical operator stack",
            "no automatic execution or learning occurs unless explicitly requested",
        )
        if decision.stopped_at != "Sigma" or decision.selection is None or decision.selection.selected_policy_id is None:
            return MemoryConditionedIntegratedCycleResult(
                actual_state.state_id,memory_state.memory_state_id,
                expectation_state.expectation_state_id if expectation_state else None,
                snapshot,decision,final_actual_state=actual_state,
                final_memory_state=memory_state,final_expectation_state=expectation_state,
                status="memory_cycle_stopped_before_unique_sigma_selection",notes=base_notes
            )
        if not execute:
            if update_epistemic_state:
                raise ValueError("epistemic update requires explicit execution and realized outcome")
            return MemoryConditionedIntegratedCycleResult(
                actual_state.state_id,memory_state.memory_state_id,
                expectation_state.expectation_state_id if expectation_state else None,
                snapshot,decision,final_actual_state=actual_state,
                final_memory_state=memory_state,final_expectation_state=expectation_state,
                status="memory_cycle_selected_not_executed",notes=base_notes
            )

        license=self.build_execution_license_from_cycle(decision,request.domain_frame)
        entry=self.instantiate_execution(
            episode_id,license,entry_sufficient=True,max_steps=max_execution_steps
        )
        if not entry.episode.active:
            if update_epistemic_state:
                raise ValueError("blocked epsilon entry cannot produce post-execution epistemic update")
            return MemoryConditionedIntegratedCycleResult(
                actual_state.state_id,memory_state.memory_state_id,
                expectation_state.expectation_state_id if expectation_state else None,
                snapshot,decision,license,entry,
                final_actual_state=actual_state,final_memory_state=memory_state,
                final_expectation_state=expectation_state,
                status="memory_cycle_execution_blocked",notes=base_notes
            )

        observations=tuple(execution_observations)
        if not observations:
            if update_epistemic_state:
                raise ValueError("epistemic update requires terminal epsilon outcome")
            return MemoryConditionedIntegratedCycleResult(
                actual_state.state_id,memory_state.memory_state_id,
                expectation_state.expectation_state_id if expectation_state else None,
                snapshot,decision,license,None,
                final_actual_state=actual_state,final_memory_state=memory_state,
                final_expectation_state=expectation_state,
                status="memory_cycle_execution_active",
                notes=base_notes+("epsilon instantiated but no execution observation supplied",)
            )

        current=entry.episode
        eps=None
        for obs in observations:
            eps=self.advance_execution(current,obs)
            current=eps.episode
            if eps.terminal:
                break
        if eps is None or not eps.terminal:
            if update_epistemic_state:
                raise ValueError("epistemic update requires terminal epsilon outcome")
            return MemoryConditionedIntegratedCycleResult(
                actual_state.state_id,memory_state.memory_state_id,
                expectation_state.expectation_state_id if expectation_state else None,
                snapshot,decision,license,eps,
                final_actual_state=actual_state,final_memory_state=memory_state,
                final_expectation_state=expectation_state,
                status="memory_cycle_execution_active",notes=base_notes
            )

        handoff=self.build_layer1_transition_handoff(eps)
        transition=self.apply_layer1_transition(actual_state,handoff)
        transition_validation=self.validate_layer1_transition_result(actual_state,handoff,transition)
        final_actual=transition.next_state

        eu_req=eu_res=eu_val=None
        pe_req=pe_res=pe_val=None
        final_memory=memory_state
        final_expectation=expectation_state
        if update_epistemic_state:
            selected_projection=next(
                (r for r in decision.projection_records
                 if decision.selection is not None and r.policy_id==decision.selection.selected_policy_id),
                None
            )
            if self.prediction_error_service is not None:
                pe_req,pe_res,pe_val=self.apply_prediction_error(
                    actual_state,eps,transition,expectation_state,selected_projection,
                    metadata={
                        "retrieval_id":snapshot.retrieval.retrieval_id,
                        "query_trace":snapshot.retrieval.query_trace,
                    }
                )
            eu_req,eu_res,eu_val=self.apply_post_execution_epistemic_update(
                actual_state,eps,transition,memory_state,expectation_state,
                metadata={
                    "retrieval_id":snapshot.retrieval.retrieval_id,
                    "query_trace":snapshot.retrieval.query_trace,
                },
                prediction_error=pe_res
            )
            final_memory=eu_res.next_memory_state
            final_expectation=eu_res.next_expectation_state

        return MemoryConditionedIntegratedCycleResult(
            actual_state.state_id,memory_state.memory_state_id,
            expectation_state.expectation_state_id if expectation_state else None,
            snapshot,decision,license,eps,handoff,transition,transition_validation,
            eu_req,eu_res,eu_val,final_actual,final_memory,final_expectation,
            "memory_cycle_transition_and_epistemic_update_applied"
                if update_epistemic_state else "memory_cycle_transition_applied",
            base_notes+(
                "next M/K references were accepted only from explicit EpistemicUpdateService"
                if update_epistemic_state
                else "M/K references were preserved because no update was requested",
            ),
            prediction_error_request=pe_req,
            prediction_error=pe_res,
            prediction_error_validation=pe_val
        )

    def evaluate_memory_conditioned_cycle_sequence(
            self, initial_actual_state: ActualPersistentStateEnvelope,
            initial_memory_state: MemoryStateReference,
            directives,
            initial_expectation_state: ExpectationStateReference | None = None
            ) -> MemoryConditionedCycleSequenceAssessment:
        """Run a finite host-authored retrieval/decision/execution/update sequence."""
        av=self.validate_actual_persistent_state(initial_actual_state)
        if not av.valid:
            raise ValueError(f"invalid initial actual state: {av.violations}")
        mv=self.validate_memory_state_reference(initial_memory_state,initial_actual_state)
        if mv:
            raise ValueError(f"invalid initial memory state: {mv}")

        ds=tuple(directives)
        actual=initial_actual_state
        memory=initial_memory_state
        expectation=initial_expectation_state
        ledger=[]
        violations=[]
        for idx,d in enumerate(ds):
            if not isinstance(d,MemoryConditionedCycleDirective):
                raise ValueError("memory-conditioned sequence requires MemoryConditionedCycleDirective entries")
            if d.expected_actual_state_id is not None and d.expected_actual_state_id != actual.state_id:
                raise ValueError(f"cycle {idx} expected actual state {d.expected_actual_state_id}, got {actual.state_id}")
            if d.expected_memory_state_id is not None and d.expected_memory_state_id != memory.memory_state_id:
                raise ValueError(f"cycle {idx} expected memory state {d.expected_memory_state_id}, got {memory.memory_state_id}")
            actual_k=expectation.expectation_state_id if expectation is not None else None
            if d.expected_expectation_state_id is not None and d.expected_expectation_state_id != actual_k:
                raise ValueError(f"cycle {idx} expected expectation state {d.expected_expectation_state_id}, got {actual_k}")

            before_actual=actual
            before_memory=memory
            before_expectation=expectation
            result=self.evaluate_memory_conditioned_integrated_cycle(
                actual,memory,d.request,query=d.query,retrieval_context=d.retrieval_context,
                governing_concerns=d.governing_concerns,expectation_state=expectation,
                request_trace=d.request_trace,execute=d.execute,
                update_epistemic_state=d.update_epistemic_state,episode_id=d.episode_id,
                max_execution_steps=d.max_execution_steps,
                execution_observations=d.execution_observations
            )
            actual=result.final_actual_state or actual
            memory=result.final_memory_state or memory
            expectation=result.final_expectation_state

            if actual.actor_id != initial_actual_state.actor_id:
                violations.append(f"cycle {idx}: actual actor identity changed")
            if memory.actor_id != initial_actual_state.actor_id:
                violations.append(f"cycle {idx}: memory actor identity changed")
            if expectation is not None and expectation.actor_id != initial_actual_state.actor_id:
                violations.append(f"cycle {idx}: expectation actor identity changed")
            if float(actual.time) < float(before_actual.time):
                violations.append(f"cycle {idx}: actual time moved backward")
            if float(memory.time) > float(actual.time)+1e-12:
                violations.append(f"cycle {idx}: memory state is future-dated relative to actual state")
            if expectation is not None and float(expectation.time) > float(actual.time)+1e-12:
                violations.append(f"cycle {idx}: expectation state is future-dated relative to actual state")

            selected=(result.decision.selection.selected_policy_id
                      if result.decision.selection is not None else None)
            transitioned=bool(result.transition_validation is not None and result.transition_validation.valid)
            mu=bool(result.epistemic_update_result is not None and
                    result.epistemic_update_result.memory_updated)
            ku=bool(result.epistemic_update_result is not None and
                    result.epistemic_update_result.expectation_updated)
            ledger.append(MemoryConditionedCycleLedgerEntry(
                idx,d.label,before_actual.state_id,before_memory.memory_state_id,
                before_expectation.expectation_state_id if before_expectation else None,
                result.perception_snapshot.retrieval.retrieval_id,
                result.decision.status,selected,
                result.epsilon_result.status if result.epsilon_result else None,
                transitioned,mu,ku,actual.state_id,memory.memory_state_id,
                expectation.expectation_state_id if expectation else None,
                (
                    "next retrieval cue/context came only from the next host directive",
                    "runtime threaded validated actual/M/K references but did not generate learning policy",
                )
            ))

            if result.status == "memory_cycle_execution_active":
                return MemoryConditionedCycleSequenceAssessment(
                    "memory_sequence_stopped_at_active_epsilon",len(ds),len(ledger),
                    tuple(ledger),actual,memory,expectation,tuple(violations),
                    ("later directives were not executed around an active epsilon episode",)
                )

        status="memory_sequence_completed" if not violations else "memory_sequence_invariant_failure"
        return MemoryConditionedCycleSequenceAssessment(
            status,len(ds),len(ledger),tuple(ledger),actual,memory,expectation,
            tuple(violations),
            (
                "finite host-authored retrieval/decision/execution/update sequence only",
                "runtime carries references across cycles but does not persist them outside the process",
                "no retrieval cue, memory update, expectation update, or next cycle is generated autonomously",
            )
        )

    def build_capacity_authority_request(
            self, actual_state: ActualPersistentStateEnvelope
            ) -> CapacityAuthorityRequest:
        """Build structural demand context without interpreting opaque Layer-1 semantics."""
        active=tuple(sorted(
            (c for c in self.active_corridors.values()
             if c.status=="active" and c.remaining_actions),
            key=lambda c:c.plan_id
        ))
        action_ids=[]
        resources=set()
        deadlines=[]
        for corridor in active:
            deadlines.append(float(corridor.deadline))
            for aid in corridor.remaining_actions:
                if aid not in action_ids:
                    action_ids.append(aid)
                action=self.registry.actions.get(aid)
                if action is None:
                    continue
                for rid in action.metadata.get("capacity_demands",{}):
                    resources.add(str(rid))
        return CapacityAuthorityRequest(
            actual_state.actor_id,actual_state.state_id,float(actual_state.time),
            tuple(c.plan_id for c in active),tuple(action_ids),tuple(sorted(resources)),
            max(deadlines) if deadlines else None,
            (
                "runtime supplied only active-corridor/action/resource/deadline structure",
                "host remains sole interpreter of actual persistent individuals, skills, availability, commitments, and restoration dynamics",
            )
        )

    def validate_capacity_authority_envelope(
            self, actual_state: ActualPersistentStateEnvelope,
            envelope: CapacityAuthorityEnvelope
            ) -> CapacityAuthorityValidationAssessment:
        violations=[]
        if not isinstance(envelope,CapacityAuthorityEnvelope):
            return CapacityAuthorityValidationAssessment(False,("capacity authority service returned wrong type",))
        if envelope.actor_id != actual_state.actor_id:
            violations.append("capacity authority actor_id mismatch")
        if envelope.state_id != actual_state.state_id:
            violations.append("capacity authority state_id mismatch")
        if not math.isfinite(float(envelope.state_time)):
            violations.append("capacity authority state_time must be finite")
        elif not math.isclose(float(envelope.state_time),float(actual_state.time),rel_tol=0.0,abs_tol=1e-12):
            violations.append("capacity authority state_time mismatch")
        if not isinstance(envelope.calendar,CapacityCalendar):
            violations.append("capacity authority envelope must contain CapacityCalendar")
        else:
            for period,vals in envelope.calendar.capacities.items():
                if not isinstance(period,int) or isinstance(period,bool) or period < 0:
                    violations.append(f"capacity period offset must be nonnegative int: {period!r}")
                    continue
                if not hasattr(vals,"items"):
                    violations.append(f"capacity period {period} must map resource ids to amounts")
                    continue
                for rid,amount in vals.items():
                    if not str(rid).strip():
                        violations.append(f"capacity period {period} contains blank resource id")
                    try:
                        value=float(amount)
                    except (TypeError,ValueError):
                        violations.append(f"capacity {period}/{rid} is not numeric")
                        continue
                    if not math.isfinite(value) or value < 0.0:
                        violations.append(f"capacity {period}/{rid} must be finite and nonnegative")
        return CapacityAuthorityValidationAssessment(
            not violations,tuple(violations),
            (
                "runtime validated attribution/time and calendar shape only",
                "runtime did not derive capacity from PP/SPV/AVS/context or reinterpret host resource semantics",
            )
        )

    def derive_capacity_authority(
            self, actual_state: ActualPersistentStateEnvelope
            ) -> CapacityAuthorityEnvelope:
        """Invoke the optional host-owned capacity authority service explicitly."""
        if self.capacity_authority_service is None:
            raise ValueError("no CapacityAuthorityService is attached")
        self.validate_actual_persistent_state(actual_state)
        request=self.build_capacity_authority_request(actual_state)
        envelope=self.capacity_authority_service.derive(actual_state,request)
        validation=self.validate_capacity_authority_envelope(actual_state,envelope)
        if not validation.valid:
            raise ValueError(f"invalid derived capacity authority: {validation.violations}")
        return envelope

    def prepare_integrated_request_capacity(
            self, actual_state: ActualPersistentStateEnvelope,
            request: CanonicalDecisionCycleRequest
            ) -> tuple[CanonicalDecisionCycleRequest, CapacityAuthorityEnvelope | None]:
        """Fill missing capacity authority from actual state without overriding explicit authority."""
        if request.joint_recovery_capacity_calendar is not None:
            return request,None
        active_capacity_bearing=any(
            bool(self.registry.actions[aid].metadata.get("capacity_demands",{}))
            for c in self.active_corridors.values()
            if c.status=="active"
            for aid in c.remaining_actions
            if aid in self.registry.actions
        )
        if not active_capacity_bearing or self.capacity_authority_service is None:
            return request,None
        envelope=self.derive_capacity_authority(actual_state)
        enriched=replace(
            request,
            joint_recovery_capacity_calendar=envelope.calendar
        )
        return enriched,envelope

    def prepare_canonical_cycle_snapshot(self, actual_state: ActualPersistentStateEnvelope) -> CanonicalCycleSnapshot:
        """Ask the host to expose a represented Layer-2 state for one actual state.

        This is an integration boundary, not a new perception operator. The
        runtime never opens PP/SPV/AVS/X to manufacture a WorldState.
        """
        actual_validation=self.validate_actual_persistent_state(actual_state)
        if not actual_validation.valid:
            raise ValueError(f"invalid actual persistent state: {actual_validation.violations}")
        pds_mapper=getattr(self.world,"perceived_decision_state_from_actual",None)
        legacy_mapper=getattr(self.world,"represented_state_from_actual",None)
        if callable(pds_mapper):
            perceived=pds_mapper(actual_state)
        elif callable(legacy_mapper):
            represented=legacy_mapper(actual_state)
            if not isinstance(represented,WorldState):
                raise ValueError("represented_state_from_actual() must return WorldState")
            perceived=self._legacy_perceived_decision_state(actual_state,represented)
        else:
            raise ValueError("canonical integrated cycle requires perceived_decision_state_from_actual() or legacy represented_state_from_actual()")
        pv=self.validate_perceived_decision_state(perceived,actual_state)
        if not pv.valid:
            raise ValueError(f"invalid perceived decision state: {pv.violations}")
        return CanonicalCycleSnapshot(
            actual_state,perceived.represented_state,
            (
                "P_i(t) supplied by host perception boundary from opaque Layer-1 actual state",
                "runtime validated only identity/time/routing; it did not derive PPP/SPV-hat/PVS/X-hat semantics",
                "existing WorldState remains the projection-compatible compatibility payload consumed by the current operator implementation",
            ),
            perceived
        )

    def evaluate_integrated_canonical_cycle(self, actual_state: ActualPersistentStateEnvelope,
                                            request: CanonicalDecisionCycleRequest, *,
                                            domain_frame: DomainFrame | None = None,
                                            execute: bool = False,
                                            episode_id: str = "canonical-cycle",
                                            max_execution_steps: int = 1,
                                            execution_observations=(),
                                            prior_transition_provenance: ExecutionTransitionProvenance | None = None) -> CanonicalIntegratedCycleResult:
        """Run one explicit integration pass without creating an autonomous loop.

        By default this stops at Sigma. When ``execute=True`` the host has
        explicitly requested epsilon realization and, if epsilon terminates, an
        explicit Layer-1 transition through the registered transition service.
        No retry, heartbeat, scheduling, persistence, or autonomous re-evaluation
        is introduced here.
        """
        prior_provenance_validation=None
        if prior_transition_provenance is not None:
            prior_provenance_validation=self.validate_execution_transition_provenance(
                prior_transition_provenance, actual_state
            )
            if not prior_provenance_validation.valid:
                raise ValueError(
                    f"invalid prior execution-transition provenance: {prior_provenance_validation.violations}"
                )
        snapshot=self.prepare_canonical_cycle_snapshot(actual_state)
        effective_request,derived_capacity=self.prepare_integrated_request_capacity(actual_state,request)
        decision=self.evaluate_canonical_decision_cycle(
            snapshot.represented_state,effective_request,
            perceived_decision_state=snapshot.perceived_decision_state
        )
        base_notes=(
            "one host-invoked integrated pass; no autonomous runtime loop was created",
            "Layer 1 actual state remained opaque to Layer 2",
        ) + ((
            "starting actual state was explicitly cross-checked against prior epsilon/Layer-1 transition provenance",
        ) if prior_provenance_validation is not None else ()) + (
            ("represented shared capacity was derived by the host-owned CapacityAuthorityService from the current actual-state snapshot",)
            if derived_capacity is not None else ()
        )
        if decision.stopped_at != "Sigma" or decision.selection is None or decision.selection.selected_policy_id is None:
            return CanonicalIntegratedCycleResult(
                actual_state.state_id,decision,final_actual_state=actual_state,
                status="integrated_cycle_stopped_before_unique_sigma_selection",notes=base_notes
            )
        if not execute:
            return CanonicalIntegratedCycleResult(
                actual_state.state_id,decision,final_actual_state=actual_state,
                status="integrated_cycle_selected_not_executed",notes=base_notes
            )

        frame=domain_frame or effective_request.domain_frame
        license=self.build_execution_license_from_cycle(decision,frame)
        entry=self.instantiate_execution(episode_id,license,entry_sufficient=True,max_steps=max_execution_steps)
        episode=entry.episode
        # Terminal-infeasibility licenses are intentionally blocked at epsilon.
        if not episode.active:
            eps=entry
            return CanonicalIntegratedCycleResult(
                actual_state.state_id,decision,license,eps,None,None,None,actual_state,
                "integrated_cycle_execution_blocked",base_notes
            )

        eps=None
        observations=tuple(execution_observations)
        if not observations:
            return CanonicalIntegratedCycleResult(
                actual_state.state_id,decision,license,None,None,None,None,actual_state,
                "integrated_cycle_execution_active",base_notes+(
                    "epsilon episode instantiated but no execution observation was supplied",)
            )
        current=episode
        for obs in observations:
            eps=self.advance_execution(current,obs)
            current=eps.episode
            if eps.terminal:
                break
        if eps is None or not eps.terminal:
            return CanonicalIntegratedCycleResult(
                actual_state.state_id,decision,license,eps,None,None,None,actual_state,
                "integrated_cycle_execution_active",base_notes
            )

        handoff=self.build_layer1_transition_handoff(eps)
        transition=self.apply_layer1_transition(actual_state,handoff)
        validation=self.validate_layer1_transition_result(actual_state,handoff,transition)
        final_state=transition.next_state
        provenance=self.build_execution_transition_provenance(actual_state,handoff,transition,validation)
        return CanonicalIntegratedCycleResult(
            actual_state.state_id,decision,license,eps,handoff,transition,validation,final_state,
            "integrated_cycle_transition_applied" if validation.valid else "integrated_cycle_transition_invalid",
            base_notes+(
                "Layer 1 transition was invoked only after terminal epsilon output and explicit execute=True",
                "transition provenance is an explicit audit carrier; a subsequent cycle remains separately host-invoked",
            ),
            prior_transition_provenance_validation=prior_provenance_validation,
            transition_provenance=provenance
        )

    def evaluate_canonical_cycle_sequence(self, initial_actual_state: ActualPersistentStateEnvelope,
                                          directives) -> CanonicalCycleSequenceAssessment:
        """Execute a finite host-authored sequence for integration stress testing.

        This is deliberately not an autonomous control loop. Every cycle request,
        execution decision, observation sequence, and hysteresis input is supplied
        before invocation by the host. The runtime only threads validated Layer-1
        state forward and records cross-cycle invariants.
        """
        initial_validation=self.validate_actual_persistent_state(initial_actual_state)
        if not initial_validation.valid:
            raise ValueError(f"invalid initial actual persistent state: {initial_validation.violations}")
        ds=tuple(directives)
        current=initial_actual_state
        prior_transition_provenance=None
        ledger=[]
        violations=[]
        for idx,d in enumerate(ds):
            if not isinstance(d,CanonicalCycleDirective):
                raise ValueError("canonical cycle sequence requires CanonicalCycleDirective entries")
            if d.expected_initial_state_id is not None and d.expected_initial_state_id != current.state_id:
                raise ValueError(
                    f"cycle {idx} expected initial state {d.expected_initial_state_id}, got {current.state_id}"
                )
            before_id=current.state_id
            before_time=float(current.time)
            result=self.evaluate_integrated_canonical_cycle(
                current,d.request,execute=d.execute,episode_id=d.episode_id,
                max_execution_steps=d.max_execution_steps,
                execution_observations=d.execution_observations,
                prior_transition_provenance=prior_transition_provenance
            )
            final=result.final_actual_state or current
            if final.actor_id != initial_actual_state.actor_id:
                violations.append(f"cycle {idx}: actor identity changed across sequence")
            if float(final.time) < before_time:
                violations.append(f"cycle {idx}: actual-state time moved backward")
            transitioned=bool(result.transition_result is not None and
                              result.transition_validation is not None and
                              result.transition_validation.valid)
            if transitioned and final.state_id == before_id:
                violations.append(f"cycle {idx}: validated transition reused prior state_id")
            if not transitioned and final.state_id != before_id:
                violations.append(f"cycle {idx}: state_id changed without validated Layer 1 transition")
            regime=(result.decision.regime_assessment.regime
                    if result.decision.regime_assessment is not None else None)
            governing=(result.decision.governing_assessment.governing_domain_ids
                       if result.decision.governing_assessment is not None else ())
            selected=(result.decision.selection.selected_policy_id
                      if result.decision.selection is not None else None)
            mode=(result.execution_license.selection_mode
                  if result.execution_license is not None else None)
            eps_status=result.epsilon_result.status if result.epsilon_result is not None else None
            ret=(result.epsilon_result.return_upstream
                 if result.epsilon_result is not None else None)
            ledger.append(CanonicalCycleLedgerEntry(
                idx,d.label,before_id,before_time,result.decision.status,
                result.decision.stopped_at,regime,tuple(governing),selected,mode,
                eps_status,ret,transitioned,final.state_id,float(final.time),
                (
                    "directive was host-authored; runtime did not derive the next directive",
                    "previous_regime, if any, came only from the directive request",
                )
            ))
            current=final
            prior_transition_provenance=result.transition_provenance if transitioned else None
            # An active epsilon episode owns the execution interval. Starting a new
            # decision cycle here would create hidden concurrent/reselection logic.
            if result.status == "integrated_cycle_execution_active":
                return CanonicalCycleSequenceAssessment(
                    "sequence_stopped_at_active_epsilon",len(ds),len(ledger),tuple(ledger),
                    current,tuple(violations),
                    ("finite host sequence stopped before any later directive because epsilon remained active",
                     "resume requires an explicit host continuation/completion action, not automatic re-selection")
                )
        status="sequence_completed" if not violations else "sequence_invariant_failure"
        return CanonicalCycleSequenceAssessment(
            status,len(ds),len(ledger),tuple(ledger),current,tuple(violations),
            (
                "finite host-authored sequence only; no heartbeat, scheduler, retry, or autonomous policy loop",
                "cross-cycle ledger records regime, governing set, Sigma selection, epsilon status, and Layer-1 state continuity",
                "no anti-oscillation rule is inferred from repeated regime or policy changes",
            )
        )

    def _evaluate_active_joint_recovery_feasibility(
            self, state, request: CanonicalDecisionCycleRequest
            ) -> JointRecoveryFeasibilityAssessment:
        """Evaluate active recovery obligations against represented shared capacity.

        Authority boundary:
        - the runtime owns active-corridor identity/deadlines and the exact scheduler;
        - the host supplies only the represented CapacityCalendar for this decision;
        - the result is an Adequacy-side structural precondition, not a ranking rule;
        - no priority, sacrifice, queue order, or arbitration policy is inferred.
        """
        active=tuple(sorted(
            c.plan_id for c in self.active_corridors.values()
            if c.status=="active" and c.remaining_actions
        ))
        calendar=request.joint_recovery_capacity_calendar

        if not active:
            return JointRecoveryFeasibilityAssessment(
                "no_active_recovery_corridors",(),calendar is not None,True,True,None,
                (
                    "no active recovery obligations require shared-capacity composition",
                    "candidate-specific projected joint sustainment remains a Q/Adequacy fact",
                )
            )

        if calendar is None:
            capacity_bearing=any(
                bool(self.registry.actions[aid].metadata.get("capacity_demands",{}))
                for c in self.active_corridors.values()
                if c.status=="active"
                for aid in c.remaining_actions
                if aid in self.registry.actions
            )
            if capacity_bearing:
                return JointRecoveryFeasibilityAssessment(
                    "active_capacity_authority_required",active,False,False,None,None,
                    (
                        "active recovery corridors contain represented capacity demands but no CapacityCalendar was supplied",
                        "strict canonical selection is blocked rather than accepting a duplicate host assertion of active-set joint sustainment",
                        "the runtime does not infer shared capacity from projection booleans",
                    )
                )
            return JointRecoveryFeasibilityAssessment(
                "active_corridors_have_no_represented_capacity_demands",
                active,False,True,True,None,
                (
                    "active recovery corridors exist but their remaining actions declare no shared-capacity demands",
                    "no capacity composition is required for the current represented active set",
                )
            )

        report=assess_joint_feasibility(
            self.registry,
            tuple(self.active_corridors.values()),
            calendar,
            float(state.time),
            diagnostic_mode=request.joint_recovery_diagnostic_mode
        )
        return JointRecoveryFeasibilityAssessment(
            "active_jointly_feasible" if report.jointly_feasible else "active_jointly_infeasible",
            active,True,True,report.jointly_feasible,report,
            (
                "runtime active-corridor ledger plus supplied CapacityCalendar is authoritative for current active-set joint feasibility",
                "no priority, queue order, or sacrifice rule was applied",
                "candidate-specific future joint sustainment remains downstream projection/Adequacy structure",
            )+tuple(report.notes)
        )

    def _bind_current_period_joint_recovery_actions(self, pi: PiConstructionAssessment,
                                                    joint: JointRecoveryFeasibilityAssessment):
        """Bind earliest-period mandatory recovery actions into every candidate policy.

        The scheduler establishes joint schedulability, not preference. Binding
        ensures Constraints, Q, Adequacy, Sigma, epsilon, and Layer 1 all receive
        the same mandatory current-period action set.
        """
        if pi.policy_space is None:
            raise ValueError("joint recovery binding requires constructed Pi")
        rep=joint.report
        if not joint.runtime_verified or joint.jointly_feasible is not True or rep is None or not rep.schedule:
            return pi,JointRecoveryExecutionBindingAssessment(
                "no_current_period_joint_recovery_binding",None,(),(),
                ("no verified feasible current-period joint schedule was available",)
            )
        first=min(s.period_offset for s in rep.schedule)
        mandatory=tuple(sorted({s.action_id for s in rep.schedule if s.period_offset==first}))
        if not mandatory:
            return pi,JointRecoveryExecutionBindingAssessment(
                "no_current_period_joint_recovery_binding",first,(),(),
                ("verified schedule contained no earliest-period actions",)
            )
        bound=[]
        for c in pi.policy_space.candidates:
            original=tuple(c.action_ids)
            actions=tuple(sorted(set(original).union(mandatory)))
            required=tuple(sorted(set(c.required_action_ids).union(mandatory)))
            md=dict(c.metadata)
            md.update({
                "joint_recovery_bound":True,
                "joint_recovery_period_offset":first,
                "joint_recovery_mandatory_action_ids":mandatory,
                "selected_candidate_action_ids_before_binding":original,
            })
            bound.append(CandidatePolicySet(c.id,actions,required,c.discretionary_action_ids,md,c.policy_class_ids))
        ps=CandidatePolicySpace(
            tuple(bound),pi.policy_space.materially_required_class_ids,
            tuple(pi.policy_space.notes)+(
                "verified earliest-period recovery obligations were bound before Constraints/Q/Adequacy/Sigma",
                "binding preserves execution authority and is not a preference or sacrifice rule",
            )
        )
        updated=replace(pi,policy_space=ps,notes=tuple(pi.notes)+(
            "mandatory current-period recovery action set bound into candidate policies",
        ))
        return updated,JointRecoveryExecutionBindingAssessment(
            "current_period_joint_recovery_bound",first,mandatory,tuple(c.id for c in bound),
            (
                "mandatory actions came only from the earliest period of the verified joint schedule",
                "tuple order is deterministic presentation only and carries no execution priority",
                "future-period recovery steps remain obligations for later host-invoked cycles",
            )
        )

    def audit_cycle_artifact_integrity(self, cycle: CanonicalDecisionCycleAssessment, *, expected_state_id: str | None = None, expected_state_time: float | None = None) -> CycleArtifactIntegrityAssessment:
        """Verify that one cycle's downstream artifacts share one identity basis.

        The audit is implementation hygiene only. It does not add operator authority,
        infer semantic staleness, or compare a cycle with persistent runtime memory.
        """
        violations=[]
        def ids(items, attr='policy_id'):
            return tuple(getattr(x,attr) for x in items)
        g=cycle.governing_assessment; graph=cycle.graph_assessment; pi=cycle.pi_construction
        constraints=cycle.constraints; framing=cycle.domain_framing; adequacy=cycle.adequacy
        records=cycle.projection_records; selection=cycle.selection
        candidates=tuple(c.id for c in (pi.policy_space.candidates if pi and pi.policy_space else ()))
        if len(candidates)!=len(set(candidates)): violations.append('Pi candidate identities are duplicated')
        governing=tuple(g.governing_domain_ids) if g else ()
        if graph and tuple(graph.governing_domain_ids)!=governing: violations.append('Graph governing-domain identity does not match G')
        if pi:
            if tuple(pi.governing_domain_ids)!=governing: violations.append('Pi governing-domain identity does not match G')
            if graph and tuple(pi.visible_seed_ids)!=tuple(graph.seed_ids): violations.append('Pi visible seed identity does not match current Graph seed set')
            if tuple(pi.emitted_candidate_ids)!=candidates: violations.append('Pi emitted candidate identity does not match its policy space')
        constraint_ids=ids(constraints.candidate_results) if constraints else ()
        if constraints and (set(constraint_ids)!=set(candidates) or len(constraint_ids)!=len(candidates)):
            violations.append('Constraints candidate identity does not match current Pi policy space')
        feasible=tuple(constraints.feasible_policy_ids) if constraints else ()
        if any(pid not in set(candidates) for pid in feasible): violations.append('Constraints feasible set contains policy outside current Pi')
        if framing:
            if tuple(framing.governing_domain_ids)!=governing: violations.append('Domain Framing governing identity does not match G')
            if framing.valid and set(framing.framed_domain_ids)!=set(governing): violations.append('valid Domain Framing does not cover exactly the current governing set')
        projection_ids=ids(records)
        if len(projection_ids)!=len(set(projection_ids)): violations.append('authoritative Q policy identities are duplicated')
        if records and (set(projection_ids)!=set(feasible) or len(projection_ids)!=len(feasible)):
            violations.append('authoritative Q policy set does not match current constraint-feasible set')
        q_state_ids=tuple(dict.fromkeys(r.state_id for r in records if r.state_id is not None))
        if len(q_state_ids)>1: violations.append('authoritative Q records contain mixed state_id identities')
        q_state_times=tuple(dict.fromkeys(float(r.state_time) for r in records if r.state_time is not None))
        if len(q_state_times)>1: violations.append('authoritative Q records contain mixed state_time identities')
        if expected_state_id is not None:
            bad=[r.policy_id for r in records if r.state_id!=expected_state_id]
            if bad: violations.append('authoritative Q state_id does not match expected cycle identity: '+','.join(bad))
        if expected_state_time is not None:
            bad=[r.policy_id for r in records if r.state_time is None or not math.isclose(float(r.state_time),float(expected_state_time),rel_tol=0.0,abs_tol=1e-12)]
            if bad: violations.append('authoritative Q state_time does not match expected cycle identity: '+','.join(bad))
        adequacy_ids=ids(adequacy.policy_results) if adequacy else ()
        if adequacy and (set(adequacy_ids)!=set(projection_ids) or len(adequacy_ids)!=len(projection_ids)):
            violations.append('Adequacy policy identity does not match authoritative Q policy set')
        if selection:
            selection_candidate_ids=tuple(c.id for c in selection.candidates)
            if selection_candidate_ids and (set(selection_candidate_ids)!=set(candidates) or len(selection_candidate_ids)!=len(candidates)):
                violations.append('Sigma selection candidate identity does not match current Pi policy space')
            if selection.selected_policy_id is not None and selection.selected_policy_id not in set(candidates):
                violations.append('Sigma selected policy is outside current Pi policy space')
        return CycleArtifactIntegrityAssessment(
            not violations,expected_state_id,expected_state_time,candidates,feasible,projection_ids,adequacy_ids,tuple(violations),
            ('cycle-local identity audit only; no persistence, freshness timeout, or semantic staleness inference',
             'execution licensing re-runs this audit rather than trusting a stored validity flag')
        )

    def evaluate_canonical_decision_cycle(self, state, request: CanonicalDecisionCycleRequest, *, perceived_decision_state: PerceivedDecisionState | None = None) -> CanonicalDecisionCycleAssessment:
        """Execute one host-invoked canonical Layer-2 cycle through Sigma.

        Exact order: PPP -> Phi -> H -> G -> R -> Graph -> Pi -> completeness ->
        Constraints -> Domain Framing -> Adequacy -> Sigma. epsilon is not invoked.
        The method stops at the first failed gate and never mutates host state.
        """
        if not self._strict_phi_h_available():
            raise ValueError("canonical decision cycle requires strict Phi/H host integration")
        if self.registry.governing_configuration is None and not self.registry.recovery_necessities:
            raise ValueError("canonical decision cycle requires canonical G configuration or recovery-necessity structure")
        if self.registry.regime_configuration is None:
            raise ValueError("canonical decision cycle requires registered regime configuration")
        trace=["PPP"]
        if perceived_decision_state is not None:
            if perceived_decision_state.represented_state is not state and perceived_decision_state.represented_state != state:
                raise ValueError("canonical cycle perceived decision state does not wrap supplied WorldState")
            if not math.isclose(float(perceived_decision_state.time),float(state.time),rel_tol=0.0,abs_tol=1e-12):
                raise ValueError("canonical cycle perceived decision state time mismatch")
        perceived=self.world.perceive(state)
        baseline=self._baseline_continuation(perceived)
        phi=self._evaluate_phi_from_perceived(perceived,baseline); trace.append("Phi")
        horizon=self._evaluate_h_from_perceived(perceived,baseline,phi); trace.append("H")
        g=self.identify_governing_domains(horizon.horizons); trace.append("G")
        # Construct DomainAssessment objects only from already-computed Phi/H facts.
        pressure_by={x.domain_id:x.pressure for x in phi.domain_results}
        domain_assessments={}
        for did,d in self.registry.domains.items():
            value=float(self.world.domain_value(perceived,did))
            domain_assessments[did]=DomainAssessment(did,value,pressure_by[did],horizon.horizons[did],did in set(g.governing_domain_ids),d.threshold)
        regime=self.classify_regime(domain_assessments,horizon.horizons,g.governing_domain_ids,
                                    contextual_interruption=request.contextual_interruption,
                                    previous=request.previous_regime); trace.append("R")
        graph=self.construct_graph(request.preservation_object,regime.regime,g.governing_domain_ids,
                                   request.required_graph_family_ids,request.required_graph_path_class_ids,
                                   config=request.graph_config); trace.append("Graph/Seed")
        if graph.status not in {"PASS","CONDITIONAL PASS"}:
            return CanonicalDecisionCycleAssessment(graph.status,"Graph/Seed",tuple(trace),phi,horizon,g,regime,graph,notes=("cycle stopped at Graph validity",))
        pi=self.construct_pi_from_graph(graph,request.materially_required_policy_class_ids,config=request.pi_config); trace.append("Pi")
        if pi.policy_space is None:
            return CanonicalDecisionCycleAssessment(pi.status,"Pi",tuple(trace),phi,horizon,g,regime,graph,pi,notes=("cycle stopped at Pi construction",))
        completeness=self.validate_pi_completeness(pi.policy_space); trace.append("Pi Completeness")
        if not completeness.complete:
            return CanonicalDecisionCycleAssessment(completeness.status,"Pi Completeness",tuple(trace),phi,horizon,g,regime,graph,pi,completeness,notes=("cycle stopped at Pi completeness",))

        joint_recovery=self._evaluate_active_joint_recovery_feasibility(state,request)
        pi,binding=self._bind_current_period_joint_recovery_actions(pi,joint_recovery)

        constraints=self._constraint_system_from_perceived(perceived,pi.policy_space.candidates,
                                                           regime=regime.regime,governing_domain_ids=g.governing_domain_ids); trace.append("Constraints")
        if not constraints.feasible_policy_ids:
            trace.append("Sigma")
            terminal_sigma=self.evaluate_sigma_terminal(constraints.candidate_results)
            terminal_selection=PolicySelectionAssessment(
                "sigma_terminal_policy_selected",tuple(pi.policy_space.candidates),(),terminal_sigma.final_policy_ids,
                terminal_sigma.selected_policy_id,(),None,completeness,None,constraints,None,None,
                ("terminal infeasibility mode entered because Pi_valid is empty",
                 "Sigma preserved hard -> conditional -> soft priority and consumed upstream structured severity comparison"),
                None,terminal_sigma
            )
            return CanonicalDecisionCycleAssessment(
                terminal_selection.status,"Sigma",tuple(trace),phi,horizon,g,regime,graph,pi,completeness,
                constraints=constraints,selection=terminal_selection,
                notes=("terminal Sigma selected from Pi_I only because Pi_valid was empty; Domain Framing, Adequacy, and Q were not invoked",)
            )
        framing=self._validate_domain_framing_against_governing(request.domain_frame,g.governing_domain_ids); trace.append("Domain Framing")
        if not framing.valid:
            return CanonicalDecisionCycleAssessment(framing.status,"Domain Framing",tuple(trace),phi,horizon,g,regime,graph,pi,completeness,constraints,framing,notes=("cycle stopped before Adequacy",))

        if request.joint_recovery_capacity_calendar is not None or joint_recovery.status=="active_capacity_authority_required":
            trace.append("Joint Recovery Feasibility")
        if joint_recovery.status=="active_capacity_authority_required":
            return CanonicalDecisionCycleAssessment(
                status="joint_recovery_capacity_authority_required",
                stopped_at="Joint Recovery Feasibility",
                pipeline_trace=tuple(trace+["Joint Recovery Feasibility"] if "Joint Recovery Feasibility" not in trace else trace),
                pressure_field=phi,
                horizon_assessment=horizon,
                governing_assessment=g,
                regime_assessment=regime,
                graph_assessment=graph,
                pi_construction=pi,
                pi_completeness=completeness,
                constraints=constraints,
                domain_framing=framing,
                notes=(
                    "ordinary Restoration Adequacy and Sigma were blocked because active capacity-bearing recovery obligations lack represented capacity authority",
                    "the host projector may not substitute a joint_sustainment_supported Boolean for the runtime's active-set feasibility computation",
                ),
                joint_recovery_feasibility=joint_recovery,
                joint_recovery_execution_binding=binding
            )
        if joint_recovery.runtime_verified and joint_recovery.jointly_feasible is False:
            return CanonicalDecisionCycleAssessment(
                status="joint_recovery_feasibility_failed",
                stopped_at="Joint Recovery Feasibility",
                pipeline_trace=tuple(trace),
                pressure_field=phi,
                horizon_assessment=horizon,
                governing_assessment=g,
                regime_assessment=regime,
                graph_assessment=graph,
                pi_construction=pi,
                pi_completeness=completeness,
                constraints=constraints,
                domain_framing=framing,
                notes=(
                    "ordinary Restoration Adequacy and Sigma were blocked because the already-active recovery set is jointly infeasible under represented shared capacity/deadlines",
                    "no queue, registration order, pressure ranking, or sacrifice rule was used to resolve the conflict",
                    "no generic arbitration authority is implemented because the reviewed canonical material supplies no universal sacrifice rule",
                ),
                joint_recovery_feasibility=joint_recovery,
                joint_recovery_execution_binding=binding
            )
        projection_model_authority=self.validate_projection_model_authority(request.projection_model_authority,request.projection_horizon)
        if self.projection_service is not None and not projection_model_authority.valid:
            raise ValueError("projection model authority failed closed: " + "; ".join(projection_model_authority.violations))
        projection_input_license=self.validate_projection_causal_inputs(perceived_decision_state,request.projection_required_causal_input_ids)
        if self.projection_service is not None and not projection_input_license.valid:
            raise ValueError("projection causal-input licensing failed closed: " + "; ".join(projection_input_license.violations))
        records={}
        feasible_policy_ids=set(constraints.feasible_policy_ids)
        for candidate in pi.policy_space.candidates:
            if candidate.id not in feasible_policy_ids:
                continue
            record=self._project_policy_record(
                perceived,candidate,candidate_mode="ordinary_adequacy",
                projection_horizon=request.projection_horizon,graph_assessment=graph,
                projection_input_trace=request.projection_input_trace,
                perceived_decision_state=perceived_decision_state,
                projection_input_license_assessment=projection_input_license,
                projection_model_authority=request.projection_model_authority,
                projection_model_authority_assessment=projection_model_authority
            )
            if record is None:
                raise ValueError("canonical decision cycle requires authoritative PolicyProjectionService or project_policy_record() / Q_t(pi)")
            if self.projection_service is None and not record.feasible:
                raise ValueError(f"legacy Q_t(pi) contradicts canonical Constraints for executable policy {candidate.id}")
            records[candidate.id]=record
        q_policy_ids=tuple(records)
        q_signatures={pid:self._projection_record_signature(rec) for pid,rec in records.items()}
        adequacy_records=tuple(records.values())
        adequacy=self.evaluate_restoration_adequacy(request.domain_frame,g.governing_domain_ids,adequacy_records); trace.append("Adequacy")
        unchanged_after_adequacy=all(self._projection_record_signature(records[pid])==sig for pid,sig in q_signatures.items())
        if not unchanged_after_adequacy:
            raise ValueError("Adequacy mutated an authoritative Q_t(pi) record")
        if adequacy.adequate_policy_ids:
            selection=self._standard_selection_from_cycle_records(pi.policy_space.candidates,completeness,framing,constraints,adequacy,records,g.governing_domain_ids)
        else:
            evals=[]
            by_candidate={c.id:c for c in pi.policy_space.candidates}
            feasible_ids=set(constraints.feasible_policy_ids)
            for pid in constraints.feasible_policy_ids:
                c=by_candidate[pid]; rec=records[pid]
                evals.append(PolicySetEvaluation(pid,c.action_ids,True,False,dict(rec.projected_horizons),("policy is valid but recovery-inadequate",),rec.projection_horizon,tuple(rec.right_censored_domain_ids)))
            profile_fn=getattr(self.world,"fallback_structure_profile",None)
            profiles=()
            if callable(profile_fn):
                profiles=tuple(profile_fn(perceived,e.policy_id,by_candidate[e.policy_id].action_ids,tuple(g.governing_domain_ids)) for e in evals)
            fs=self.evaluate_sigma_fallback(tuple(evals),g.governing_domain_ids,profiles)
            selection=PolicySelectionAssessment(
                fs.status,tuple(pi.policy_space.candidates),tuple(evals),fs.stage3_policy_ids or fs.stage1_policy_ids,fs.selected_policy_id,(),None,
                completeness,framing,constraints,adequacy,None,
                ("recovery-unavailable Sigma operated only over Pi_valid after authoritative adequacy failure",),fs
            )
        unchanged_after_sigma=all(self._projection_record_signature(records[pid])==sig for pid,sig in q_signatures.items())
        if not unchanged_after_sigma:
            raise ValueError("Sigma mutated an authoritative Q_t(pi) record")
        sigma_consumed=tuple(e.policy_id for e in selection.evaluations if e.policy_id in records)
        audit=ProjectionConsistencyAudit(
            q_policy_ids,tuple(r.policy_id for r in adequacy_records),sigma_consumed,
            unchanged_after_adequacy,unchanged_after_sigma,
            (
                "Adequacy and Sigma consumed the cycle-local authoritative Q record set without reprojection",
                "projection quality/confidence metadata remained trace evidence and was not converted into a Sigma ranking input",
            )
        )
        trace.append("Sigma")
        status=selection.status
        provisional=CanonicalDecisionCycleAssessment(status,"Sigma",tuple(trace),phi,horizon,g,regime,graph,pi,completeness,constraints,framing,adequacy,selection,tuple(records.values()),(
            "one perceived snapshot and one baseline continuation were reused across Phi/H/G/R",
            "one authoritative Q_t(pi) record was requested per constraint-feasible policy",
            "when a canonical projection service is attached, Q identity/horizon/censoring/trace invariants are validated before Adequacy or Sigma",
            "epsilon was intentionally not invoked by the decision cycle",
        ),joint_recovery,binding,audit,projection_input_license,projection_model_authority)
        # Compatibility discipline: older projectors may use pre-P_i state identifiers.
        # The cycle audit therefore anchors to the authoritative Q set's own identity
        # convention, while callers with a typed identity may invoke the audit with an
        # explicit expected_state_id/time to enforce that stronger crosswalk.
        expected_state_id=next((r.state_id for r in records.values() if r.state_id is not None),None)
        expected_state_time=next((float(r.state_time) for r in records.values() if r.state_time is not None),None)
        integrity=self.audit_cycle_artifact_integrity(provisional,expected_state_id=expected_state_id,expected_state_time=expected_state_time)
        if not integrity.valid:
            raise ValueError("cycle artifact identity integrity failed closed: " + "; ".join(integrity.violations))
        return replace(provisional,cycle_artifact_integrity=integrity)

    def evaluate_recovery_policy_space(self, state, policy_space: CandidatePolicySpace, frame: DomainFrame):
        """Strict v0.23 path using authoritative Q_t(pi) for Restoration Adequacy."""
        completeness=self.validate_pi_completeness(policy_space)
        if not completeness.complete:
            return PolicySelectionAssessment(
                completeness.status,tuple(policy_space.candidates),(),(),None,(),
                None,completeness,None,None,None,None,
                ("policy evaluation stopped at Pi completeness validation",)
            )
        constraints,terminals,records=self._evaluate_constraints_with_projection_records(
            state,policy_space.candidates
        )
        if not constraints.feasible_policy_ids:
            return PolicySelectionAssessment(
                constraints.status,tuple(policy_space.candidates),(),(),None,(),
                None,completeness,None,constraints,None,None,
                ("policy evaluation stopped at Constraints because no candidate is host-feasible",)
            )
        framing=self.validate_domain_framing(state,frame)
        if not framing.valid:
            return PolicySelectionAssessment(
                framing.status,tuple(policy_space.candidates),(),(),None,(),
                None,completeness,framing,constraints,None,None,
                ("policy evaluation stopped at Domain Framing before Adequacy",)
            )
        _,_,_,governing=self._assess_domains(state)
        feasible_records=[records[pid] for pid in constraints.feasible_policy_ids]
        adequacy=self.evaluate_restoration_adequacy(frame,governing,feasible_records)
        return self._evaluate_policy_sets_after_completeness(
            state,policy_space.candidates,pi_completeness=completeness,
            domain_framing=framing,constraints=constraints,
            projected_terminals=terminals,adequacy=adequacy,
            projection_records=records
        )

    def evaluate_framed_policy_space(self, state, policy_space: CandidatePolicySpace, frame: DomainFrame):
        """Compatibility path retaining the pre-v0.23 horizon adequacy heuristic.

        This path is preserved for historical examples/tests only. It is not a
        canonical Restoration Adequacy result because it does not consume Q_t(pi).
        New full-pipeline integrations must use evaluate_recovery_policy_space().
        """
        completeness=self.validate_pi_completeness(policy_space)
        if not completeness.complete:
            return PolicySelectionAssessment(
                completeness.status, tuple(policy_space.candidates), (), (), None, (),
                None, completeness, None, None, None, None,
                ("policy evaluation stopped at Pi completeness validation",)
            )
        constraints,terminals=self._evaluate_constraints_with_terminals(state,policy_space.candidates)
        if not constraints.feasible_policy_ids:
            return PolicySelectionAssessment(
                constraints.status, tuple(policy_space.candidates), (), (), None, (),
                None, completeness, None, constraints, None, None,
                ("policy evaluation stopped at Constraints because no candidate is host-feasible",)
            )
        framing=self.validate_domain_framing(state, frame)
        if not framing.valid:
            return PolicySelectionAssessment(
                framing.status, tuple(policy_space.candidates), (), (), None, (),
                None, completeness, framing, constraints, None, None,
                ("policy evaluation stopped at Domain Framing before Adequacy",)
            )
        return self._evaluate_policy_sets_after_completeness(
            state, policy_space.candidates, pi_completeness=completeness,
            domain_framing=framing, constraints=constraints, projected_terminals=terminals
        )

    def evaluate_policy_space(self, state, policy_space: CandidatePolicySpace):
        """Strict pipeline path: Pi completeness must pass before downstream evaluation."""
        completeness=self.validate_pi_completeness(policy_space)
        if not completeness.complete:
            return PolicySelectionAssessment(
                completeness.status, tuple(policy_space.candidates), (), (), None, (), None, completeness, None, None, None, None,
                ("policy evaluation stopped at Pi completeness validation",)
            )
        return self._evaluate_policy_sets_after_completeness(
            state, policy_space.candidates, pi_completeness=completeness
        )

    def evaluate_policy_sets(self, state, candidates):
        """Compatibility policy evaluator retained for pre-v0.18 callers.

        This method does not claim Pi-completeness validation because no explicit
        required-class basis is supplied. New generic integrations should use
        ``evaluate_policy_space``.
        """
        unverified=PiCompletenessAssessment(
            "pi_completeness_basis_not_supplied", False, (),
            tuple(sorted({cid for c in candidates for cid in c.policy_class_ids})), (),
            tuple(c.id for c in candidates),
            ("compatibility path only; downstream result is not a completeness-validated full-pipeline result",)
        )
        return self._evaluate_policy_sets_after_completeness(state, candidates, pi_completeness=unverified)

    def assess(self,state,*,select=True,capacity_calendar: CapacityCalendar | None = None):
        perceived,domains,horizons,governing=self._assess_domains(state)
        evaluations=[]
        active_next={c.remaining_actions[0] for c in self.active_corridors.values() if c.status=="active" and c.remaining_actions}
        for aid,action in self.registry.actions.items():
            pr=self.world.project(perceived,action)
            if not pr.feasible:
                evaluations.append(ActionEvaluation(aid,False,False,{},pr.reasons or ("hard constraint",))); continue
            terminal=pr.next_state; reasons=()
            plan=self._plan_for_trigger(aid)
            if plan:
                terminal,reasons=self._project_sequence(pr.next_state,plan.continuation_actions)
            else:
                # If this is the required next step of an active corridor, evaluate through its remaining tail.
                matching=[c for c in self.active_corridors.values() if c.status=="active" and c.remaining_actions and c.remaining_actions[0]==aid]
                if matching:
                    tail=matching[0].remaining_actions[1:]
                    terminal,reasons=self._project_sequence(pr.next_state,tail)
            if terminal is None:
                evaluations.append(ActionEvaluation(aid,True,False,{},tuple(reasons))); continue
            _,_,ph,_=self._assess_domains(terminal)
            adequate=all(ph[d]>0 and (self.registry.domains[d].governing_horizon is None or ph[d]>self.registry.domains[d].governing_horizon or ph[d]>=horizons[d]) for d in governing)
            if active_next and aid not in active_next and capacity_calendar is None:
                adequate=False; reasons=("does not continue active recovery corridor when joint capacity is not supplied",)
            evaluations.append(ActionEvaluation(aid,True,adequate,ph,() if adequate else tuple(reasons) or ("not restoration-adequate in prototype corridor gate",)))
        steady=next((e for e in evaluations if e.action_id=="steady"),None)
        active=tuple(sorted(c.plan_id for c in self.active_corridors.values() if c.status=="active" and c.remaining_actions))
        if not active:
            recovery=RecoveryAdequacyAssessment("no_active_corridors", None, ())
        elif capacity_calendar is None:
            recovery=RecoveryAdequacyAssessment(
                "capacity_not_supplied", None, active, notes=(
                    "active recovery corridors exist but no shared-capacity calendar was supplied to ordinary assessment",
                    "individual corridor continuation remains available; joint adequacy is not asserted",
                ))
        else:
            report=assess_joint_feasibility(self.registry, tuple(self.active_corridors.values()), capacity_calendar, state.time)
            recovery=RecoveryAdequacyAssessment(
                status="active_jointly_feasible" if report.jointly_feasible else "active_jointly_infeasible",
                jointly_feasible=report.jointly_feasible, active_corridors=active,
                infeasible_corridor_sets=report.infeasible_corridor_sets, schedule=report.schedule,
                deadline_slack=report.deadline_slack, bottleneck_resources=report.bottleneck_resources,
                residual_capacity=report.residual_capacity, infeasible_sets_complete=report.infeasible_sets_complete,
                notes=report.notes,
            )

        selected=None
        selected_policy=None
        discretionary=None
        policy_selection=None
        selection_blocked = recovery.jointly_feasible is False
        scheduled_now=set()
        if recovery.jointly_feasible and recovery.schedule:
            first_period=min(s.period_offset for s in recovery.schedule)
            scheduled_now={s.action_id for s in recovery.schedule if s.period_offset==first_period}
        if select and not selection_blocked:
            aa=[e for e in evaluations if e.feasible and e.adequate]
            if scheduled_now:
                by_id={e.action_id:e for e in aa}
                required=[]
                first_period=min(s.period_offset for s in recovery.schedule) if recovery.schedule else 0
                for step in recovery.schedule:
                    if step.period_offset==first_period and step.action_id in by_id and step.action_id not in required:
                        required.append(step.action_id)
                residual_before=dict(recovery.residual_capacity.get(first_period, {}))
                residual=dict(residual_before)
                supplemental=[]
                # v0.8: recovery is fixed first. Discretionary candidates are then
                # evaluated as a residual-capacity set. When several incompatible
                # maximal sets remain, selection is explicitly unresolved rather
                # than falling through to action-id ordering.
                optional=[]
                for e in aa:
                    if e.action_id in scheduled_now or e.action_id == "steady":
                        continue
                    action=self.registry.actions[e.action_id]
                    if action.metadata.get("policy_role") != "discretionary":
                        continue
                    demands={str(k):float(v) for k,v in action.metadata.get("capacity_demands",{}).items()}
                    if all(amt <= residual_before.get(r,0.0)+1e-12 for r,amt in demands.items()):
                        optional.append((e,demands))

                eligible=tuple(sorted(e.action_id for e,_ in optional))
                maximal_sets=[]
                if optional:
                    demand_by_id={e.action_id:d for e,d in optional}
                    feasible=[]
                    for n in range(1,len(eligible)+1):
                        for subset in combinations(eligible,n):
                            used={}
                            fits=True
                            for aid in subset:
                                for r,amt in demand_by_id[aid].items():
                                    used[r]=used.get(r,0.0)+amt
                                    if used[r] > residual_before.get(r,0.0)+1e-12:
                                        fits=False; break
                                if not fits: break
                            if fits: feasible.append(subset)
                    maximal_sets=[x for x in feasible if not any(set(x) < set(y) for y in feasible)]

                if not optional:
                    discretionary=DiscretionarySelectionAssessment(
                        "no_eligible_discretionary_actions", (), (), (), residual_before, residual_before,
                        ("no explicitly discretionary adequate action fits current residual capacity",))
                elif len(maximal_sets)==1:
                    supplemental=list(maximal_sets[0])
                    for aid in supplemental:
                        for r,amt in demand_by_id[aid].items():
                            residual[r]=max(0.0,float(residual.get(r,0.0))-amt)
                    status="all_eligible_fit" if set(supplemental)==set(eligible) else "capacity_uniquely_determines_subset"
                    discretionary=DiscretionarySelectionAssessment(
                        status, eligible, tuple(maximal_sets), tuple(supplemental), residual_before, residual,
                        ("discretionary selection required no value tie-break among alternative maximal sets",))
                else:
                    candidates=[]
                    for idx,subset in enumerate(maximal_sets,1):
                        candidates.append(CandidatePolicySet(
                            f"policy_{idx}", tuple(required)+tuple(subset), tuple(required), tuple(subset),
                            {"source":"residual_discretionary_maximal_set"}))
                    policy_selection=self.evaluate_policy_sets(perceived,tuple(candidates))
                    if policy_selection.selected_policy_id is not None:
                        chosen=next(c for c in candidates if c.id==policy_selection.selected_policy_id)
                        supplemental=list(chosen.discretionary_action_ids)
                        for aid in supplemental:
                            for r,amt in demand_by_id[aid].items():
                                residual[r]=max(0.0,float(residual.get(r,0.0))-amt)
                        discretionary=DiscretionarySelectionAssessment(
                            "resolved_by_governing_consequences", eligible, tuple(maximal_sets), tuple(supplemental), residual_before, residual,
                            ("multiple capacity-feasible discretionary sets existed",
                             "a unique policy set was selected by represented governing-domain consequence dominance",))
                    else:
                        discretionary=DiscretionarySelectionAssessment(
                            "competing_maximal_sets_unresolved", eligible, tuple(maximal_sets), (), residual_before, residual_before,
                            ("multiple incompatible maximal discretionary sets fit residual capacity",
                             "their represented governing-domain consequences did not produce a unique dominance result",
                             "no scalar, lexicographic, or action-id tie-break was introduced",))

                ordered=required+supplemental
                if ordered:
                    policy_notes=("required recovery actions are scheduled before supplemental discretionary work",)
                    if supplemental:
                        policy_notes+=("supplemental work fits entirely within residual recovery capacity",)
                    if discretionary.status=="competing_maximal_sets_unresolved":
                        policy_notes+=("residual discretionary conflict remains unresolved; residual capacity is intentionally unused",)
                    selected_policy=SelectedPolicy(tuple(ordered), first_period, True, tuple(required), tuple(supplemental), residual, policy_notes)
                    selected=ordered[0] if len(ordered)==1 else None
            elif aa:
                # Never use action id, registration order, or lexicographic domain
                # ordering as a hidden tie-break. A single action may be selected
                # only when it is the sole adequate action or it simultaneously
                # attains the componentwise maximum on every governing domain.
                chosen=None
                if len(aa)==1:
                    chosen=aa[0]
                elif governing:
                    gov_order=tuple(sorted(governing))
                    maxima={d:max(e.projected_horizons.get(d,-math.inf) for e in aa) for d in gov_order}
                    global_dominators=[
                        e for e in aa
                        if all(e.projected_horizons.get(d,-math.inf) >= maxima[d] for d in gov_order)
                    ]
                    if len(global_dominators)==1:
                        chosen=global_dominators[0]
                if chosen is not None:
                    selected=chosen.action_id
                    selected_policy=SelectedPolicy((chosen.action_id,),0,False,(),(chosen.action_id,),{},(
                        "selected only because one adequate action uniquely componentwise-dominates all alternatives on governing domains",
                    ) if len(aa)>1 else ())
        notes=[
            "v0.9 represents competing residual-capacity policies as first-class candidate policy sets.",
            "Policy-level comparison uses only represented current-governing-domain consequences and remains unresolved when those consequences do not uniquely dominate.",
            "Recovery ordering and capacity scheduling remain prototype formalization surfaces, not a canonical sacrifice rule.",
            "Ordinary action selection never uses action names, registration order, or lexicographic domain order as a tie-break.",
        ]
        if selection_blocked:
            notes.append("Sigma selection withheld because the active recovery set is jointly infeasible; no sacrifice rule has been applied.")
        regime_assessment=None
        regime=regime_label(governing,horizons)
        if self.registry.regime_configuration is not None and governing:
            regime_assessment=self.classify_regime(domains,horizons,governing)
            regime=regime_assessment.regime
        return PVPPAssessment(
            state_time=state.time, domains=domains, governing_domains=tuple(sorted(governing)),
            regime=regime, preservation_targets=tuple(sorted(governing)),
            steady_adequate=bool(steady and steady.adequate), action_evaluations=tuple(evaluations),
            selected_action=selected, pipeline_trace=PIPELINE, recovery_adequacy=recovery,
            selected_policy=selected_policy, discretionary_selection=discretionary,
            policy_selection=policy_selection, regime_assessment=regime_assessment, notes=tuple(notes))

    def assess_recovery_feasibility(self, calendar: CapacityCalendar, *, now: float = 0.0, diagnostic_mode: str = "witness"):
        """Evaluate active recovery corridors jointly without applying a priority rule.

        The ordinary runtime path returns one inclusion-minimal infeasible
        witness when the joint set cannot be scheduled. Exhaustive enumeration
        of every minimal conflict set remains available via
        diagnostic_mode="all_minimal" for offline diagnostics.
        """
        return assess_joint_feasibility(
            self.registry, tuple(self.active_corridors.values()), calendar, now,
            diagnostic_mode=diagnostic_mode,
        )

    def decide(self,state,*,capacity_calendar: CapacityCalendar | None = None): return self.assess(state,select=True,capacity_calendar=capacity_calendar)
    def build_execution_license(self, selection: PolicySelectionAssessment,
                                frame: DomainFrame) -> ExecutionLicenseEnvelope:
        """Construct epsilon's upstream licensing envelope from a resolved strict-pipeline result."""
        if selection.selected_policy_id is None:
            raise ValueError("epsilon requires a policy already selected by Sigma")
        if selection.pi_completeness is None or not selection.pi_completeness.complete:
            raise ValueError("epsilon requires passed Pi completeness")
        if selection.constraints is None:
            raise ValueError("epsilon requires explicit Constraints assessment")
        if selection.domain_framing is None or not selection.domain_framing.valid:
            raise ValueError("epsilon requires valid Domain Framing")
        if selection.adequacy is None:
            raise ValueError("epsilon requires explicit authoritative Restoration Adequacy")
        candidate=next((c for c in selection.candidates if c.id==selection.selected_policy_id),None)
        evaluation=next((e for e in selection.evaluations if e.policy_id==selection.selected_policy_id),None)
        if candidate is None or evaluation is None:
            raise ValueError("selected policy is not present in the evaluated candidate set")
        if selection.selected_policy_id not in selection.adequacy.adequate_policy_ids:
            raise ValueError("selected policy is not in Pi_adequate")
        feasible=selection.selected_policy_id in selection.constraints.feasible_policy_ids
        framed_by_domain={t.domain_id:t.function_id for t in frame.targets}
        gov=tuple(sorted(selection.domain_framing.governing_domain_ids))
        missing=[d for d in gov if d not in framed_by_domain]
        if missing:
            raise ValueError(f"frame does not contain selected licensing targets: {missing}")
        return ExecutionLicenseEnvelope(
            selection.selected_policy_id,candidate.action_ids,gov,
            tuple(framed_by_domain[d] for d in gov),
            True,feasible,True,True,
            ("constructed from the explicit upstream selection/licensing result",
             "epsilon receives the selected policy; no executable-policy object is inserted")
        )

    def build_execution_license_from_cycle(self, cycle: CanonicalDecisionCycleAssessment,
                                           frame: DomainFrame) -> ExecutionLicenseEnvelope:
        """Construct epsilon licensing directly from one completed canonical cycle.

        The method preserves Sigma mode rather than forcing all selected policies
        through ordinary adequacy semantics.

        Standard:
            constraint-feasible + framed + adequate -> entry authorized.

        Recovery-unavailable fallback:
            constraint-feasible + framed + explicitly recovery-inadequate, but
            selected by the canonical fallback mode -> entry authorized while
            adequacy_sufficient remains False.

        Terminal infeasibility:
            Sigma's selected terminal policy is preserved for traceability, but
            epsilon entry is blocked because current epsilon authority forbids
            laundering an upstream-invalid policy into execution. This is an
            explicit source-alignment guard, not a new theory rule.
        """
        selection=cycle.selection
        if cycle.stopped_at != "Sigma" or selection is None or selection.selected_policy_id is None:
            raise ValueError("epsilon licensing requires a canonical cycle resolved by Sigma")
        if cycle.pi_construction is None or cycle.pi_construction.policy_space is None:
            raise ValueError("epsilon licensing requires the cycle's generated policy space")
        if cycle.pi_completeness is None or not cycle.pi_completeness.complete:
            raise ValueError("epsilon licensing requires passed Pi completeness")
        if cycle.governing_assessment is None:
            raise ValueError("epsilon licensing requires governing-domain structure")
        expected_id=(cycle.cycle_artifact_integrity.state_id if cycle.cycle_artifact_integrity is not None else None)
        expected_time=(cycle.cycle_artifact_integrity.state_time if cycle.cycle_artifact_integrity is not None else None)
        fresh_audit=self.audit_cycle_artifact_integrity(cycle,expected_state_id=expected_id,expected_state_time=expected_time)
        if not fresh_audit.valid:
            raise ValueError("epsilon licensing rejected stale or identity-inconsistent cycle artifacts: " + "; ".join(fresh_audit.violations))

        candidates={c.id:c for c in cycle.pi_construction.policy_space.candidates}
        candidate=candidates.get(selection.selected_policy_id)
        if candidate is None:
            raise ValueError("Sigma-selected policy is not present in the cycle policy space")
        selected_candidate_actions=tuple(candidate.metadata.get(
            "selected_candidate_action_ids_before_binding",candidate.action_ids
        ))
        mandatory_recovery_actions=tuple(candidate.metadata.get(
            "joint_recovery_mandatory_action_ids",()
        ))

        mode=("terminal_infeasibility" if selection.terminal_sigma is not None
              else "recovery_unavailable_fallback" if selection.fallback_sigma is not None
              else "standard")
        gov=tuple(cycle.governing_assessment.governing_domain_ids)

        if mode == "terminal_infeasibility":
            if cycle.constraints is None or cycle.constraints.feasible_policy_ids:
                raise ValueError("terminal epsilon posture requires Pi_valid to be empty")
            return ExecutionLicenseEnvelope(
                selection.selected_policy_id,candidate.action_ids,gov,(),
                True,False,False,False,
                (
                    "Sigma terminal selection preserved for execution-boundary traceability",
                    "entry is blocked: terminal policy was selected from Pi_I after Pi_valid became empty",
                    "epsilon may not reinterpret upstream infeasibility as executable validity",
                    "current Sigma/epsilon sources leave terminal selection-to-execution licensing tension explicit",
                ),
                selection_mode=mode,entry_authorized=False,
                selected_candidate_action_ids=selected_candidate_actions,
                mandatory_recovery_action_ids=mandatory_recovery_actions
            )

        if cycle.constraints is None:
            raise ValueError("epsilon licensing requires explicit Constraints assessment")
        feasible=selection.selected_policy_id in cycle.constraints.feasible_policy_ids
        if not feasible:
            raise ValueError("non-terminal epsilon licensing requires a constraint-feasible selected policy")
        if cycle.domain_framing is None or not cycle.domain_framing.valid:
            raise ValueError("non-terminal epsilon licensing requires valid Domain Framing")
        framed_by_domain={t.domain_id:t.function_id for t in frame.targets}
        missing=[d for d in gov if d not in framed_by_domain]
        if missing:
            raise ValueError(f"frame does not contain selected licensing targets: {missing}")
        framed=tuple(framed_by_domain[d] for d in gov)

        if cycle.adequacy is None:
            raise ValueError("non-terminal epsilon licensing requires explicit Restoration Adequacy")
        adequate=selection.selected_policy_id in cycle.adequacy.adequate_policy_ids

        if mode == "standard":
            if not adequate:
                raise ValueError("standard Sigma selection must be recovery-adequate before epsilon entry")
            return ExecutionLicenseEnvelope(
                selection.selected_policy_id,candidate.action_ids,gov,framed,
                True,True,True,True,
                (
                    "constructed from canonical standard Sigma selection",
                    "ordinary epsilon entry preserves Pi completeness, Constraints, framing, and adequacy licensing",
                ),
                selection_mode=mode,entry_authorized=True,
                selected_candidate_action_ids=selected_candidate_actions,
                mandatory_recovery_action_ids=mandatory_recovery_actions
            )

        # Recovery-unavailable fallback is explicitly selected only because no
        # adequate policy exists. Preserve that negative classification instead
        # of pretending the fallback policy became adequate.
        if adequate or cycle.adequacy.adequate_policy_ids:
            raise ValueError("fallback epsilon licensing requires Pi_adequate to be empty")
        return ExecutionLicenseEnvelope(
            selection.selected_policy_id,candidate.action_ids,gov,framed,
            True,True,True,False,
            (
                "constructed from canonical recovery-unavailable Sigma fallback selection",
                "selected fallback policy remains explicitly recovery-inadequate",
                "entry authorization comes from the already-completed fallback selection mode, not from adequacy relabeling",
            ),
            selection_mode=mode,entry_authorized=True,
            selected_candidate_action_ids=selected_candidate_actions,
            mandatory_recovery_action_ids=mandatory_recovery_actions
        )

    @staticmethod
    def _materialize_execution_trace(tail: ExecutionTraceNode | None):
        nodes=[]
        cur=tail
        while cur is not None:
            nodes.append(cur)
            cur=cur.prior
        nodes.reverse()
        return (
            tuple(n.event_id for n in nodes),
            tuple(n.realized_pv_bundle for n in nodes if n.realized_pv_bundle),
            tuple(n.information for n in nodes if n.information),
        )

    def instantiate_execution(self, episode_id: str, license: ExecutionLicenseEnvelope, *,
                              entry_sufficient: bool, max_steps: int) -> EpsilonStepResult:
        """Instantiate x_exec only from an already-selected, upstream-licensed policy."""
        if not episode_id:
            raise ValueError("episode_id required")
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if not license.selected_policy_id or not license.action_ids:
            raise ValueError("epsilon requires one already-selected policy")
        # v0.37: entry authorization is mode-aware and explicit. Standard mode
        # still requires the full ordinary licensing conjunction. Recovery-unavailable
        # fallback preserves adequacy_sufficient=False while remaining executable by
        # explicit Sigma fallback license. Terminal infeasibility remains blocked.
        if license.selection_mode == "standard":
            licensed=(license.entry_authorized and license.pi_complete and
                      license.constraints_feasible and license.framing_valid and
                      license.adequacy_sufficient)
        elif license.selection_mode == "recovery_unavailable_fallback":
            licensed=(license.entry_authorized and license.pi_complete and
                      license.constraints_feasible and license.framing_valid and
                      not license.adequacy_sufficient)
        elif license.selection_mode == "terminal_infeasibility":
            licensed=False
        else:
            raise ValueError(f"unknown epsilon selection mode: {license.selection_mode}")
        episode=ExecutionEpisode(
            episode_id,license,max_steps,0,bool(entry_sufficient),None,
            active=bool(entry_sufficient and licensed)
        )
        if not licensed:
            return EpsilonStepResult(
                episode,"aborted_return",True,True,(),(),(),
                ("execution entry blocked because the upstream licensing envelope is incomplete",
                 "epsilon does not repair or reinterpret upstream invalidity")
            )
        if not entry_sufficient:
            return EpsilonStepResult(
                episode,"aborted_return",True,True,(),(),(),
                ("execution entry sufficiency failed; return upstream before realization",)
            )
        return EpsilonStepResult(
            episode,"active",False,False,(),(),(),
            ("selected policy instantiated as a bounded execution episode",)
        )

    def advance_execution(self, episode: ExecutionEpisode,
                          observation: ExecutionObservation) -> EpsilonStepResult:
        """Advance one bounded realization step without performing Layer 1 transition."""
        if not episode.active:
            raise ValueError("execution episode is already terminal")
        if not observation.event_id:
            raise ValueError("execution observation event_id required")
        node=ExecutionTraceNode(
            observation.event_id,dict(observation.realized_pv_bundle),
            dict(observation.information),episode.trace_tail
        )
        count=episode.step_count+1

        status="active"; terminal=False; return_upstream=False
        notes=[]
        if observation.emergency:
            status="emergency_return"; terminal=True; return_upstream=True
            notes.append("execution exposed immediate governing risk; return to already-defined upstream emergency handling")
        elif observation.failed:
            status="failed"; terminal=True; return_upstream=True
            notes.append("execution failed to realize the licensed path")
        elif observation.material_policy_class_change_required:
            status="partial_realization" if observation.realized_pv_bundle else "aborted_return"
            terminal=True; return_upstream=True
            notes.append("material policy-class change is outside epsilon; return upstream")
        elif not observation.continuation_sufficient:
            status="partial_realization" if observation.realized_pv_bundle else "aborted_return"
            terminal=True; return_upstream=True
            notes.append("continuation sufficiency failed; epsilon may not rewrite upstream adequacy")
        elif observation.completed:
            if observation.completion_sufficient:
                status="completed_staged" if observation.staged else "completed"
                terminal=True
                notes.append("selected policy completed inside the licensed execution corridor")
            else:
                status="partial_realization" if observation.realized_pv_bundle else "aborted_return"
                terminal=True; return_upstream=True
                notes.append("completion sufficiency failed; return upstream rather than laundering completion")
        elif count >= episode.max_steps:
            status="partial_realization" if observation.realized_pv_bundle else "aborted_return"
            terminal=True; return_upstream=True
            notes.append("bounded execution step limit reached; return upstream")
        elif observation.staged:
            notes.append("licensed staged continuation remains active; staging is not a new policy selection")

        next_episode=ExecutionEpisode(
            episode.episode_id,episode.license,episode.max_steps,count,
            episode.entry_sufficient,node,active=not terminal
        )
        if terminal:
            path,bundles,infos=self._materialize_execution_trace(node)
        else:
            path=bundles=infos=()
        return EpsilonStepResult(
            next_episode,status,terminal,return_upstream,bundles,infos,path,
            tuple(notes) + (
                "epsilon does not invoke Sigma, Pi, Domain Framing, Adequacy, or Layer 1 transition",
            )
        )

    def build_layer1_transition_handoff(self, result: EpsilonStepResult) -> Layer1TransitionHandoff:
        """Build the immutable epsilon -> Layer 1 bridge without mutating actual state.

        Canonical epsilon owns realization outputs only. Layer 1 owns the ontological
        transition. The handoff therefore deliberately contains no next_state and this
        method never calls WorldAdapter.execute() or any host mutation surface.
        """
        if not result.terminal:
            raise ValueError("Layer 1 handoff requires a terminal epsilon result")
        allowed={
            "completed","completed_staged","partial_realization",
            "aborted_return","failed","emergency_return"
        }
        if result.status not in allowed:
            raise ValueError(f"non-canonical terminal epsilon status: {result.status}")
        if result.episode.active:
            raise ValueError("terminal epsilon result may not contain an active episode")
        if not result.episode.episode_id or not result.episode.license.selected_policy_id:
            raise ValueError("epsilon handoff requires execution and selected-policy identity")
        if result.status in {"completed","completed_staged"} and result.return_upstream:
            raise ValueError("completed epsilon status may not request upstream return")
        if result.status in {"aborted_return","emergency_return"} and not result.return_upstream:
            raise ValueError("return-class epsilon status must request upstream return")
        return Layer1TransitionHandoff(
            result.episode.episode_id,
            result.episode.license.selected_policy_id,
            result.status,
            tuple(result.execution_path),
            tuple(dict(x) for x in result.realized_pv_bundles),
            tuple(dict(x) for x in result.information_events),
            bool(result.return_upstream),
            (
                "epsilon realization outputs only; no actual persistent-state mutation has occurred",
                "Layer 1 / host transition T exclusively owns the ontological state update",
                "a selected policy, successful execution status, or realized PV bundle is not itself next state",
                "licensed_action_ids carries the complete bounded current-period execution authority",
            ),
            tuple(result.episode.license.action_ids),
            tuple(result.episode.license.mandatory_recovery_action_ids),
        )

    def validate_actual_persistent_state(self, state: ActualPersistentStateEnvelope) -> Layer1TransitionValidationAssessment:
        """Validate only the outer canonical actual-state carrier.

        The runtime intentionally does not interpret PP, SPV, AVS, or X contents.
        """
        violations=[]
        if not state.actor_id:
            violations.append("actor_id is required")
        if not state.state_id:
            violations.append("state_id is required")
        try:
            t=float(state.time)
            if not math.isfinite(t):
                violations.append("state time must be finite")
        except Exception:
            violations.append("state time must be numeric")
        # None means the canonical outer component itself is absent. The runtime
        # does not impose any inner type, arithmetic, or scalar semantics.
        for name,value in (("PP",state.pp),("SPV",state.spv),("AVS",state.avs),("X",state.context)):
            if value is None:
                violations.append(f"{name} component is absent")
        return Layer1TransitionValidationAssessment(
            not violations,state.actor_id,state.state_id,None,tuple(violations),
            ("validated canonical outer state crosswalk only; component semantics remain host/authority owned",)
        )

    def apply_layer1_transition(self, current_state: ActualPersistentStateEnvelope,
                                handoff: Layer1TransitionHandoff) -> Layer1TransitionResult:
        """Explicitly invoke the host-owned Layer 1 transition service.

        This method is never called by the canonical decision cycle or epsilon.
        It exists solely as the explicit bridge after epsilon has produced a
        terminal Layer1TransitionHandoff.
        """
        if self.layer1_transition_service is None:
            raise ValueError("no Layer1TransitionService is attached")
        before=self.validate_actual_persistent_state(current_state)
        if not before.valid:
            raise ValueError(f"invalid current actual persistent state: {before.violations}")
        if not handoff.episode_id or not handoff.selected_policy_id:
            raise ValueError("Layer 1 transition requires epsilon episode and selected-policy identity")
        result=self.layer1_transition_service.transition(current_state,handoff)
        assessment=self.validate_layer1_transition_result(current_state,handoff,result)
        if not assessment.valid:
            raise ValueError(f"invalid Layer 1 transition result: {assessment.violations}")
        return result

    def validate_layer1_transition_result(self, prior: ActualPersistentStateEnvelope,
                                          handoff: Layer1TransitionHandoff,
                                          result: Layer1TransitionResult) -> Layer1TransitionValidationAssessment:
        violations=[]
        if result.episode_id != handoff.episode_id:
            violations.append("transition result episode_id does not match epsilon handoff")
        if result.selected_policy_id != handoff.selected_policy_id:
            violations.append("transition result selected_policy_id does not match epsilon handoff")
        if result.prior_state_id != prior.state_id:
            violations.append("transition result prior_state_id does not match current actual state")
        if not result.transition_applied:
            violations.append("Layer 1 transition service did not confirm transition application")
        nxt=result.next_state
        nxt_assessment=self.validate_actual_persistent_state(nxt)
        violations.extend(nxt_assessment.violations)
        if nxt.actor_id != prior.actor_id:
            violations.append("Layer 1 transition may not silently change actor identity")
        if nxt.state_id == prior.state_id:
            violations.append("applied Layer 1 transition must produce a new state_id")
        try:
            if float(nxt.time) < float(prior.time):
                violations.append("Layer 1 transition time may not move backward")
        except Exception:
            pass
        failed_checks=tuple(k for k,v in result.invariant_checks.items() if not bool(v))
        if failed_checks:
            violations.append(f"Layer 1 invariant checks failed: {failed_checks}")
        return Layer1TransitionValidationAssessment(
            not violations,prior.actor_id,prior.state_id,nxt.state_id,tuple(violations),
            ("runtime validated attribution/identity/time/invariant posture only",
             "PP/SPV/AVS/X transition semantics remain exclusively Layer 1 / host-owned")
        )

    def build_execution_transition_provenance(
            self, prior: ActualPersistentStateEnvelope, handoff: Layer1TransitionHandoff,
            result: Layer1TransitionResult, validation: Layer1TransitionValidationAssessment
            ) -> ExecutionTransitionProvenance:
        """Create an audit-only provenance carrier after a validated Layer-1 transition.

        The carrier confers no decision or execution authority and is not retained
        by the runtime. It can be passed explicitly into a later host-invoked cycle.
        """
        if not validation.valid:
            raise ValueError("execution-transition provenance requires a validated Layer-1 transition")
        return ExecutionTransitionProvenance(
            actor_id=prior.actor_id,
            episode_id=handoff.episode_id,
            selected_policy_id=handoff.selected_policy_id,
            licensed_action_ids=tuple(handoff.licensed_action_ids),
            mandatory_recovery_action_ids=tuple(handoff.mandatory_recovery_action_ids),
            execution_status=handoff.execution_status,
            execution_path=tuple(handoff.execution_path),
            prior_state_id=prior.state_id,
            prior_state_time=float(prior.time),
            next_state_id=result.next_state.state_id,
            next_state_time=float(result.next_state.time),
            transition_applied=bool(result.transition_applied),
            realized_pv_evidence_signature=self._execution_evidence_signature(tuple(handoff.realized_pv_bundles)),
            execution_information_signature=self._execution_evidence_signature(tuple(handoff.execution_information)),
            return_upstream=bool(handoff.return_upstream),
        )

    def validate_execution_transition_provenance(
            self, provenance: ExecutionTransitionProvenance,
            current_state: ActualPersistentStateEnvelope
            ) -> ExecutionTransitionProvenanceAssessment:
        """Validate that a host-supplied starting state is the recorded transition result.

        This is identity/provenance validation only. The runtime does not infer how
        PP/SPV/AVS/X changed and does not store provenance between invocations.
        """
        violations=[]
        if not provenance.actor_id or not provenance.episode_id or not provenance.selected_policy_id:
            violations.append("provenance requires actor, episode, and selected-policy identity")
        if not provenance.transition_applied:
            violations.append("provenance does not record an applied Layer-1 transition")
        if provenance.actor_id != current_state.actor_id:
            violations.append("provenance actor_id does not match current actual state")
        if provenance.next_state_id != current_state.state_id:
            violations.append("current actual state_id does not match provenance next_state_id")
        try:
            if float(provenance.next_state_time) != float(current_state.time):
                violations.append("current actual-state time does not match provenance next_state_time")
            if float(provenance.next_state_time) < float(provenance.prior_state_time):
                violations.append("provenance transition time moves backward")
        except Exception:
            violations.append("provenance state times must be numeric")
        if provenance.next_state_id == provenance.prior_state_id:
            violations.append("provenance applied transition may not reuse prior state_id")
        if len(set(provenance.licensed_action_ids)) != len(provenance.licensed_action_ids):
            violations.append("provenance licensed_action_ids contain duplicates")
        mandatory=set(provenance.mandatory_recovery_action_ids)
        if not mandatory.issubset(set(provenance.licensed_action_ids)):
            violations.append("mandatory recovery actions are not contained in licensed execution authority")
        return ExecutionTransitionProvenanceAssessment(
            not violations,current_state.actor_id,provenance.episode_id,
            provenance.prior_state_id,provenance.next_state_id,tuple(violations),
            (
                "validated explicit epsilon -> handoff -> Layer-1 result identity continuity only",
                "no persistence, state mutation, or causal reconstruction was performed",
            )
        )

    def audit_integrated_cycle_lifecycle_integrity(
            self, integrated: CanonicalIntegratedCycleResult
            ) -> IntegratedCycleLifecycleIntegrityAssessment:
        """Adversarial status/artifact-shape audit for one host-invoked cycle.

        This is a regression/integration surface only. It does not repair a cycle,
        manufacture missing artifacts, advance epsilon, or apply Layer 1.
        """
        violations=[]
        st=integrated.status
        lic=integrated.execution_license
        eps=integrated.epsilon_result
        hand=integrated.handoff
        tr=integrated.transition_result
        tv=integrated.transition_validation
        prov=integrated.transition_provenance
        final=integrated.final_actual_state

        if st == 'integrated_cycle_selected_not_executed':
            if any(x is not None for x in (lic,eps,hand,tr,tv,prov)):
                violations.append('selected-not-executed cycle contains execution or transition artifacts')
        elif st == 'integrated_cycle_execution_blocked':
            if lic is None or eps is None:
                violations.append('execution-blocked cycle requires license and epsilon result')
            if any(x is not None for x in (hand,tr,tv,prov)):
                violations.append('execution-blocked cycle may not contain Layer-1 transition artifacts')
        elif st == 'integrated_cycle_execution_active':
            if lic is None:
                violations.append('active execution cycle requires execution license')
            if eps is not None and eps.terminal:
                violations.append('active execution cycle may not carry terminal epsilon result')
            if any(x is not None for x in (hand,tr,tv,prov)):
                violations.append('active execution cycle may not contain Layer-1 transition artifacts')
        elif st in ('integrated_cycle_transition_applied','integrated_cycle_transition_invalid','executed'):
            if any(x is None for x in (lic,eps,hand,tr,tv,prov,final)):
                violations.append('transition-complete cycle requires complete license/epsilon/handoff/transition/provenance chain')
            if eps is not None and not eps.terminal:
                violations.append('Layer-1 transition may only follow terminal epsilon result')
            if hand is not None and eps is not None and hand.episode_id != eps.episode.episode_id:
                violations.append('handoff episode does not match terminal epsilon episode')
            if tr is not None and integrated.initial_actual_state_id != tr.prior_state_id:
                violations.append('transition prior_state_id does not match integrated initial state')
            if prov is not None and integrated.initial_actual_state_id != prov.prior_state_id:
                violations.append('transition provenance prior_state_id does not match integrated initial state')
            if final is not None and prov is not None:
                if final.state_id != prov.next_state_id or float(final.time) != float(prov.next_state_time):
                    violations.append('final actual state does not match transition provenance next-state identity')
            if st in ('integrated_cycle_transition_applied','executed') and tv is not None and not tv.valid:
                violations.append('transition-applied status carries invalid transition validation')
            if st == 'integrated_cycle_transition_invalid' and tv is not None and tv.valid:
                violations.append('transition-invalid status carries valid transition validation')
        elif st == 'integrated_cycle_stopped_before_unique_sigma_selection':
            if any(x is not None for x in (lic,eps,hand,tr,tv,prov)):
                violations.append('pre-selection stop contains downstream execution artifacts')

        if prov is not None and not prov.transition_applied:
            violations.append('transition provenance exists without applied transition posture')
        return IntegratedCycleLifecycleIntegrityAssessment(
            not violations,st,tuple(violations),(
                'testing/integration-only lifecycle audit; status and artifact shape are checked without creating authority',
                'partial execution remains inside epsilon and cannot be represented as a Layer-1 transition',
                'no persistence, automatic re-entry, repair, or state inference is introduced',
            )
        )

    def audit_post_selection_identity_chain(
            self, integrated: CanonicalIntegratedCycleResult,
            prediction_error_request: PredictionErrorRequest | None = None,
            prediction_error_assessment: PredictionErrorAssessment | None = None,
            epistemic_update_request: PostExecutionEpistemicUpdateRequest | None = None
            ) -> CrossObjectExecutionIdentityAssessment:
        """Adversarial audit for cross-object identity drift after Sigma selection.

        This testing/integration-only surface does not create authority or repair
        mismatches. It checks that independently valid objects have not been
        spliced across episodes, policies, action bundles, or transition chains.
        """
        violations=[]
        lic=integrated.execution_license
        eps=integrated.epsilon_result
        hand=integrated.handoff
        prov=integrated.transition_provenance
        actor = prov.actor_id if prov is not None else ''
        episode = eps.episode.episode_id if eps is not None else (prov.episode_id if prov is not None else '')
        policy = lic.selected_policy_id if lic is not None else ''
        actions = tuple(lic.action_ids) if lic is not None else ()
        if lic is None:
            violations.append('integrated result lacks execution license')
        if eps is None:
            violations.append('integrated result lacks epsilon result')
        if hand is None:
            violations.append('integrated result lacks Layer-1 handoff')
        if prov is None:
            violations.append('integrated result lacks execution-transition provenance')
        if eps is not None and lic is not None:
            if eps.episode.license.selected_policy_id != lic.selected_policy_id:
                violations.append('epsilon policy identity differs from execution license')
            if tuple(eps.episode.license.action_ids) != tuple(lic.action_ids):
                violations.append('epsilon action authority differs from execution license')
        if hand is not None and lic is not None:
            if eps is not None and hand.episode_id != eps.episode.episode_id:
                violations.append('Layer-1 handoff episode identity differs from epsilon episode')
            if hand.selected_policy_id != lic.selected_policy_id:
                violations.append('Layer-1 handoff policy identity differs from execution license')
            if tuple(hand.licensed_action_ids) != tuple(lic.action_ids):
                violations.append('Layer-1 handoff action authority differs from execution license')
        if prov is not None and lic is not None:
            if eps is not None and prov.episode_id != eps.episode.episode_id:
                violations.append('transition provenance episode identity differs from epsilon episode')
            if prov.selected_policy_id != lic.selected_policy_id:
                violations.append('transition provenance policy identity differs from execution license')
            if tuple(prov.licensed_action_ids) != tuple(lic.action_ids):
                violations.append('transition provenance action authority differs from execution license')
        if prediction_error_request is not None:
            if prov is None:
                violations.append('prediction-error request supplied without transition provenance')
            else:
                if (prediction_error_request.actor_id,prediction_error_request.episode_id,prediction_error_request.selected_policy_id) != (prov.actor_id,prov.episode_id,prov.selected_policy_id):
                    violations.append('prediction-error request identity differs from transition provenance')
                if prediction_error_request.prior_actual_state_id != prov.prior_state_id or prediction_error_request.next_actual_state_id != prov.next_state_id:
                    violations.append('prediction-error request state chain differs from transition provenance')
        if prediction_error_assessment is not None:
            if prediction_error_request is None:
                violations.append('prediction-error assessment supplied without its request')
            else:
                if (prediction_error_assessment.actor_id,prediction_error_assessment.episode_id,prediction_error_assessment.selected_policy_id) != (prediction_error_request.actor_id,prediction_error_request.episode_id,prediction_error_request.selected_policy_id):
                    violations.append('prediction-error assessment identity differs from prediction-error request')
        if epistemic_update_request is not None:
            if prov is None:
                violations.append('epistemic-update request supplied without transition provenance')
            else:
                if (epistemic_update_request.actor_id,epistemic_update_request.episode_id,epistemic_update_request.selected_policy_id) != (prov.actor_id,prov.episode_id,prov.selected_policy_id):
                    violations.append('epistemic-update request identity differs from transition provenance')
                if epistemic_update_request.prior_actual_state_id != prov.prior_state_id or epistemic_update_request.next_actual_state_id != prov.next_state_id:
                    violations.append('epistemic-update request state chain differs from transition provenance')
            if prediction_error_assessment is not None and epistemic_update_request.prediction_error is not prediction_error_assessment:
                violations.append('epistemic-update request does not carry the exact audited prediction-error assessment object')
        return CrossObjectExecutionIdentityAssessment(
            not violations,actor,episode,policy,actions,tuple(violations),
            (
                'testing/integration-only cross-object identity audit; no execution or learning authority is created',
                'object identity, episode/policy/action authority, and transition-state continuity are checked without semantic reinterpretation',
            )
        )

    def evaluate_proposal(self,state,action_id):
        a=self.assess(state,select=False)
        return next(e for e in a.action_evaluations if e.action_id==action_id)
    def _resolve_recovery_confirmation(self, confirmation: RecoveryActionConfirmation):
        """Resolve one host-confirmed action without registration-order priority."""
        aid=confirmation.action_id
        if aid not in self.registry.actions:
            raise ValueError(f"execution confirmation references unregistered action: {aid}")

        trigger_matches=[
            self.registry.recovery_plans[pid]
            for pid in self.registry.recovery_trigger_index.get(aid, ())
        ]
        continuation_matches=[
            c for c in self.active_corridors.values()
            if c.status == "active" and c.remaining_actions and c.remaining_actions[0] == aid
        ]

        if confirmation.recovery_plan_id is not None:
            pid=confirmation.recovery_plan_id
            plan=self.registry.recovery_plans.get(pid)
            corridor=self.active_corridors.get(pid)
            if plan is None:
                raise ValueError(f"execution confirmation references unknown recovery plan: {pid}")
            if plan.trigger_action == aid:
                return ("trigger",pid,plan)
            if corridor is not None and corridor.status == "active" and corridor.remaining_actions and corridor.remaining_actions[0] == aid:
                return ("continuation",pid,corridor)
            raise ValueError(f"action {aid} is not the trigger or next continuation action for recovery plan {pid}")

        choices=[("trigger",p.id,p) for p in trigger_matches] + [
            ("continuation",c.plan_id,c) for c in continuation_matches
        ]
        if len(choices) > 1:
            ids=tuple(x[1] for x in choices)
            raise ValueError(
                f"ambiguous recovery bookkeeping for action {aid}; explicit recovery_plan_id required among {ids}"
            )
        if not choices:
            return ("ignored",None,None)
        return choices[0]

    def _apply_recovery_action_confirmations(self, episode_id: str, committed_state_time: float,
                                             action_confirmations,
                                             *, evidence_note: str) -> ExecutionBookkeepingAssessment:
        """Shared recovery-ledger update after transition authority has been established."""
        if not episode_id:
            raise ValueError("recovery bookkeeping requires episode_id")
        if not math.isfinite(float(committed_state_time)):
            raise ValueError("committed_state_time must be finite")

        started=[]; advanced=[]; completed=[]; ignored=[]
        for confirmation in tuple(action_confirmations):
            if not isinstance(confirmation,RecoveryActionConfirmation):
                raise ValueError("recovery bookkeeping requires RecoveryActionConfirmation entries")
            mode,pid,obj=self._resolve_recovery_confirmation(confirmation)
            if mode == "ignored":
                ignored.append(confirmation.action_id)
                continue
            if mode == "trigger":
                plan=obj
                existing=self.active_corridors.get(pid)
                if existing is not None and existing.status == "active":
                    raise ValueError(f"recovery corridor {pid} is already active")
                status="complete" if not plan.continuation_actions else "active"
                self.active_corridors[pid]=ActiveRecoveryCorridor(
                    plan.id,plan.domain_id,plan.function_id,tuple(plan.continuation_actions),
                    float(committed_state_time)+plan.deadline_offset,status
                )
                started.append(pid)
                if status == "complete":
                    completed.append(pid)
                continue

            corridor=obj
            rem=corridor.remaining_actions[1:]
            status="complete" if not rem else "active"
            self.active_corridors[pid]=ActiveRecoveryCorridor(
                corridor.plan_id,corridor.domain_id,corridor.function_id,
                rem,corridor.deadline,status
            )
            advanced.append(pid)
            if status == "complete":
                completed.append(pid)

        return ExecutionBookkeepingAssessment(
            episode_id,
            tuple(started),tuple(advanced),tuple(completed),tuple(ignored),
            (
                evidence_note,
                "runtime-local recovery bookkeeping consumed explicit realized-action attribution only",
                "no PP/world-state mutation occurred in Layer 2",
                "no persistence or memory-state write was performed",
            )
        )

    def build_layer1_execution_commit_from_transition(
            self, prior_actual_state: ActualPersistentStateEnvelope,
            result: EpsilonStepResult,
            transition_result: Layer1TransitionResult,
            action_confirmations=(), *,
            notes=()) -> Layer1ExecutionCommit:
        """Derive the legacy commit record from a validated Layer-1 transition.

        The commit is now a compatibility/audit view. It no longer needs to act as
        a second independent assertion that transition handling occurred.
        """
        if not result.terminal:
            raise ValueError("post-execution bookkeeping requires a terminal epsilon result")
        handoff=self.build_layer1_transition_handoff(result)
        validation=self.validate_layer1_transition_result(
            prior_actual_state,handoff,transition_result
        )
        if not validation.valid:
            raise ValueError(
                f"cannot derive execution commit from invalid Layer 1 transition: {validation.violations}"
            )
        return Layer1ExecutionCommit(
            transition_result.episode_id,
            float(transition_result.next_state.time),
            True,
            tuple(action_confirmations),
            (
                "derived from validated Layer1TransitionResult; not an independent transition assertion",
                *tuple(notes),
            )
        )

    def record_recovery_bookkeeping_from_transition(
            self, prior_actual_state: ActualPersistentStateEnvelope,
            result: EpsilonStepResult,
            transition_result: Layer1TransitionResult,
            action_confirmations=()) -> ExecutionBookkeepingAssessment:
        """Canonical recovery-bookkeeping bridge from validated Layer-1 transition.

        The host must still identify which registered recovery actions were actually
        realized. The runtime does not infer action identity from epsilon event IDs,
        path labels, policy membership, or registration order.
        """
        commit=self.build_layer1_execution_commit_from_transition(
            prior_actual_state,result,transition_result,action_confirmations
        )
        return self._apply_recovery_action_confirmations(
            commit.episode_id,commit.committed_state_time,commit.action_confirmations,
            evidence_note="transition-authoritative recovery bookkeeping followed a validated Layer1TransitionResult"
        )

    def record_layer1_execution_commit(self, result: EpsilonStepResult,
                                       commit: Layer1ExecutionCommit) -> ExecutionBookkeepingAssessment:
        """Legacy v0.38 compatibility surface.

        New canonical integrations should call
        ``record_recovery_bookkeeping_from_transition`` so transition authority is
        established by the validated Layer1TransitionResult rather than duplicated
        by a host-supplied boolean. This method is retained for existing adapters.
        """
        if not result.terminal:
            raise ValueError("post-execution bookkeeping requires a terminal epsilon result")
        if commit.episode_id != result.episode.episode_id:
            raise ValueError("Layer 1 execution commit episode_id does not match epsilon episode")
        if not commit.state_transition_applied:
            raise ValueError("legacy recovery bookkeeping requires confirmed Layer 1 transition handling")
        return self._apply_recovery_action_confirmations(
            commit.episode_id,commit.committed_state_time,commit.action_confirmations,
            evidence_note="legacy compatibility bookkeeping consumed host-supplied Layer1ExecutionCommit"
        )

    def record_execution(self,result: ExecutionResult):
        """Legacy pre-epsilon compatibility recorder.

        Canonical integrations should use epsilon plus a validated Layer1TransitionResult and record_recovery_bookkeeping_from_transition().
        This wrapper preserves the historical examples but is not the canonical
        judgment/execution bookkeeping path.
        """
        if not result.success:
            return
        aid=result.action_id
        confirmation=RecoveryActionConfirmation(aid)
        # Preserve old single-action behavior while removing hidden first-match
        # priority: ambiguous legacy mappings now fail closed.
        mode,pid,obj=self._resolve_recovery_confirmation(confirmation)
        if mode == "ignored":
            return
        if mode == "trigger":
            plan=obj
            self.active_corridors[pid]=ActiveRecoveryCorridor(
                plan.id,plan.domain_id,plan.function_id,plan.continuation_actions,
                result.next_state.time+plan.deadline_offset,
                "complete" if not plan.continuation_actions else "active"
            )
            return
        corridor=obj
        rem=corridor.remaining_actions[1:]
        self.active_corridors[pid]=ActiveRecoveryCorridor(
            corridor.plan_id,corridor.domain_id,corridor.function_id,rem,corridor.deadline,
            "complete" if not rem else "active"
        )
