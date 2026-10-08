from __future__ import annotations

from .models import GovernanceInvalidationSignal, GovernanceReentryAssessment

# Canonical Layer-2 order used only to choose the earliest explicitly invalidated
# artifact.  It does not infer that a later observation invalidates an earlier stage.
CANONICAL_REENTRY_STAGE_ORDER = (
    "PPP", "Phi", "H", "G", "R", "Graph/Seed", "Pi", "Pi Completeness",
    "Constraints", "Domain Framing", "Joint Recovery Feasibility", "Adequacy",
    "Sigma", "epsilon",
)


def assess_governance_reentry(signals: tuple[GovernanceInvalidationSignal, ...]) -> GovernanceReentryAssessment:
    """Validate explicit invalidations and identify the earliest canonical re-entry stage.

    This is decision-only.  The caller supplies the invalidated stage(s); the runtime
    neither guesses causal invalidation nor recomputes any governance operator here.
    """
    violations: list[str] = []
    if not signals:
        violations.append("at least one invalidation signal is required")
    ids = [s.signal_id for s in signals]
    if any(not x.strip() for x in ids):
        violations.append("invalidation signal_id must be nonempty")
    if len(ids) != len(set(ids)):
        violations.append("invalidation signal_id values must be unique")
    for sig in signals:
        if sig.invalidated_stage not in CANONICAL_REENTRY_STAGE_ORDER:
            violations.append(f"unsupported invalidated stage: {sig.invalidated_stage}")
        if not sig.reason.strip():
            violations.append(f"invalidation reason must be nonempty: {sig.signal_id}")
        if not sig.source_kind.strip():
            violations.append(f"invalidation source_kind must be nonempty: {sig.signal_id}")
        if len(sig.evidence_ids) != len(set(sig.evidence_ids)):
            violations.append(f"duplicate evidence identity: {sig.signal_id}")
        if len(sig.artifact_ids) != len(set(sig.artifact_ids)):
            violations.append(f"duplicate artifact identity: {sig.signal_id}")
    valid = not violations
    stages = tuple(dict.fromkeys(s.invalidated_stage for s in signals if s.invalidated_stage in CANONICAL_REENTRY_STAGE_ORDER))
    earliest = min(stages, key=CANONICAL_REENTRY_STAGE_ORDER.index) if valid and stages else None
    return GovernanceReentryAssessment(
        valid=valid,
        signal_ids=tuple(ids),
        invalidated_stages=stages,
        recompute_from_stage=earliest,
        return_to_governance=bool(valid and earliest),
        violations=tuple(violations),
        notes=(
            "earliest stage is selected only among explicitly supplied invalidations",
            "no automatic recomputation, downstream repair, or causal invalidation inference is performed",
        ),
    )


def derive_dependency_invalidations(
    dependencies: tuple["GovernanceArtifactDependency", ...],
    changes: tuple["GovernanceDependencyChange", ...],
) -> "GovernanceDependencyInvalidationAssessment":
    """Derive invalidation signals only from explicit dependency matches.

    A change invalidates an artifact only when fact_kind matches and at least one
    changed fact identity is explicitly registered as a dependency of that artifact.
    No semantic dependency is guessed from names, stage order, or temporal proximity.
    """
    from .models import (
        GovernanceArtifactDependency, GovernanceDependencyChange,
        GovernanceDependencyInvalidationAssessment,
    )
    violations: list[str] = []
    dep_ids = [d.dependency_id for d in dependencies]
    change_ids = [c.change_id for c in changes]
    if len(dep_ids) != len(set(dep_ids)):
        violations.append("dependency_id values must be unique")
    if len(change_ids) != len(set(change_ids)):
        violations.append("change_id values must be unique")
    for dep in dependencies:
        if not dep.dependency_id.strip() or not dep.artifact_id.strip():
            violations.append("dependency and artifact identities must be nonempty")
        if dep.stage not in CANONICAL_REENTRY_STAGE_ORDER:
            violations.append(f"unsupported dependency stage: {dep.stage}")
        if not dep.fact_kind.strip() or not dep.fact_ids:
            violations.append(f"dependency fact_kind/fact_ids required: {dep.dependency_id}")
        if len(dep.fact_ids) != len(set(dep.fact_ids)) or len(dep.provenance_ids) != len(set(dep.provenance_ids)):
            violations.append(f"duplicate dependency fact/provenance identity: {dep.dependency_id}")
    for ch in changes:
        if not ch.change_id.strip() or not ch.fact_kind.strip() or not ch.changed_fact_ids or not ch.reason.strip():
            violations.append(f"change identity/kind/facts/reason required: {ch.change_id}")
        if len(ch.changed_fact_ids) != len(set(ch.changed_fact_ids)) or len(ch.evidence_ids) != len(set(ch.evidence_ids)):
            violations.append(f"duplicate changed fact/evidence identity: {ch.change_id}")
    if violations:
        empty = assess_governance_reentry(())
        return GovernanceDependencyInvalidationAssessment(False, tuple(change_ids), (), (), empty, tuple(violations), ())

    signals = []
    matched = []
    for ch in changes:
        changed = set(ch.changed_fact_ids)
        for dep in dependencies:
            if dep.fact_kind == ch.fact_kind and changed.intersection(dep.fact_ids):
                matched.append(dep.dependency_id)
                signals.append(GovernanceInvalidationSignal(
                    signal_id=f"dep:{ch.change_id}:{dep.dependency_id}",
                    invalidated_stage=dep.stage,
                    reason=ch.reason,
                    source_kind=f"dependency_change:{ch.fact_kind}",
                    evidence_ids=ch.evidence_ids,
                    artifact_ids=(dep.artifact_id,),
                    execution_id=ch.execution_id,
                    configuration_id=ch.configuration_id,
                    notes=("derived only from explicit registered dependency match",),
                ))
    reentry = assess_governance_reentry(tuple(signals)) if signals else GovernanceReentryAssessment(
        valid=True, signal_ids=(), invalidated_stages=(), recompute_from_stage=None,
        return_to_governance=False, violations=(),
        notes=("no registered dependency matched the explicit fact changes", "no invalidation inferred"),
    )
    return GovernanceDependencyInvalidationAssessment(
        valid=True, change_ids=tuple(change_ids), matched_dependency_ids=tuple(dict.fromkeys(matched)),
        invalidation_signals=tuple(signals), reentry=reentry, violations=(),
        notes=("dependency matching is identity-based and explicit", "no recomputation is performed"),
    )


def plan_governance_reentry(
    assessment: GovernanceReentryAssessment,
    signals: tuple[GovernanceInvalidationSignal, ...] = (),
) -> "GovernanceReentryPlan":
    """Build an auditable, decision-only recomputation scope.

    Every canonical result at or downstream of the earliest invalidated stage is
    non-reusable. Earlier results remain reusable *by this plan only*; this does not
    assert that they are valid under facts not represented by the supplied assessment.
    No operator is executed here.
    """
    from .models import GovernanceReentryPlan
    violations: list[str] = []
    if not assessment.valid:
        violations.append("re-entry assessment must be valid")
    if assessment.recompute_from_stage is not None and assessment.recompute_from_stage not in CANONICAL_REENTRY_STAGE_ORDER:
        violations.append(f"unsupported recompute_from_stage: {assessment.recompute_from_stage}")
    if assessment.recompute_from_stage is None and assessment.return_to_governance:
        violations.append("return_to_governance cannot be true without recompute_from_stage")
    if assessment.recompute_from_stage is not None and not assessment.return_to_governance:
        violations.append("recompute_from_stage requires return_to_governance")
    supplied_ids = tuple(s.signal_id for s in signals)
    if signals and supplied_ids != assessment.signal_ids:
        violations.append("supplied signal identities must exactly match the re-entry assessment")
    artifact_ids = tuple(dict.fromkeys(a for s in signals for a in s.artifact_ids))
    if violations:
        return GovernanceReentryPlan(False, None, (), (), tuple(assessment.signal_ids), artifact_ids, False, tuple(violations), ())
    if assessment.recompute_from_stage is None:
        return GovernanceReentryPlan(
            True, None, CANONICAL_REENTRY_STAGE_ORDER, (), tuple(assessment.signal_ids), artifact_ids, False, (),
            ("no invalidated stage is established; no recomputation scope is created", "no operator execution is performed"),
        )
    idx = CANONICAL_REENTRY_STAGE_ORDER.index(assessment.recompute_from_stage)
    return GovernanceReentryPlan(
        True,
        assessment.recompute_from_stage,
        CANONICAL_REENTRY_STAGE_ORDER[:idx],
        CANONICAL_REENTRY_STAGE_ORDER[idx:],
        tuple(assessment.signal_ids),
        artifact_ids,
        False,
        (),
        (
            "all canonical stage results at or downstream of recompute_from_stage are non-reusable for this re-entry",
            "upstream stages are reusable only relative to the supplied invalidation assessment",
            "this plan is decision-only and performs no automatic recomputation",
        ),
    )


def execute_governance_reentry(runtime, plan, actual_state, request):
    """Execute one bounded automatic re-entry pass when a truthful canonical entry exists.

    v0.84 supports only PPP-boundary plans.  That boundary can use the mature
    evaluate_integrated_canonical_cycle(..., execute=False) entry point without
    recomputing any stage that the plan declared reusable.  Later-stage plans fail
    visibly rather than silently restarting at PPP and violating the plan.
    """
    from .models import GovernanceReentryExecutionResult
    if not plan.valid:
        return GovernanceReentryExecutionResult(False, plan.recompute_from_stage, "invalid_reentry_plan",
            violations=("re-entry plan must be valid",))
    if plan.execute_reentry:
        return GovernanceReentryExecutionResult(False, plan.recompute_from_stage, "invalid_reentry_plan",
            violations=("v0.84 requires a decision-only source plan; execution authority is supplied by this explicit call",))
    if plan.recompute_from_stage is None:
        return GovernanceReentryExecutionResult(True, None, "no_reentry_required",
            reused_stage_ids=tuple(plan.reusable_upstream_stages), notes=("no invalidated stage was established; no operator executed",))
    if plan.recompute_from_stage != "PPP":
        return GovernanceReentryExecutionResult(False, plan.recompute_from_stage, "partial_stage_reentry_not_yet_supported",
            reused_stage_ids=tuple(plan.reusable_upstream_stages),
            violations=("v0.84 has no canonical partial-stage execution entry point for this boundary",),
            notes=("runtime refused to restart at PPP because that would recompute stages the plan marked reusable",))
    if plan.reusable_upstream_stages:
        return GovernanceReentryExecutionResult(False, plan.recompute_from_stage, "invalid_reentry_plan",
            violations=("PPP re-entry cannot declare reusable upstream canonical stages",))
    integrated = runtime.evaluate_integrated_canonical_cycle(actual_state, request, execute=False)
    decision = integrated.decision
    recomputed = tuple(decision.pipeline_trace)
    return GovernanceReentryExecutionResult(True, "PPP", "reentry_pass_completed", decision,
        (), recomputed, (), (
            "one bounded automatic governance re-entry pass executed through the mature canonical cycle entry point",
            "epsilon and Layer-1 transition were not executed",
            "no cascading invalidation/re-entry loop was created",
        ))


def validate_reusable_artifact_bundle(
    plan,
    bundle,
    *,
    expected_cycle_id: str,
    expected_initial_state_id: str,
    expected_configuration_id: str,
):
    """Validate identity and stage coverage for a proposed reusable-artifact bundle.

    This is a routing/integrity gate only.  It never re-evaluates an opaque stage
    artifact and never upgrades the plan's evidentiary claim that the stage is reusable.
    """
    from .models import GovernanceReusableArtifactBundleAssessment
    violations: list[str] = []
    if not plan.valid:
        violations.append("re-entry plan must be valid")
    if not bundle.bundle_id.strip() or not bundle.cycle_id.strip():
        violations.append("bundle_id and cycle_id must be nonempty")
    if not bundle.initial_state_id.strip() or not bundle.configuration_id.strip():
        violations.append("initial_state_id and configuration_id must be nonempty")
    if not expected_cycle_id.strip() or not expected_initial_state_id.strip() or not expected_configuration_id.strip():
        violations.append("expected cycle/state/configuration identities must be nonempty")
    if bundle.cycle_id != expected_cycle_id:
        violations.append("bundle cycle_id does not match requested re-entry cycle")
    if bundle.initial_state_id != expected_initial_state_id:
        violations.append("bundle initial_state_id does not match requested re-entry state")
    if bundle.configuration_id != expected_configuration_id:
        violations.append("bundle configuration_id does not match requested runtime configuration")
    stages = tuple(stage for stage, _ in bundle.stage_artifacts)
    if len(stages) != len(set(stages)):
        violations.append("bundle stage identities must be unique")
    unsupported = tuple(s for s in stages if s not in CANONICAL_REENTRY_STAGE_ORDER)
    if unsupported:
        violations.append("bundle contains unsupported canonical stage identity: " + ", ".join(unsupported))
    required = tuple(plan.reusable_upstream_stages)
    if stages != required:
        violations.append("bundle stage coverage/order must exactly match plan reusable_upstream_stages")
    if any(payload is None for _, payload in bundle.stage_artifacts):
        violations.append("reusable stage artifact payloads must be present")
    if len(bundle.provenance_ids) != len(set(bundle.provenance_ids)):
        violations.append("bundle provenance_ids must be unique")
    return GovernanceReusableArtifactBundleAssessment(
        valid=not violations,
        bundle_id=bundle.bundle_id,
        cycle_id=bundle.cycle_id,
        initial_state_id=bundle.initial_state_id,
        configuration_id=bundle.configuration_id,
        reusable_stage_ids=stages,
        violations=tuple(violations),
        notes=(
            "bundle validation establishes identity, ordering, and coverage only",
            "opaque artifact semantic validity is not re-proved by this boundary",
            "no canonical operator is executed and no artifact is recomputed",
        ),
    )



def _terminal_sigma_partial_selection(runtime, pi, completeness, constraints):
    """Reuse canonical terminal Sigma when a partial re-entry produces empty Pi_valid."""
    from .models import PolicySelectionAssessment
    terminal = runtime.evaluate_sigma_terminal(constraints.candidate_results)
    return PolicySelectionAssessment(
        "sigma_terminal_policy_selected", tuple(pi.policy_space.candidates), (), terminal.final_policy_ids,
        terminal.selected_policy_id, (), None, completeness, None, constraints, None, None,
        ("terminal infeasibility mode entered because Pi_valid is empty during bounded re-entry",
         "canonical terminal Sigma was reused without Domain Framing, Adequacy, or Q"),
        None, terminal
    )


def _fallback_sigma_partial_selection(runtime, perceived, pi, completeness, framing, constraints, adequacy, records, governing_domain_ids):
    """Reuse canonical recovery-unavailable fallback Sigma over the authoritative Q set."""
    from .models import PolicySetEvaluation, PolicySelectionAssessment
    by_candidate={c.id:c for c in pi.policy_space.candidates}
    evals=[]
    for pid in constraints.feasible_policy_ids:
        c=by_candidate[pid]; rec=records[pid]
        evals.append(PolicySetEvaluation(pid,c.action_ids,True,False,dict(rec.projected_horizons),("policy is valid but recovery-inadequate",),rec.projection_horizon,tuple(rec.right_censored_domain_ids)))
    profile_fn=getattr(runtime.world,"fallback_structure_profile",None)
    profiles=()
    if callable(profile_fn) and perceived is not None:
        profiles=tuple(profile_fn(perceived,e.policy_id,by_candidate[e.policy_id].action_ids,tuple(governing_domain_ids)) for e in evals)
    fs=runtime.evaluate_sigma_fallback(tuple(evals),governing_domain_ids,profiles)
    return PolicySelectionAssessment(
        fs.status,tuple(pi.policy_space.candidates),tuple(evals),fs.stage3_policy_ids or fs.stage1_policy_ids,fs.selected_policy_id,(),None,
        completeness,framing,constraints,adequacy,None,
        ("recovery-unavailable Sigma operated only over Pi_valid after authoritative adequacy failure during bounded re-entry",),fs
    )

def execute_sigma_reentry(runtime, plan, bundle, bundle_assessment):
    """Execute one truthful standard-Sigma-only re-entry from validated reusable artifacts.

    This v0.86 entry point is deliberately limited to the ordinary adequate-policy
    Sigma path.  It never reprojects Q_t(pi), never recomputes an upstream operator,
    and stops before epsilon.  Recovery-unavailable fallback Sigma remains a later
    bounded entry because it can require host structural-profile input.
    """
    from .models import (
        GovernanceReentryExecutionResult, GoverningAssessment, PiConstructionAssessment,
        PiCompletenessAssessment, ConstraintsAssessment, DomainFramingAssessment,
        SigmaReusableAdequacyArtifact, CanonicalDecisionCycleAssessment,
    )
    violations=[]
    if not plan.valid:
        violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "Sigma":
        violations.append("Sigma re-entry requires recompute_from_stage == Sigma")
    if not bundle_assessment.valid:
        violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id:
        violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages):
        violations.append("bundle assessment stage coverage does not match re-entry plan")
    artifacts=dict(bundle.stage_artifacts)
    required={"G","Pi","Pi Completeness","Constraints","Domain Framing","Adequacy"}
    missing=tuple(sorted(required-set(artifacts)))
    if missing:
        violations.append("Sigma re-entry bundle omits required reusable artifacts: " + ", ".join(missing))
    if violations:
        return GovernanceReentryExecutionResult(False,"Sigma","invalid_sigma_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    g=artifacts["G"]; pi=artifacts["Pi"]; completeness=artifacts["Pi Completeness"]
    constraints=artifacts["Constraints"]; framing=artifacts["Domain Framing"]; aq=artifacts["Adequacy"]
    typed=(("G",g,GoverningAssessment),("Pi",pi,PiConstructionAssessment),("Pi Completeness",completeness,PiCompletenessAssessment),("Constraints",constraints,ConstraintsAssessment),("Domain Framing",framing,DomainFramingAssessment),("Adequacy",aq,SigmaReusableAdequacyArtifact))
    for stage,payload,typ in typed:
        if not isinstance(payload,typ):
            violations.append(f"Sigma re-entry {stage} artifact has wrong type")
    if violations:
        return GovernanceReentryExecutionResult(False,"Sigma","invalid_sigma_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    if pi.policy_space is None:
        violations.append("Sigma re-entry requires reusable Pi policy_space")
    if not completeness.complete:
        violations.append("Sigma re-entry requires reusable Pi completeness pass")
    if not framing.valid:
        violations.append("Sigma re-entry requires reusable Domain Framing pass")
    if not aq.adequacy.adequate_policy_ids:
        violations.append("v0.86 Sigma-only re-entry supports standard adequate-policy Sigma only")
    records={r.policy_id:r for r in aq.projection_records}
    if len(records)!=len(aq.projection_records):
        violations.append("Sigma re-entry projection record identities must be unique")
    if violations:
        return GovernanceReentryExecutionResult(False,"Sigma","sigma_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    selection=runtime._standard_selection_from_cycle_records(
        pi.policy_space.candidates, completeness, framing, constraints,
        aq.adequacy, records, g.governing_domain_ids,
    )
    decision=CanonicalDecisionCycleAssessment(
        selection.status,"Sigma",("Sigma",),
        governing_assessment=g, pi_construction=pi, pi_completeness=completeness,
        constraints=constraints, domain_framing=framing, adequacy=aq.adequacy,
        selection=selection, projection_records=tuple(aq.projection_records),
        notes=("v0.86 standard Sigma-only re-entry reused validated upstream artifacts without reprojection",
               "epsilon was intentionally not invoked",),
    )
    return GovernanceReentryExecutionResult(
        True,"Sigma","reentry_pass_completed",decision,
        tuple(plan.reusable_upstream_stages),("Sigma",),(),
        ("only Sigma was recomputed", "validated upstream artifacts were reused", "epsilon was not executed"),
    )



def execute_domain_framing_reentry(runtime, plan, bundle, bundle_assessment, state, request):
    """Execute one bounded Domain Framing -> projection/Adequacy -> standard Sigma pass.

    Upstream G, Graph, Pi, Pi Completeness, and Constraints are reused exactly.
    Projection records are regenerated only after the newly validated frame, because
    the canonical presentation order marks Joint Recovery Feasibility downstream of
    Domain Framing even though executable dependency binding may occur earlier.
    The pass stops before epsilon and never mutates Layer 1.
    """
    from .models import (
        GovernanceReentryExecutionResult, GoverningAssessment, GraphConstructionAssessment,
        PiConstructionAssessment, PiCompletenessAssessment, ConstraintsAssessment,
        CanonicalDecisionCycleAssessment,
    )
    violations=[]
    if not plan.valid: violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "Domain Framing": violations.append("Domain Framing re-entry requires Domain Framing boundary")
    if not bundle_assessment.valid: violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id: violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages): violations.append("bundle assessment stage coverage does not match re-entry plan")
    artifacts=dict(bundle.stage_artifacts)
    required={"G","Graph/Seed","Pi","Pi Completeness","Constraints"}
    missing=tuple(sorted(required-set(artifacts)))
    if missing: violations.append("Domain Framing re-entry bundle omits required artifacts: "+", ".join(missing))
    if violations:
        return GovernanceReentryExecutionResult(False,"Domain Framing","invalid_domain_framing_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    g=artifacts["G"]; graph=artifacts["Graph/Seed"]; pi=artifacts["Pi"]; completeness=artifacts["Pi Completeness"]; constraints=artifacts["Constraints"]
    typed=(("G",g,GoverningAssessment),("Graph/Seed",graph,GraphConstructionAssessment),("Pi",pi,PiConstructionAssessment),("Pi Completeness",completeness,PiCompletenessAssessment),("Constraints",constraints,ConstraintsAssessment))
    for stage,payload,typ in typed:
        if not isinstance(payload,typ): violations.append(f"Domain Framing re-entry {stage} artifact has wrong type")
    if violations:
        return GovernanceReentryExecutionResult(False,"Domain Framing","domain_framing_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    if pi.policy_space is None: violations.append("Domain Framing re-entry requires reusable Pi policy_space")
    if not completeness.complete: violations.append("Domain Framing re-entry requires reusable Pi completeness pass")
    if not constraints.feasible_policy_ids: violations.append("Domain Framing re-entry requires reusable nonempty Constraints feasible set")
    if violations:
        return GovernanceReentryExecutionResult(False,"Domain Framing","domain_framing_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    framing=runtime._validate_domain_framing_against_governing(request.domain_frame,g.governing_domain_ids)
    if not framing.valid:
        decision=CanonicalDecisionCycleAssessment(framing.status,"Domain Framing",("Domain Framing",),governing_assessment=g,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing)
        return GovernanceReentryExecutionResult(True,"Domain Framing","reentry_pass_stopped",decision,tuple(plan.reusable_upstream_stages),("Domain Framing",),(),("Domain Framing stopped the bounded pass",))
    perceived=runtime.world.perceive(state)
    pma=runtime.validate_projection_model_authority(request.projection_model_authority,request.projection_horizon)
    if runtime.projection_service is not None and not pma.valid:
        return GovernanceReentryExecutionResult(False,"Domain Framing","domain_framing_reentry_projection_authority_failed",reused_stage_ids=tuple(plan.reusable_upstream_stages),recomputed_stage_ids=("Domain Framing",),violations=tuple(pma.violations))
    records={}; feasible=set(constraints.feasible_policy_ids)
    for candidate in pi.policy_space.candidates:
        if candidate.id not in feasible: continue
        rec=runtime._project_policy_record(perceived,candidate,candidate_mode="ordinary_adequacy",projection_horizon=request.projection_horizon,graph_assessment=graph,projection_input_trace=request.projection_input_trace,projection_model_authority=request.projection_model_authority,projection_model_authority_assessment=pma)
        if rec is None: raise ValueError("Domain Framing re-entry requires authoritative Q_t(pi)")
        records[candidate.id]=rec
    adequacy=runtime.evaluate_restoration_adequacy(request.domain_frame,g.governing_domain_ids,tuple(records.values()))
    if not adequacy.adequate_policy_ids:
        selection=_fallback_sigma_partial_selection(runtime,perceived,pi,completeness,framing,constraints,adequacy,records,g.governing_domain_ids)
        stages=("Domain Framing","Joint Recovery Feasibility","Adequacy","Sigma")
        decision=CanonicalDecisionCycleAssessment(selection.status,"Sigma",stages,governing_assessment=g,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing,adequacy=adequacy,selection=selection,projection_records=tuple(records.values()),notes=("v0.120 canonical recovery-unavailable fallback Sigma continuation","epsilon was intentionally not invoked"))
        return GovernanceReentryExecutionResult(True,"Domain Framing","reentry_pass_completed",decision,tuple(plan.reusable_upstream_stages),stages,(),("fallback Sigma completed the bounded re-entry pass","epsilon was not executed"))
    selection=runtime._standard_selection_from_cycle_records(pi.policy_space.candidates,completeness,framing,constraints,adequacy,records,g.governing_domain_ids)
    stages=("Domain Framing","Joint Recovery Feasibility","Adequacy","Sigma")
    decision=CanonicalDecisionCycleAssessment(selection.status,"Sigma",stages,governing_assessment=g,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing,adequacy=adequacy,selection=selection,projection_records=tuple(records.values()),notes=("v0.115 recomputed Domain Framing and its downstream projection/Adequacy/Sigma lineage","epsilon was intentionally not invoked"))
    return GovernanceReentryExecutionResult(True,"Domain Framing","reentry_pass_completed",decision,tuple(plan.reusable_upstream_stages),stages,(),("validated upstream artifacts were reused","epsilon was not executed"))


def execute_adequacy_reentry(runtime, plan, bundle, bundle_assessment):
    """Execute one bounded Adequacy->standard-Sigma re-entry from reusable artifacts.

    No stage upstream of Adequacy is recomputed, Q_t(pi) is not regenerated, and the
    pass stops before epsilon.  v0.87 deliberately supports only the standard Sigma
    path after recomputed Adequacy; fallback Sigma remains separately bounded.
    """
    from .models import (
        GovernanceReentryExecutionResult, GoverningAssessment, PiConstructionAssessment,
        PiCompletenessAssessment, ConstraintsAssessment, DomainFramingAssessment,
        AdequacyReusableProjectionArtifact, AdequacyReusableDomainFramingArtifact, CanonicalDecisionCycleAssessment,
    )
    violations=[]
    if not plan.valid:
        violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "Adequacy":
        violations.append("Adequacy re-entry requires recompute_from_stage == Adequacy")
    if not bundle_assessment.valid:
        violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id:
        violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages):
        violations.append("bundle assessment stage coverage does not match re-entry plan")
    artifacts=dict(bundle.stage_artifacts)
    required={"G","Pi","Pi Completeness","Constraints","Domain Framing","Joint Recovery Feasibility"}
    missing=tuple(sorted(required-set(artifacts)))
    if missing:
        violations.append("Adequacy re-entry bundle omits required reusable artifacts: " + ", ".join(missing))
    if violations:
        return GovernanceReentryExecutionResult(False,"Adequacy","invalid_adequacy_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    g=artifacts["G"]; pi=artifacts["Pi"]; completeness=artifacts["Pi Completeness"]
    constraints=artifacts["Constraints"]; framing=artifacts["Domain Framing"]
    q=artifacts["Joint Recovery Feasibility"]
    typed=(("G",g,GoverningAssessment),("Pi",pi,PiConstructionAssessment),("Pi Completeness",completeness,PiCompletenessAssessment),("Constraints",constraints,ConstraintsAssessment),("Domain Framing",framing,AdequacyReusableDomainFramingArtifact),("Joint Recovery Feasibility",q,AdequacyReusableProjectionArtifact))
    for stage,payload,typ in typed:
        if not isinstance(payload,typ):
            violations.append(f"Adequacy re-entry {stage} artifact has wrong type")
    if violations:
        return GovernanceReentryExecutionResult(False,"Adequacy","invalid_adequacy_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    if pi.policy_space is None:
        violations.append("Adequacy re-entry requires reusable Pi policy_space")
    if not completeness.complete:
        violations.append("Adequacy re-entry requires reusable Pi completeness pass")
    if not framing.assessment.valid:
        violations.append("Adequacy re-entry requires reusable Domain Framing pass")
    records={r.policy_id:r for r in q.projection_records}
    if len(records)!=len(q.projection_records):
        violations.append("Adequacy re-entry projection record identities must be unique")
    feasible_ids=tuple(constraints.feasible_policy_ids)
    if set(records) != set(feasible_ids):
        violations.append("Adequacy re-entry Q_t(pi) coverage must exactly match Constraints feasible_policy_ids")
    if violations:
        return GovernanceReentryExecutionResult(False,"Adequacy","adequacy_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    adequacy=runtime.evaluate_restoration_adequacy(framing.frame,g.governing_domain_ids,tuple(q.projection_records))
    if not adequacy.adequate_policy_ids:
        selection=_fallback_sigma_partial_selection(runtime,None,pi,completeness,framing.assessment,constraints,adequacy,records,g.governing_domain_ids)
        decision=CanonicalDecisionCycleAssessment(selection.status,"Sigma",("Adequacy","Sigma"),governing_assessment=g,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing.assessment,adequacy=adequacy,selection=selection,projection_records=tuple(q.projection_records),notes=("v0.120 canonical recovery-unavailable fallback Sigma continuation from reusable authoritative Q","epsilon was intentionally not invoked"))
        return GovernanceReentryExecutionResult(True,"Adequacy","reentry_pass_completed",decision,tuple(plan.reusable_upstream_stages),("Adequacy","Sigma"),(),("fallback Sigma completed the bounded re-entry pass","epsilon was not executed"))
    selection=runtime._standard_selection_from_cycle_records(
        pi.policy_space.candidates, completeness, framing.assessment, constraints,
        adequacy, records, g.governing_domain_ids,
    )
    decision=CanonicalDecisionCycleAssessment(
        selection.status,"Sigma",("Adequacy","Sigma"),
        governing_assessment=g, pi_construction=pi, pi_completeness=completeness,
        constraints=constraints, domain_framing=framing.assessment, adequacy=adequacy,
        selection=selection, projection_records=tuple(q.projection_records),
        notes=("v0.87 Adequacy re-entry reused validated upstream artifacts and authoritative Q_t(pi)",
               "only Adequacy and standard Sigma were recomputed", "epsilon was intentionally not invoked"),
    )
    return GovernanceReentryExecutionResult(
        True,"Adequacy","reentry_pass_completed",decision,
        tuple(plan.reusable_upstream_stages),("Adequacy","Sigma"),(),
        ("validated upstream artifacts and Q_t(pi) were reused", "epsilon was not executed"),
    )


def assess_joint_recovery_reentry_readiness(plan, cycle):
    """Audit whether the current re-entry plan can truthfully support joint-recovery re-entry.

    This function deliberately does not execute joint recovery.  v0.88 preserves the
    pre-binding Pi artifact and exposes a dependency-ordering issue: joint recovery can
    rewrite Pi before Constraints, so a plan that treats Constraints as reusable is not
    a sufficient recomputation scope.
    """
    from .models import JointRecoveryReentryReadinessAssessment
    violations=[]
    if not plan.valid:
        violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "Joint Recovery Feasibility":
        violations.append("readiness audit requires a Joint Recovery Feasibility boundary plan")
    preserved=getattr(cycle,"pi_before_joint_recovery_binding",None) is not None
    if not preserved:
        violations.append("originating cycle does not preserve pre-binding Pi")
    # Joint recovery binding occurs before Constraints in the executable kernel.
    # Therefore Constraints cannot be reused after a joint-recovery invalidation.
    scope_ok="Constraints" not in tuple(plan.reusable_upstream_stages)
    if not scope_ok:
        violations.append("re-entry plan incorrectly treats Constraints as reusable even though joint-recovery binding can change the Pi consumed by Constraints")
    ready=not violations
    return JointRecoveryReentryReadinessAssessment(
        ready,
        "joint_recovery_reentry_ready" if ready else "joint_recovery_reentry_dependency_scope_insufficient",
        preserved,scope_ok,tuple(violations),
        (
            "v0.88 is an audit/readiness gate only; no joint-recovery operator is executed",
            "pre-binding Pi is now preserved for future truthful recomputation",
            "presentation-stage order must not override executable data dependencies",
        )
    )


def apply_executable_dependency_scope(plan):
    """Repair a decision-only re-entry scope using explicit executable dependencies.

    v0.89 adds one narrowly proven dependency rule: Joint Recovery Feasibility can
    bind mandatory current-period actions into Pi before Constraints. Therefore a
    Joint Recovery invalidation cannot reuse Constraints, Domain Framing, Adequacy,
    Sigma, or epsilon even though the presentation order places Joint Recovery later.

    No other dependency is inferred here. No operator is executed.
    """
    from .models import GovernanceReentryPlan
    if not plan.valid:
        return plan
    if plan.recompute_from_stage != "Joint Recovery Feasibility":
        return plan
    reusable = ("PPP", "Phi", "H", "G", "R", "Graph/Seed", "Pi", "Pi Completeness")
    nonreusable = ("Joint Recovery Feasibility", "Constraints", "Domain Framing", "Adequacy", "Sigma", "epsilon")
    return GovernanceReentryPlan(
        True,
        "Joint Recovery Feasibility",
        reusable,
        nonreusable,
        tuple(plan.signal_ids),
        tuple(plan.invalidated_artifact_ids),
        False,
        (),
        tuple(plan.notes) + (
            "v0.89 executable dependency scope applied: joint-recovery binding can change Pi before Constraints",
            "Constraints and its downstream consumers are therefore non-reusable for this re-entry",
            "no dependency beyond the explicitly established joint-recovery binding lineage is inferred",
        ),
    )


def execute_joint_recovery_reentry(runtime, plan, bundle, bundle_assessment, state, request):
    """Execute one bounded Joint Recovery -> Constraints -> Framing -> Adequacy -> Sigma pass.

    The executor consumes the preserved pre-binding Pi from the reusable bundle.  It
    recomputes active joint-recovery feasibility and mandatory current-period binding,
    then every executable consumer of that bound Pi.  It never recomputes PPP through
    Pi Completeness and stops before epsilon.  v0.90 supports the standard Sigma
    continuation; fallback/terminal Sigma remain explicit bounded outcomes.
    """
    from .models import (
        GovernanceReentryExecutionResult, GoverningAssessment, RegimeAssessment,
        GraphConstructionAssessment, PiConstructionAssessment, PiCompletenessAssessment,
        CanonicalDecisionCycleAssessment,
    )
    violations=[]
    if not plan.valid: violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "Joint Recovery Feasibility":
        violations.append("Joint Recovery re-entry requires Joint Recovery Feasibility boundary")
    if not bundle_assessment.valid: violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id: violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages):
        violations.append("bundle assessment stage coverage does not match re-entry plan")
    artifacts=dict(bundle.stage_artifacts)
    required={"G","R","Graph/Seed","Pi","Pi Completeness"}
    missing=tuple(sorted(required-set(artifacts)))
    if missing: violations.append("Joint Recovery re-entry bundle omits required artifacts: "+", ".join(missing))
    if violations:
        return GovernanceReentryExecutionResult(False,"Joint Recovery Feasibility","invalid_joint_recovery_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    g=artifacts["G"]; regime=artifacts["R"]; graph=artifacts["Graph/Seed"]; pi0=artifacts["Pi"]; completeness=artifacts["Pi Completeness"]
    for stage,payload,typ in (("G",g,GoverningAssessment),("R",regime,RegimeAssessment),("Graph/Seed",graph,GraphConstructionAssessment),("Pi",pi0,PiConstructionAssessment),("Pi Completeness",completeness,PiCompletenessAssessment)):
        if not isinstance(payload,typ): violations.append(f"Joint Recovery re-entry {stage} artifact has wrong type")
    if isinstance(pi0,PiConstructionAssessment) and pi0.policy_space is None: violations.append("Joint Recovery re-entry requires reusable pre-binding Pi policy_space")
    if isinstance(completeness,PiCompletenessAssessment) and not completeness.complete: violations.append("Joint Recovery re-entry requires reusable Pi completeness pass")
    if violations:
        return GovernanceReentryExecutionResult(False,"Joint Recovery Feasibility","joint_recovery_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))

    perceived=runtime.world.perceive(state)
    joint=runtime._evaluate_active_joint_recovery_feasibility(state,request)
    pi,binding=runtime._bind_current_period_joint_recovery_actions(pi0,joint)
    if joint.status=="active_capacity_authority_required" or (joint.runtime_verified and joint.jointly_feasible is False):
        decision=CanonicalDecisionCycleAssessment(joint.status,"Joint Recovery Feasibility",("Joint Recovery Feasibility",),governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,joint_recovery_feasibility=joint,joint_recovery_execution_binding=binding,pi_before_joint_recovery_binding=pi0,notes=("v0.90 bounded Joint Recovery re-entry stopped before downstream governance",))
        return GovernanceReentryExecutionResult(True,"Joint Recovery Feasibility","reentry_pass_stopped",decision,tuple(plan.reusable_upstream_stages),("Joint Recovery Feasibility",),(),("joint-recovery gate stopped the bounded pass",))

    constraints=runtime._constraint_system_from_perceived(perceived,pi.policy_space.candidates,regime=regime.regime,governing_domain_ids=g.governing_domain_ids)
    if not constraints.feasible_policy_ids:
        selection=_terminal_sigma_partial_selection(runtime,pi,completeness,constraints)
        stages=("Joint Recovery Feasibility","Constraints","Sigma")
        decision=CanonicalDecisionCycleAssessment(selection.status,"Sigma",stages,governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,selection=selection,joint_recovery_feasibility=joint,joint_recovery_execution_binding=binding,pi_before_joint_recovery_binding=pi0,notes=("v0.120 canonical terminal Sigma continuation; Domain Framing, Adequacy, and Q were not invoked","epsilon was intentionally not invoked"))
        return GovernanceReentryExecutionResult(True,"Joint Recovery Feasibility","reentry_pass_completed",decision,tuple(plan.reusable_upstream_stages),stages,(),("terminal Sigma completed the bounded re-entry pass","epsilon was not executed"))
    framing=runtime._validate_domain_framing_against_governing(request.domain_frame,g.governing_domain_ids)
    if not framing.valid:
        decision=CanonicalDecisionCycleAssessment(framing.status,"Domain Framing",("Joint Recovery Feasibility","Constraints","Domain Framing"),governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing,joint_recovery_feasibility=joint,joint_recovery_execution_binding=binding,pi_before_joint_recovery_binding=pi0)
        return GovernanceReentryExecutionResult(True,"Joint Recovery Feasibility","reentry_pass_stopped",decision,tuple(plan.reusable_upstream_stages),("Joint Recovery Feasibility","Constraints","Domain Framing"),(),("Domain Framing stopped the bounded pass",))

    pma=runtime.validate_projection_model_authority(request.projection_model_authority,request.projection_horizon)
    if runtime.projection_service is not None and not pma.valid:
        return GovernanceReentryExecutionResult(False,"Joint Recovery Feasibility","joint_recovery_reentry_projection_authority_failed",reused_stage_ids=tuple(plan.reusable_upstream_stages),recomputed_stage_ids=("Joint Recovery Feasibility","Constraints","Domain Framing"),violations=tuple(pma.violations))
    records={}
    feasible=set(constraints.feasible_policy_ids)
    for candidate in pi.policy_space.candidates:
        if candidate.id not in feasible: continue
        rec=runtime._project_policy_record(perceived,candidate,candidate_mode="ordinary_adequacy",projection_horizon=request.projection_horizon,graph_assessment=graph,projection_input_trace=request.projection_input_trace,projection_model_authority=request.projection_model_authority,projection_model_authority_assessment=pma)
        if rec is None: raise ValueError("Joint Recovery re-entry requires authoritative Q_t(pi)")
        records[candidate.id]=rec
    adequacy=runtime.evaluate_restoration_adequacy(request.domain_frame,g.governing_domain_ids,tuple(records.values()))
    if not adequacy.adequate_policy_ids:
        selection=_fallback_sigma_partial_selection(runtime,perceived,pi,completeness,framing,constraints,adequacy,records,g.governing_domain_ids)
        stages=("Joint Recovery Feasibility","Constraints","Domain Framing","Adequacy","Sigma")
        decision=CanonicalDecisionCycleAssessment(selection.status,"Sigma",stages,governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing,adequacy=adequacy,selection=selection,projection_records=tuple(records.values()),joint_recovery_feasibility=joint,joint_recovery_execution_binding=binding,pi_before_joint_recovery_binding=pi0,notes=("v0.120 canonical recovery-unavailable fallback Sigma continuation","epsilon was intentionally not invoked"))
        return GovernanceReentryExecutionResult(True,"Joint Recovery Feasibility","reentry_pass_completed",decision,tuple(plan.reusable_upstream_stages),stages,(),("fallback Sigma completed the bounded re-entry pass","epsilon was not executed"))
    selection=runtime._standard_selection_from_cycle_records(pi.policy_space.candidates,completeness,framing,constraints,adequacy,records,g.governing_domain_ids)
    stages=("Joint Recovery Feasibility","Constraints","Domain Framing","Adequacy","Sigma")
    decision=CanonicalDecisionCycleAssessment(selection.status,"Sigma",stages,governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing,adequacy=adequacy,selection=selection,projection_records=tuple(records.values()),joint_recovery_feasibility=joint,joint_recovery_execution_binding=binding,pi_before_joint_recovery_binding=pi0,notes=("v0.90 reused pre-binding Pi and recomputed its executable downstream lineage","epsilon was intentionally not invoked"))
    return GovernanceReentryExecutionResult(True,"Joint Recovery Feasibility","reentry_pass_completed",decision,tuple(plan.reusable_upstream_stages),stages,(),("single bounded re-entry pass completed","epsilon was not executed"))


def execute_constraints_reentry(runtime, plan, bundle, bundle_assessment, state, request):
    """Execute one bounded Constraints -> Framing -> Adequacy -> standard Sigma pass.

    The exact already-bound Pi and its regime/G context are reusable inputs.  This
    entry point does not rerun joint recovery or mutate/rebind Pi.  It recomputes
    Constraints and every ordinary downstream consumer, stopping before epsilon.
    """
    from .models import (
        GovernanceReentryExecutionResult, ConstraintsReusablePiArtifact,
        PiCompletenessAssessment, GraphConstructionAssessment,
        CanonicalDecisionCycleAssessment,
    )
    violations=[]
    if not plan.valid: violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "Constraints": violations.append("Constraints re-entry requires Constraints boundary")
    if not bundle_assessment.valid: violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id: violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages): violations.append("bundle assessment stage coverage does not match re-entry plan")
    artifacts=dict(bundle.stage_artifacts)
    required={"Graph/Seed","Pi","Pi Completeness"}
    missing=tuple(sorted(required-set(artifacts)))
    if missing: violations.append("Constraints re-entry bundle omits required artifacts: "+", ".join(missing))
    if violations:
        return GovernanceReentryExecutionResult(False,"Constraints","invalid_constraints_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    graph=artifacts["Graph/Seed"]; pi_payload=artifacts["Pi"]; completeness=artifacts["Pi Completeness"]
    if not isinstance(graph,GraphConstructionAssessment): violations.append("Constraints re-entry Graph/Seed artifact has wrong type")
    if not isinstance(pi_payload,ConstraintsReusablePiArtifact): violations.append("Constraints re-entry Pi artifact has wrong type")
    if not isinstance(completeness,PiCompletenessAssessment): violations.append("Constraints re-entry Pi Completeness artifact has wrong type")
    if violations:
        return GovernanceReentryExecutionResult(False,"Constraints","constraints_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    pi=pi_payload.pi_construction; regime=pi_payload.regime_assessment; g=pi_payload.governing_assessment
    if pi.policy_space is None: violations.append("Constraints re-entry requires reusable bound Pi policy_space")
    if not completeness.complete: violations.append("Constraints re-entry requires reusable Pi completeness pass")
    if violations:
        return GovernanceReentryExecutionResult(False,"Constraints","constraints_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    perceived=runtime.world.perceive(state)
    constraints=runtime._constraint_system_from_perceived(perceived,pi.policy_space.candidates,regime=regime.regime,governing_domain_ids=g.governing_domain_ids)
    if not constraints.feasible_policy_ids:
        selection=_terminal_sigma_partial_selection(runtime,pi,completeness,constraints)
        stages=("Constraints","Sigma")
        decision=CanonicalDecisionCycleAssessment(selection.status,"Sigma",stages,governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,selection=selection,joint_recovery_feasibility=pi_payload.joint_recovery_artifact,notes=("v0.120 canonical terminal Sigma continuation; Domain Framing, Adequacy, and Q were not invoked","epsilon was intentionally not invoked"))
        return GovernanceReentryExecutionResult(True,"Constraints","reentry_pass_completed",decision,tuple(plan.reusable_upstream_stages),stages,(),("terminal Sigma completed the bounded re-entry pass","epsilon was not executed"))
    framing=runtime._validate_domain_framing_against_governing(request.domain_frame,g.governing_domain_ids)
    if not framing.valid:
        decision=CanonicalDecisionCycleAssessment(framing.status,"Domain Framing",("Constraints","Domain Framing"),governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing,joint_recovery_feasibility=pi_payload.joint_recovery_artifact)
        return GovernanceReentryExecutionResult(True,"Constraints","reentry_pass_stopped",decision,tuple(plan.reusable_upstream_stages),("Constraints","Domain Framing"),(),("Domain Framing stopped the bounded pass",))
    pma=runtime.validate_projection_model_authority(request.projection_model_authority,request.projection_horizon)
    if runtime.projection_service is not None and not pma.valid:
        return GovernanceReentryExecutionResult(False,"Constraints","constraints_reentry_projection_authority_failed",reused_stage_ids=tuple(plan.reusable_upstream_stages),recomputed_stage_ids=("Constraints","Domain Framing"),violations=tuple(pma.violations))
    records={}; feasible=set(constraints.feasible_policy_ids)
    for candidate in pi.policy_space.candidates:
        if candidate.id not in feasible: continue
        rec=runtime._project_policy_record(perceived,candidate,candidate_mode="ordinary_adequacy",projection_horizon=request.projection_horizon,graph_assessment=graph,projection_input_trace=request.projection_input_trace,projection_model_authority=request.projection_model_authority,projection_model_authority_assessment=pma)
        if rec is None: raise ValueError("Constraints re-entry requires authoritative Q_t(pi)")
        records[candidate.id]=rec
    adequacy=runtime.evaluate_restoration_adequacy(request.domain_frame,g.governing_domain_ids,tuple(records.values()))
    if not adequacy.adequate_policy_ids:
        selection=_fallback_sigma_partial_selection(runtime,perceived,pi,completeness,framing,constraints,adequacy,records,g.governing_domain_ids)
        stages=("Constraints","Domain Framing","Adequacy","Sigma")
        decision=CanonicalDecisionCycleAssessment(selection.status,"Sigma",stages,governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing,adequacy=adequacy,selection=selection,projection_records=tuple(records.values()),joint_recovery_feasibility=pi_payload.joint_recovery_artifact,notes=("v0.120 canonical recovery-unavailable fallback Sigma continuation","epsilon was intentionally not invoked"))
        return GovernanceReentryExecutionResult(True,"Constraints","reentry_pass_completed",decision,tuple(plan.reusable_upstream_stages),stages,(),("fallback Sigma completed the bounded re-entry pass","epsilon was not executed"))
    selection=runtime._standard_selection_from_cycle_records(pi.policy_space.candidates,completeness,framing,constraints,adequacy,records,g.governing_domain_ids)
    stages=("Constraints","Domain Framing","Adequacy","Sigma")
    decision=CanonicalDecisionCycleAssessment(selection.status,"Sigma",stages,governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing,adequacy=adequacy,selection=selection,projection_records=tuple(records.values()),joint_recovery_feasibility=pi_payload.joint_recovery_artifact,notes=("v0.91 reused exact bound Pi and recomputed its ordinary downstream lineage","epsilon was intentionally not invoked"))
    return GovernanceReentryExecutionResult(True,"Constraints","reentry_pass_completed",decision,tuple(plan.reusable_upstream_stages),stages,(),("single bounded re-entry pass completed","epsilon was not executed"))


def execute_pi_completeness_reentry(runtime, plan, bundle, bundle_assessment, state, request):
    """Execute one bounded Pi Completeness -> Joint Recovery -> downstream pass.

    Pi Completeness is a validation-only gate: it does not alter Pi.  The exact
    reusable Pi supplied at this boundary is therefore the pre-joint-recovery Pi.
    After completeness passes, the mature joint-recovery binding is recomputed and
    every executable consumer of the resulting bound Pi is recomputed through
    standard Sigma.  The pass stops before epsilon.
    """
    from .models import (
        GovernanceReentryExecutionResult, GoverningAssessment, RegimeAssessment,
        GraphConstructionAssessment, PiConstructionAssessment,
        CanonicalDecisionCycleAssessment,
    )
    violations=[]
    if not plan.valid: violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "Pi Completeness": violations.append("Pi Completeness re-entry requires Pi Completeness boundary")
    if not bundle_assessment.valid: violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id: violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages): violations.append("bundle assessment stage coverage does not match re-entry plan")
    artifacts=dict(bundle.stage_artifacts)
    required={"G","R","Graph/Seed","Pi"}
    missing=tuple(sorted(required-set(artifacts)))
    if missing: violations.append("Pi Completeness re-entry bundle omits required artifacts: "+", ".join(missing))
    if violations:
        return GovernanceReentryExecutionResult(False,"Pi Completeness","invalid_pi_completeness_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    g=artifacts["G"]; regime=artifacts["R"]; graph=artifacts["Graph/Seed"]; pi0=artifacts["Pi"]
    for stage,payload,typ in (("G",g,GoverningAssessment),("R",regime,RegimeAssessment),("Graph/Seed",graph,GraphConstructionAssessment),("Pi",pi0,PiConstructionAssessment)):
        if not isinstance(payload,typ): violations.append(f"Pi Completeness re-entry {stage} artifact has wrong type")
    if isinstance(pi0,PiConstructionAssessment) and pi0.policy_space is None: violations.append("Pi Completeness re-entry requires reusable Pi policy_space")
    if violations:
        return GovernanceReentryExecutionResult(False,"Pi Completeness","pi_completeness_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))

    completeness=runtime.validate_pi_completeness(pi0.policy_space)
    if not completeness.complete:
        decision=CanonicalDecisionCycleAssessment(completeness.status,"Pi Completeness",("Pi Completeness",),governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi0,pi_completeness=completeness,pi_before_joint_recovery_binding=pi0,notes=("v0.92 bounded Pi Completeness re-entry stopped at completeness failure",))
        return GovernanceReentryExecutionResult(True,"Pi Completeness","reentry_pass_stopped",decision,tuple(plan.reusable_upstream_stages),("Pi Completeness",),(),("Pi Completeness blocked downstream governance",))

    joint=runtime._evaluate_active_joint_recovery_feasibility(state,request)
    pi,binding=runtime._bind_current_period_joint_recovery_actions(pi0,joint)
    if joint.status in {"active_capacity_authority_required","joint_recovery_infeasible"}:
        decision=CanonicalDecisionCycleAssessment(joint.status,"Joint Recovery Feasibility",("Pi Completeness","Joint Recovery Feasibility"),governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,joint_recovery_feasibility=joint,joint_recovery_execution_binding=binding,pi_before_joint_recovery_binding=pi0,notes=("v0.92 bounded Pi Completeness re-entry stopped at Joint Recovery Feasibility",))
        return GovernanceReentryExecutionResult(True,"Pi Completeness","reentry_pass_stopped",decision,tuple(plan.reusable_upstream_stages),("Pi Completeness","Joint Recovery Feasibility"),(),("Joint Recovery Feasibility blocked downstream governance",))

    perceived=runtime.world.perceive(state)
    constraints=runtime._constraint_system_from_perceived(perceived,pi.policy_space.candidates,regime=regime.regime,governing_domain_ids=g.governing_domain_ids)
    if not constraints.feasible_policy_ids:
        selection=_terminal_sigma_partial_selection(runtime,pi,completeness,constraints)
        stages=("Pi Completeness","Joint Recovery Feasibility","Constraints","Sigma")
        decision=CanonicalDecisionCycleAssessment(selection.status,"Sigma",stages,governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,selection=selection,joint_recovery_feasibility=joint,joint_recovery_execution_binding=binding,pi_before_joint_recovery_binding=pi0,notes=("v0.120 canonical terminal Sigma continuation; Domain Framing, Adequacy, and Q were not invoked","epsilon was intentionally not invoked"))
        return GovernanceReentryExecutionResult(True,"Pi Completeness","reentry_pass_completed",decision,tuple(plan.reusable_upstream_stages),stages,(),("terminal Sigma completed the bounded re-entry pass","epsilon was not executed"))
    framing=runtime._validate_domain_framing_against_governing(request.domain_frame,g.governing_domain_ids)
    if not framing.valid:
        stages=("Pi Completeness","Joint Recovery Feasibility","Constraints","Domain Framing")
        decision=CanonicalDecisionCycleAssessment(framing.status,"Domain Framing",stages,governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing,joint_recovery_feasibility=joint,joint_recovery_execution_binding=binding,pi_before_joint_recovery_binding=pi0)
        return GovernanceReentryExecutionResult(True,"Pi Completeness","reentry_pass_stopped",decision,tuple(plan.reusable_upstream_stages),stages,(),("Domain Framing stopped the bounded pass",))
    pma=runtime.validate_projection_model_authority(request.projection_model_authority,request.projection_horizon)
    if runtime.projection_service is not None and not pma.valid:
        return GovernanceReentryExecutionResult(False,"Pi Completeness","pi_completeness_reentry_projection_authority_failed",reused_stage_ids=tuple(plan.reusable_upstream_stages),recomputed_stage_ids=("Pi Completeness","Joint Recovery Feasibility","Constraints","Domain Framing"),violations=tuple(pma.violations))
    records={}; feasible=set(constraints.feasible_policy_ids)
    for candidate in pi.policy_space.candidates:
        if candidate.id not in feasible: continue
        rec=runtime._project_policy_record(perceived,candidate,candidate_mode="ordinary_adequacy",projection_horizon=request.projection_horizon,graph_assessment=graph,projection_input_trace=request.projection_input_trace,projection_model_authority=request.projection_model_authority,projection_model_authority_assessment=pma)
        if rec is None: raise ValueError("Pi Completeness re-entry requires authoritative Q_t(pi)")
        records[candidate.id]=rec
    adequacy=runtime.evaluate_restoration_adequacy(request.domain_frame,g.governing_domain_ids,tuple(records.values()))
    if not adequacy.adequate_policy_ids:
        selection=_fallback_sigma_partial_selection(runtime,perceived,pi,completeness,framing,constraints,adequacy,records,g.governing_domain_ids)
        stages=("Pi Completeness","Joint Recovery Feasibility","Constraints","Domain Framing","Adequacy","Sigma")
        decision=CanonicalDecisionCycleAssessment(selection.status,"Sigma",stages,governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing,adequacy=adequacy,selection=selection,projection_records=tuple(records.values()),joint_recovery_feasibility=joint,joint_recovery_execution_binding=binding,pi_before_joint_recovery_binding=pi0,notes=("v0.120 canonical recovery-unavailable fallback Sigma continuation","epsilon was intentionally not invoked"))
        return GovernanceReentryExecutionResult(True,"Pi Completeness","reentry_pass_completed",decision,tuple(plan.reusable_upstream_stages),stages,(),("fallback Sigma completed the bounded re-entry pass","epsilon was not executed"))
    selection=runtime._standard_selection_from_cycle_records(pi.policy_space.candidates,completeness,framing,constraints,adequacy,records,g.governing_domain_ids)
    stages=("Pi Completeness","Joint Recovery Feasibility","Constraints","Domain Framing","Adequacy","Sigma")
    decision=CanonicalDecisionCycleAssessment(selection.status,"Sigma",stages,governing_assessment=g,regime_assessment=regime,graph_assessment=graph,pi_construction=pi,pi_completeness=completeness,constraints=constraints,domain_framing=framing,adequacy=adequacy,selection=selection,projection_records=tuple(records.values()),joint_recovery_feasibility=joint,joint_recovery_execution_binding=binding,pi_before_joint_recovery_binding=pi0,notes=("v0.92 recomputed Pi completeness without altering pre-binding Pi","joint recovery and all executable downstream consumers were recomputed","epsilon was intentionally not invoked"))
    return GovernanceReentryExecutionResult(True,"Pi Completeness","reentry_pass_completed",decision,tuple(plan.reusable_upstream_stages),stages,(),("single bounded re-entry pass completed","epsilon was not executed"))


def execute_pi_reentry(runtime, plan, bundle, bundle_assessment, state, request, pi_inputs):
    """Execute one bounded Pi -> completeness -> executable downstream pass.

    Pi is reconstructed only from the reusable Graph artifact plus an explicit
    reusable Pi input payload.  It does not reacquire G/R or infer materially
    required classes/configuration.  Downstream execution delegates to the
    established v0.92 Pi Completeness entry point and stops before epsilon.
    """
    from .models import (
        GovernanceReentryExecutionResult, GraphConstructionAssessment,
        PiReusableConstructionInputs, GovernanceReentryPlan,
        GovernanceReusableArtifactBundle, GovernanceReusableArtifactBundleAssessment,
    )
    violations=[]
    if not plan.valid: violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "Pi": violations.append("Pi re-entry requires Pi boundary")
    if not bundle_assessment.valid: violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id: violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages): violations.append("bundle assessment stage coverage does not match re-entry plan")
    artifacts=dict(bundle.stage_artifacts)
    if "Graph/Seed" not in artifacts: violations.append("Pi re-entry bundle omits Graph/Seed artifact")
    
    if violations:
        return GovernanceReentryExecutionResult(False,"Pi","invalid_pi_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    graph=artifacts["Graph/Seed"]; inputs=pi_inputs
    if not isinstance(graph,GraphConstructionAssessment): violations.append("Pi re-entry Graph/Seed artifact has wrong type")
    if not isinstance(inputs,PiReusableConstructionInputs): violations.append("Pi re-entry requires explicit reusable Pi construction inputs")
    if isinstance(graph,GraphConstructionAssessment):
        g=artifacts.get("G"); r=artifacts.get("R")
        if g is not None and tuple(graph.governing_domain_ids) != tuple(g.governing_domain_ids): violations.append("Graph governing identity does not match reusable G artifact")
        if r is not None and graph.regime != r.regime: violations.append("Graph regime identity does not match reusable R artifact")
    if isinstance(inputs,PiReusableConstructionInputs):
        if len(inputs.materially_required_policy_class_ids) != len(set(inputs.materially_required_policy_class_ids)): violations.append("Pi materially required policy class identities must be unique")
        if inputs.pi_config is not None and inputs.pi_config.max_candidates <= 0: violations.append("Pi max_candidates must be positive")
        if tuple(inputs.materially_required_policy_class_ids) != tuple(request.materially_required_policy_class_ids): violations.append("reusable Pi material-requirement declaration does not match re-entry request")
        if inputs.pi_config != request.pi_config: violations.append("reusable Pi configuration does not match re-entry request")
    if violations:
        return GovernanceReentryExecutionResult(False,"Pi","pi_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    pi=runtime.construct_pi_from_graph(graph,inputs.materially_required_policy_class_ids,config=inputs.pi_config)
    if pi.policy_space is None:
        from .models import CanonicalDecisionCycleAssessment
        decision=CanonicalDecisionCycleAssessment(pi.status,"Pi",("Pi",),governing_assessment=artifacts.get("G"),regime_assessment=artifacts.get("R"),graph_assessment=graph,pi_construction=pi,notes=("v0.93 bounded Pi re-entry stopped at Pi construction",))
        return GovernanceReentryExecutionResult(True,"Pi","reentry_pass_stopped",decision,tuple(plan.reusable_upstream_stages),("Pi",),(),("Pi construction blocked downstream governance",))
    downstream_stages=("PPP","Phi","H","G","R","Graph/Seed","Pi")
    downstream_plan=GovernanceReentryPlan(True,"Pi Completeness",downstream_stages,("Pi Completeness","Constraints","Domain Framing","Joint Recovery Feasibility","Adequacy","Sigma","epsilon"),tuple(plan.signal_ids),tuple(plan.invalidated_artifact_ids),False,(),("v0.93 internal bounded handoff from freshly recomputed Pi",))
    downstream_artifacts=[]
    for stage in downstream_stages:
        if stage == "Pi": downstream_artifacts.append((stage,pi))
        elif stage in artifacts: downstream_artifacts.append((stage,artifacts[stage]))
        else: downstream_artifacts.append((stage,None))
    db=GovernanceReusableArtifactBundle(bundle.bundle_id+":pi",bundle.cycle_id,bundle.initial_state_id,bundle.configuration_id,tuple(downstream_artifacts),tuple(bundle.provenance_ids),("v0.93 internal Pi-to-completeness handoff",))
    dba=GovernanceReusableArtifactBundleAssessment(True,db.bundle_id,db.cycle_id,db.initial_state_id,db.configuration_id,downstream_stages,(),("fresh Pi accepted as the Pi Completeness reusable boundary",))
    result=execute_pi_completeness_reentry(runtime,downstream_plan,db,dba,state,request)
    if result.decision is not None:
        from dataclasses import replace
        result=replace(result,recompute_from_stage="Pi",recomputed_stage_ids=("Pi",)+tuple(result.recomputed_stage_ids),reused_stage_ids=tuple(plan.reusable_upstream_stages),notes=("v0.93 recomputed Pi from explicit reusable construction inputs",)+tuple(result.notes))
    return result


def execute_graph_reentry(runtime, plan, bundle, bundle_assessment, state, request, graph_inputs, pi_inputs):
    """Execute one bounded Graph/Seed -> Pi -> established downstream pass.

    Graph is reconstructed only after verifying that its explicit declarations and
    the identity of the registered graph substrate match the authorized re-entry
    inputs.  The runtime does not silently adopt a changed registry.
    """
    from .models import (
        GovernanceReentryExecutionResult, GoverningAssessment, RegimeAssessment,
        GraphReusableConstructionInputs, PiReusableConstructionInputs,
        GovernanceReentryPlan, GovernanceReusableArtifactBundle,
        GovernanceReusableArtifactBundleAssessment, CanonicalDecisionCycleAssessment,
    )
    violations=[]
    if not plan.valid: violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "Graph/Seed": violations.append("Graph/Seed re-entry requires Graph/Seed boundary")
    if not bundle_assessment.valid: violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id: violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages): violations.append("bundle assessment stage coverage does not match re-entry plan")
    artifacts=dict(bundle.stage_artifacts)
    if "G" not in artifacts or "R" not in artifacts: violations.append("Graph/Seed re-entry requires reusable G and R artifacts")
    if not isinstance(graph_inputs,GraphReusableConstructionInputs): violations.append("Graph/Seed re-entry requires explicit reusable Graph construction inputs")
    if not isinstance(pi_inputs,PiReusableConstructionInputs): violations.append("Graph/Seed re-entry requires explicit reusable Pi construction inputs")
    if violations:
        return GovernanceReentryExecutionResult(False,"Graph/Seed","invalid_graph_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    g=artifacts["G"]; regime=artifacts["R"]
    if not isinstance(g,GoverningAssessment): violations.append("Graph/Seed re-entry G artifact has wrong type")
    if not isinstance(regime,RegimeAssessment): violations.append("Graph/Seed re-entry R artifact has wrong type")
    gi=graph_inputs
    if gi.preservation_object != request.preservation_object: violations.append("reusable Graph preservation object does not match re-entry request")
    if tuple(gi.required_graph_family_ids) != tuple(request.required_graph_family_ids): violations.append("reusable Graph required-family declaration does not match re-entry request")
    if tuple(gi.required_graph_path_class_ids) != tuple(request.required_graph_path_class_ids): violations.append("reusable Graph required-path declaration does not match re-entry request")
    if gi.graph_config != request.graph_config: violations.append("reusable Graph configuration does not match re-entry request")
    if not gi.graph_substrate_identity.strip(): violations.append("reusable Graph substrate identity must be explicit")
    elif gi.graph_substrate_identity != runtime.registry.graph_substrate_identity(): violations.append("registered Graph substrate identity changed since reusable inputs were authorized")
    if violations:
        return GovernanceReentryExecutionResult(False,"Graph/Seed","graph_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    graph=runtime.construct_graph(gi.preservation_object,regime.regime,g.governing_domain_ids,gi.required_graph_family_ids,gi.required_graph_path_class_ids,config=gi.graph_config)
    if graph.status not in {"PASS","CONDITIONAL PASS"}:
        decision=CanonicalDecisionCycleAssessment(graph.status,"Graph/Seed",("Graph/Seed",),governing_assessment=g,regime_assessment=regime,graph_assessment=graph,notes=("v0.94 bounded Graph/Seed re-entry stopped at Graph validity",))
        return GovernanceReentryExecutionResult(True,"Graph/Seed","reentry_pass_stopped",decision,tuple(plan.reusable_upstream_stages),("Graph/Seed",),(),("Graph validity blocked downstream governance",))
    downstream_stages=("PPP","Phi","H","G","R","Graph/Seed")
    downstream_plan=GovernanceReentryPlan(True,"Pi",downstream_stages,("Pi","Pi Completeness","Constraints","Domain Framing","Joint Recovery Feasibility","Adequacy","Sigma","epsilon"),tuple(plan.signal_ids),tuple(plan.invalidated_artifact_ids),False,(),("v0.94 internal bounded handoff from freshly recomputed Graph",))
    downstream_artifacts=[]
    for stage in downstream_stages:
        if stage == "Graph/Seed": downstream_artifacts.append((stage,graph))
        elif stage in artifacts: downstream_artifacts.append((stage,artifacts[stage]))
        else: downstream_artifacts.append((stage,None))
    db=GovernanceReusableArtifactBundle(bundle.bundle_id+":graph",bundle.cycle_id,bundle.initial_state_id,bundle.configuration_id,tuple(downstream_artifacts),tuple(bundle.provenance_ids),("v0.94 internal Graph-to-Pi handoff",))
    dba=GovernanceReusableArtifactBundleAssessment(True,db.bundle_id,db.cycle_id,db.initial_state_id,db.configuration_id,downstream_stages,(),("fresh Graph accepted as the Pi reusable boundary",))
    result=execute_pi_reentry(runtime,downstream_plan,db,dba,state,request,pi_inputs)
    from dataclasses import replace
    if result.decision is not None:
        result=replace(result,recompute_from_stage="Graph/Seed",recomputed_stage_ids=("Graph/Seed",)+tuple(result.recomputed_stage_ids),reused_stage_ids=tuple(plan.reusable_upstream_stages),notes=("v0.94 recomputed Graph from identity-bound registered substrate",)+tuple(result.notes))
    return result


def execute_regime_reentry(runtime, plan, bundle, bundle_assessment, state, request, regime_inputs, graph_inputs, pi_inputs):
    """Execute one bounded R -> Graph -> established downstream pass without reacquiring world state for R."""
    from .models import (
        GovernanceReentryExecutionResult, PressureFieldAssessment, HorizonAssessment, GoverningAssessment,
        RegimeReusableClassificationInputs, GraphReusableConstructionInputs, PiReusableConstructionInputs,
        DomainAssessment, GovernanceReentryPlan, GovernanceReusableArtifactBundle,
        GovernanceReusableArtifactBundleAssessment,
    )
    violations=[]
    if not plan.valid: violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "R": violations.append("R re-entry requires R boundary")
    if not bundle_assessment.valid: violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id: violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages): violations.append("bundle assessment stage coverage does not match re-entry plan")
    artifacts=dict(bundle.stage_artifacts)
    phi=artifacts.get("Phi"); horizon=artifacts.get("H"); g=artifacts.get("G")
    if not isinstance(phi,PressureFieldAssessment): violations.append("R re-entry Phi artifact has wrong type")
    if not isinstance(horizon,HorizonAssessment): violations.append("R re-entry H artifact has wrong type")
    if not isinstance(g,GoverningAssessment): violations.append("R re-entry G artifact has wrong type")
    if not isinstance(regime_inputs,RegimeReusableClassificationInputs): violations.append("R re-entry requires explicit reusable regime classification inputs")
    if not isinstance(graph_inputs,GraphReusableConstructionInputs): violations.append("R re-entry requires explicit reusable Graph construction inputs")
    if not isinstance(pi_inputs,PiReusableConstructionInputs): violations.append("R re-entry requires explicit reusable Pi construction inputs")
    if violations:
        return GovernanceReentryExecutionResult(False,"R","invalid_regime_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    ri=regime_inputs
    if not ri.regime_configuration_identity.strip(): violations.append("reusable R configuration identity must be explicit")
    elif ri.regime_configuration_identity != runtime.registry.regime_configuration_identity(): violations.append("registered R configuration identity changed since reusable inputs were authorized")
    if bool(ri.contextual_interruption) != bool(request.contextual_interruption): violations.append("reusable R contextual-interruption input does not match re-entry request")
    if ri.previous_regime != request.previous_regime: violations.append("reusable R previous-regime input does not match re-entry request")
    ds={x.domain_id:x for x in ri.domain_assessments}
    if len(ds)!=len(ri.domain_assessments): violations.append("reusable R domain assessments contain duplicate domain identity")
    if set(ds)!=set(runtime.registry.domains): violations.append("reusable R domain-assessment coverage does not match registered domains")
    pmap={x.domain_id:x.pressure for x in phi.domain_results}; hmap=horizon.horizons; gov=set(g.governing_domain_ids)
    for did,x in ds.items():
        if did not in pmap or did not in hmap: violations.append(f"reusable R domain {did} is absent from Phi/H"); continue
        if float(x.pressure)!=float(pmap[did]): violations.append(f"reusable R pressure for {did} does not match Phi")
        if float(x.horizon)!=float(hmap[did]): violations.append(f"reusable R horizon for {did} does not match H")
        if bool(x.governing)!=(did in gov): violations.append(f"reusable R governing flag for {did} does not match G")
    if violations:
        return GovernanceReentryExecutionResult(False,"R","regime_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    regime=runtime.classify_regime(ds,hmap,g.governing_domain_ids,contextual_interruption=ri.contextual_interruption,previous=ri.previous_regime)
    downstream_stages=("PPP","Phi","H","G","R")
    downstream_plan=GovernanceReentryPlan(True,"Graph/Seed",downstream_stages,("Graph/Seed","Pi","Pi Completeness","Constraints","Domain Framing","Joint Recovery Feasibility","Adequacy","Sigma","epsilon"),tuple(plan.signal_ids),tuple(plan.invalidated_artifact_ids),False,(),("v0.95 internal bounded handoff from freshly recomputed R",))
    downstream_artifacts=[]
    for stage in downstream_stages:
        if stage=="R": downstream_artifacts.append((stage,regime))
        elif stage in artifacts: downstream_artifacts.append((stage,artifacts[stage]))
        else: downstream_artifacts.append((stage,None))
    db=GovernanceReusableArtifactBundle(bundle.bundle_id+":regime",bundle.cycle_id,bundle.initial_state_id,bundle.configuration_id,tuple(downstream_artifacts),tuple(bundle.provenance_ids),("v0.95 internal R-to-Graph handoff",))
    dba=GovernanceReusableArtifactBundleAssessment(True,db.bundle_id,db.cycle_id,db.initial_state_id,db.configuration_id,downstream_stages,(),("fresh R accepted as Graph reusable boundary",))
    result=execute_graph_reentry(runtime,downstream_plan,db,dba,state,request,graph_inputs,pi_inputs)
    from dataclasses import replace
    if result.decision is not None:
        result=replace(result,recompute_from_stage="R",recomputed_stage_ids=("R",)+tuple(result.recomputed_stage_ids),reused_stage_ids=tuple(plan.reusable_upstream_stages),notes=("v0.95 recomputed R solely from reusable Phi/H/G-consistent domain assessments and identity-bound R configuration",)+tuple(result.notes))
    return result


def execute_governing_reentry(runtime, plan, bundle, bundle_assessment, state, request, governing_inputs, regime_inputs, graph_inputs, pi_inputs):
    """Execute one bounded G -> R -> established downstream pass without reacquiring world state for G."""
    from dataclasses import replace
    from .models import (
        GovernanceReentryExecutionResult, PressureFieldAssessment, HorizonAssessment,
        GoverningReusableIdentificationInputs, RegimeReusableClassificationInputs,
        GraphReusableConstructionInputs, PiReusableConstructionInputs, DomainAssessment,
        GovernanceReentryPlan, GovernanceReusableArtifactBundle,
        GovernanceReusableArtifactBundleAssessment,
    )
    violations=[]
    if not plan.valid: violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "G": violations.append("G re-entry requires G boundary")
    if not bundle_assessment.valid: violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id: violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages): violations.append("bundle assessment stage coverage does not match re-entry plan")
    artifacts=dict(bundle.stage_artifacts)
    phi=artifacts.get("Phi"); horizon=artifacts.get("H")
    if not isinstance(phi,PressureFieldAssessment): violations.append("G re-entry Phi artifact has wrong type")
    if not isinstance(horizon,HorizonAssessment): violations.append("G re-entry H artifact has wrong type")
    if not isinstance(governing_inputs,GoverningReusableIdentificationInputs): violations.append("G re-entry requires explicit reusable governing inputs")
    if not isinstance(regime_inputs,RegimeReusableClassificationInputs): violations.append("G re-entry requires explicit reusable regime inputs")
    if not isinstance(graph_inputs,GraphReusableConstructionInputs): violations.append("G re-entry requires explicit reusable Graph inputs")
    if not isinstance(pi_inputs,PiReusableConstructionInputs): violations.append("G re-entry requires explicit reusable Pi inputs")
    if violations:
        return GovernanceReentryExecutionResult(False,"G","invalid_governing_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    if not governing_inputs.governing_substrate_identity.strip(): violations.append("reusable G substrate identity must be explicit")
    elif governing_inputs.governing_substrate_identity != runtime.registry.governing_substrate_identity(): violations.append("registered G substrate identity changed since reusable inputs were authorized")
    if set(horizon.horizons) != set(runtime.registry.domains): violations.append("reusable H domain coverage does not match registered G domain substrate")
    if violations:
        return GovernanceReentryExecutionResult(False,"G","governing_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    g=runtime.identify_governing_domains(horizon.horizons)
    # R-relevant governing flags are downstream of fresh G. Preserve captured value/pressure/horizon/threshold,
    # but replace only the invalidated governing-membership field before R validates against Phi/H/G.
    gov=set(g.governing_domain_ids)
    refreshed_ds=tuple(DomainAssessment(x.domain_id,x.perceived_value,x.pressure,x.horizon,x.domain_id in gov,x.threshold) for x in regime_inputs.domain_assessments)
    refreshed_ri=RegimeReusableClassificationInputs(refreshed_ds,regime_inputs.contextual_interruption,regime_inputs.previous_regime,regime_inputs.regime_configuration_identity,regime_inputs.notes+("v0.96 governing membership refreshed from newly recomputed G",))
    downstream_stages=("PPP","Phi","H","G")
    downstream_plan=GovernanceReentryPlan(True,"R",downstream_stages,("R","Graph/Seed","Pi","Pi Completeness","Constraints","Domain Framing","Joint Recovery Feasibility","Adequacy","Sigma","epsilon"),tuple(plan.signal_ids),tuple(plan.invalidated_artifact_ids),False,(),("v0.96 internal bounded handoff from freshly recomputed G",))
    downstream_artifacts=[]
    for stage in downstream_stages:
        if stage=="G": downstream_artifacts.append((stage,g))
        elif stage in artifacts: downstream_artifacts.append((stage,artifacts[stage]))
        else: downstream_artifacts.append((stage,None))
    db=GovernanceReusableArtifactBundle(bundle.bundle_id+":governing",bundle.cycle_id,bundle.initial_state_id,bundle.configuration_id,tuple(downstream_artifacts),tuple(bundle.provenance_ids),("v0.96 internal G-to-R handoff",))
    dba=GovernanceReusableArtifactBundleAssessment(True,db.bundle_id,db.cycle_id,db.initial_state_id,db.configuration_id,downstream_stages,(),("fresh G accepted as R reusable boundary",))
    result=execute_regime_reentry(runtime,downstream_plan,db,dba,state,request,refreshed_ri,graph_inputs,pi_inputs)
    if result.decision is not None:
        result=replace(result,recompute_from_stage="G",recomputed_stage_ids=("G",)+tuple(result.recomputed_stage_ids),reused_stage_ids=tuple(plan.reusable_upstream_stages),notes=("v0.96 recomputed G solely from reusable H and identity-bound G structural substrate",)+tuple(result.notes))
    return result


def execute_horizon_reentry(runtime, plan, bundle, bundle_assessment, state, request, horizon_inputs, governing_inputs, regime_inputs, graph_inputs, pi_inputs):
    """Execute one bounded H -> G -> established downstream pass without a new perception/project step."""
    from dataclasses import replace
    from .models import (
        GovernanceReentryExecutionResult, PressureFieldAssessment, HorizonAssessment,
        HorizonDomainResult, HorizonReusableEvaluationInputs, GoverningReusableIdentificationInputs,
        RegimeReusableClassificationInputs, GraphReusableConstructionInputs, PiReusableConstructionInputs,
        DomainAssessment, GovernanceReentryPlan, GovernanceReusableArtifactBundle,
        GovernanceReusableArtifactBundleAssessment, HorizonConfiguration,
    )
    violations=[]
    if not plan.valid: violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "H": violations.append("H re-entry requires H boundary")
    if not bundle_assessment.valid: violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id: violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages): violations.append("bundle assessment stage coverage does not match re-entry plan")
    artifacts=dict(bundle.stage_artifacts); phi=artifacts.get("Phi")
    if not isinstance(phi,PressureFieldAssessment): violations.append("H re-entry Phi artifact has wrong type")
    if not isinstance(horizon_inputs,HorizonReusableEvaluationInputs): violations.append("H re-entry requires explicit reusable H inputs")
    if not isinstance(governing_inputs,GoverningReusableIdentificationInputs): violations.append("H re-entry requires explicit reusable governing inputs")
    if not isinstance(regime_inputs,RegimeReusableClassificationInputs): violations.append("H re-entry requires explicit reusable regime inputs")
    if not isinstance(graph_inputs,GraphReusableConstructionInputs): violations.append("H re-entry requires explicit reusable Graph inputs")
    if not isinstance(pi_inputs,PiReusableConstructionInputs): violations.append("H re-entry requires explicit reusable Pi inputs")
    if violations: return GovernanceReentryExecutionResult(False,"H","invalid_horizon_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    if horizon_inputs.horizon_configuration_identity != runtime.registry.horizon_configuration_identity(): violations.append("registered H configuration identity changed since reusable inputs were authorized")
    pby={x.domain_id:x for x in phi.domain_results}
    if set(pby) != set(runtime.registry.domains): violations.append("reusable Phi domain coverage does not match registered H domain substrate")
    if violations: return GovernanceReentryExecutionResult(False,"H","horizon_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    cfg=runtime.registry.horizon_configuration or HorizonConfiguration()
    results=[]
    for did,d in runtime.registry.domains.items():
        pr=pby[did]; margin=float(pr.factors.margin); drift=float(pr.factors.local_trajectory)
        expected=float(runtime.world.expected_deterioration(horizon_inputs.perceived_state,did,drift,pr.pressure,pr.factors))
        import math
        if math.isnan(expected): return GovernanceReentryExecutionResult(False,"H","horizon_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=(f"H expected deterioration for {did} may not be NaN",))
        horizon=0.0 if margin <= 0 else margin/max(cfg.epsilon_deterioration,-expected)
        results.append(HorizonDomainResult(did,margin,expected,float(horizon)))
    h=HorizonAssessment(tuple(results),("v0.97 H re-entry uses captured perceived/baseline causal boundary and fresh expected-deterioration evaluation; no new perception/project/domain-value read",))
    # Refresh downstream R horizon fields from fresh H while retaining captured Phi pressure/value evidence.
    hmap=h.horizons
    refreshed_ds=tuple(DomainAssessment(x.domain_id,x.perceived_value,x.pressure,hmap[x.domain_id],x.governing,x.threshold) for x in regime_inputs.domain_assessments)
    refreshed_ri=RegimeReusableClassificationInputs(refreshed_ds,regime_inputs.contextual_interruption,regime_inputs.previous_regime,regime_inputs.regime_configuration_identity,regime_inputs.notes+("v0.97 horizon refreshed from newly recomputed H",))
    downstream_stages=("PPP","Phi","H")
    downstream_plan=GovernanceReentryPlan(True,"G",downstream_stages,("G","R","Graph/Seed","Pi","Pi Completeness","Constraints","Domain Framing","Joint Recovery Feasibility","Adequacy","Sigma","epsilon"),tuple(plan.signal_ids),tuple(plan.invalidated_artifact_ids),False,(),("v0.97 internal bounded handoff from freshly recomputed H",))
    da=[]
    for stage in downstream_stages: da.append((stage,h if stage=="H" else artifacts.get(stage)))
    db=GovernanceReusableArtifactBundle(bundle.bundle_id+":horizon",bundle.cycle_id,bundle.initial_state_id,bundle.configuration_id,tuple(da),tuple(bundle.provenance_ids),("v0.97 internal H-to-G handoff",))
    dba=GovernanceReusableArtifactBundleAssessment(True,db.bundle_id,db.cycle_id,db.initial_state_id,db.configuration_id,downstream_stages,(),("fresh H accepted as G reusable boundary",))
    result=execute_governing_reentry(runtime,downstream_plan,db,dba,state,request,governing_inputs,refreshed_ri,graph_inputs,pi_inputs)
    if result.decision is not None:
        result=replace(result,recompute_from_stage="H",recomputed_stage_ids=("H",)+tuple(result.recomputed_stage_ids),reused_stage_ids=tuple(plan.reusable_upstream_stages),notes=("v0.97 recomputed H from reusable Phi plus captured causal-state evidence without a new perception step",)+tuple(result.notes))
    return result


def execute_phi_reentry(runtime, plan, bundle, bundle_assessment, state, request, phi_inputs, horizon_inputs, governing_inputs, regime_inputs, graph_inputs, pi_inputs):
    """Execute one bounded Phi -> H -> established downstream pass without new perception/baseline construction."""
    from dataclasses import replace
    from .models import (
        GovernanceReentryExecutionResult, PhiReusableEvaluationInputs,
        HorizonReusableEvaluationInputs, GoverningReusableIdentificationInputs,
        RegimeReusableClassificationInputs, GraphReusableConstructionInputs,
        PiReusableConstructionInputs, GovernanceReentryPlan,
        GovernanceReusableArtifactBundle, GovernanceReusableArtifactBundleAssessment,
    )
    violations=[]
    if not plan.valid: violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "Phi": violations.append("Phi re-entry requires Phi boundary")
    if not bundle_assessment.valid: violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id: violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages): violations.append("bundle assessment stage coverage does not match re-entry plan")
    if not isinstance(phi_inputs,PhiReusableEvaluationInputs): violations.append("Phi re-entry requires explicit reusable Phi inputs")
    if not isinstance(horizon_inputs,HorizonReusableEvaluationInputs): violations.append("Phi re-entry requires explicit reusable H inputs")
    if not isinstance(governing_inputs,GoverningReusableIdentificationInputs): violations.append("Phi re-entry requires explicit reusable governing inputs")
    if not isinstance(regime_inputs,RegimeReusableClassificationInputs): violations.append("Phi re-entry requires explicit reusable regime inputs")
    if not isinstance(graph_inputs,GraphReusableConstructionInputs): violations.append("Phi re-entry requires explicit reusable Graph inputs")
    if not isinstance(pi_inputs,PiReusableConstructionInputs): violations.append("Phi re-entry requires explicit reusable Pi inputs")
    if violations: return GovernanceReentryExecutionResult(False,"Phi","invalid_phi_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    if phi_inputs.phi_substrate_identity != runtime.registry.phi_substrate_identity(): violations.append("registered Phi domain substrate identity changed since reusable inputs were authorized")
    if phi_inputs.perceived_state != horizon_inputs.perceived_state: violations.append("Phi and H reusable perceived-state payloads do not match")
    if phi_inputs.baseline_state != horizon_inputs.baseline_state: violations.append("Phi and H reusable baseline-state payloads do not match")
    if violations: return GovernanceReentryExecutionResult(False,"Phi","phi_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    try:
        phi=runtime._evaluate_phi_from_perceived(phi_inputs.perceived_state,phi_inputs.baseline_state)
    except Exception as exc:
        return GovernanceReentryExecutionResult(False,"Phi","phi_reentry_not_executable",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=(f"Phi evaluation failed: {exc}",))
    downstream_stages=("PPP","Phi")
    downstream_plan=GovernanceReentryPlan(True,"H",downstream_stages,("H","G","R","Graph/Seed","Pi","Pi Completeness","Constraints","Domain Framing","Joint Recovery Feasibility","Adequacy","Sigma","epsilon"),tuple(plan.signal_ids),tuple(plan.invalidated_artifact_ids),False,(),("v0.98 internal bounded handoff from freshly recomputed Phi",))
    artifacts=dict(bundle.stage_artifacts)
    db=GovernanceReusableArtifactBundle(bundle.bundle_id+":phi",bundle.cycle_id,bundle.initial_state_id,bundle.configuration_id,(("PPP",artifacts.get("PPP")),("Phi",phi)),tuple(bundle.provenance_ids),("v0.98 internal Phi-to-H handoff",))
    dba=GovernanceReusableArtifactBundleAssessment(True,db.bundle_id,db.cycle_id,db.initial_state_id,db.configuration_id,downstream_stages,(),("fresh Phi accepted as H reusable boundary",))
    result=execute_horizon_reentry(runtime,downstream_plan,db,dba,state,request,horizon_inputs,governing_inputs,regime_inputs,graph_inputs,pi_inputs)
    if result.decision is not None:
        result=replace(result,recompute_from_stage="Phi",recomputed_stage_ids=("Phi",)+tuple(result.recomputed_stage_ids),reused_stage_ids=tuple(plan.reusable_upstream_stages),notes=("v0.98 recomputed Phi from captured perceived/baseline state without a new perception or baseline-construction step",)+tuple(result.notes))
    return result


def execute_ppp_reentry(runtime, plan, bundle, bundle_assessment, request, ppp_inputs,
                        horizon_inputs, governing_inputs, regime_inputs, graph_inputs, pi_inputs):
    """Execute one bounded PPP/P_i(t) -> Phi -> established downstream pass.

    A PPP invalidation means perception itself is stale.  This entry point therefore
    starts from the authoritative ActualPersistentStateEnvelope and calls the host
    perception boundary again.  It never treats the old represented state as a fresh
    perception.  v0.99 supports the ordinary actual-state perception path only;
    memory-conditioned retrieval/perception requires its own explicit re-entry path.
    """
    from dataclasses import replace
    from .models import (
        GovernanceReentryExecutionResult, PPPReentryInputs,
        HorizonReusableEvaluationInputs, GoverningReusableIdentificationInputs,
        RegimeReusableClassificationInputs, GraphReusableConstructionInputs,
        PiReusableConstructionInputs, GovernanceReentryPlan,
        GovernanceReusableArtifactBundle, GovernanceReusableArtifactBundleAssessment,
        PhiReusableEvaluationInputs,
    )
    violations=[]
    if not plan.valid: violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "PPP": violations.append("PPP re-entry requires PPP boundary")
    if plan.reusable_upstream_stages: violations.append("PPP re-entry may not claim reusable canonical upstream stages")
    if not bundle_assessment.valid: violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id: violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages): violations.append("bundle assessment stage coverage does not match re-entry plan")
    if not isinstance(ppp_inputs,PPPReentryInputs): violations.append("PPP re-entry requires explicit actual-state input")
    if not isinstance(horizon_inputs,HorizonReusableEvaluationInputs): violations.append("PPP re-entry requires explicit reusable H configuration input")
    if not isinstance(governing_inputs,GoverningReusableIdentificationInputs): violations.append("PPP re-entry requires explicit reusable governing input")
    if not isinstance(regime_inputs,RegimeReusableClassificationInputs): violations.append("PPP re-entry requires explicit reusable regime input")
    if not isinstance(graph_inputs,GraphReusableConstructionInputs): violations.append("PPP re-entry requires explicit reusable Graph input")
    if not isinstance(pi_inputs,PiReusableConstructionInputs): violations.append("PPP re-entry requires explicit reusable Pi input")
    if violations:
        return GovernanceReentryExecutionResult(False,"PPP","invalid_ppp_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    actual=ppp_inputs.actual_state
    if actual.state_id != bundle.initial_state_id:
        return GovernanceReentryExecutionResult(False,"PPP","ppp_reentry_not_executable",violations=("actual-state identity does not match re-entry bundle initial state",))
    try:
        snapshot=runtime.prepare_canonical_cycle_snapshot(actual)
        perceived=snapshot.perceived_decision_state
        if perceived is None:
            raise ValueError("fresh perception boundary did not return typed PerceivedDecisionState")
        baseline=runtime._baseline_continuation(snapshot.represented_state)
    except Exception as exc:
        return GovernanceReentryExecutionResult(False,"PPP","ppp_reentry_not_executable",violations=(f"fresh perception/baseline construction failed: {exc}",))
    # Downstream H is allowed to re-run its invalidated causal mapping, but its
    # captured state boundary must now be refreshed to the newly perceived state.
    fresh_hi=replace(horizon_inputs,perceived_state=snapshot.represented_state,baseline_state=baseline)
    fresh_fi=PhiReusableEvaluationInputs(snapshot.represented_state,baseline,runtime.registry.phi_substrate_identity(),("v0.99 state boundary refreshed by fresh PPP perception",))
    downstream_plan=GovernanceReentryPlan(True,"Phi",("PPP",),("Phi","H","G","R","Graph/Seed","Pi","Pi Completeness","Constraints","Domain Framing","Joint Recovery Feasibility","Adequacy","Sigma","epsilon"),tuple(plan.signal_ids),tuple(plan.invalidated_artifact_ids),False,(),("v0.99 internal bounded handoff from fresh PPP",))
    db=GovernanceReusableArtifactBundle(bundle.bundle_id+":ppp",bundle.cycle_id,bundle.initial_state_id,bundle.configuration_id,(("PPP",perceived),),tuple(bundle.provenance_ids),("v0.99 fresh host-supplied P_i(t) accepted as Phi upstream boundary",))
    dba=GovernanceReusableArtifactBundleAssessment(True,db.bundle_id,db.cycle_id,db.initial_state_id,db.configuration_id,("PPP",),(),("fresh PPP accepted as Phi reusable boundary",))
    result=execute_phi_reentry(runtime,downstream_plan,db,dba,snapshot.represented_state,request,fresh_fi,fresh_hi,governing_inputs,regime_inputs,graph_inputs,pi_inputs)
    if result.decision is not None:
        result=replace(result,recompute_from_stage="PPP",recomputed_stage_ids=("PPP",)+tuple(result.recomputed_stage_ids),reused_stage_ids=(),notes=("v0.99 reacquired P_i(t) from authoritative actual state through the host perception boundary; old represented state was not reused",)+tuple(result.notes))
    return result


def execute_memory_conditioned_ppp_reentry(runtime, plan, bundle, bundle_assessment, request, perception_inputs,
                                             horizon_inputs, governing_inputs, regime_inputs, graph_inputs, pi_inputs):
    """Execute one bounded memory-conditioned PPP/P_i(t) -> standard Sigma pass.

    This is deliberately separate from ordinary PPP re-entry.  Retained memory
    M_i(t) is never passed to the perception adapter: the established licensed
    retrieval boundary reconstructs R^M_i(t,q), validates it, and only then calls
    the memory-conditioned host perception mapping with retrieval + optional K_i(t).
    """
    from dataclasses import replace
    from .models import (
        GovernanceReentryExecutionResult, MemoryConditionedPPPReentryInputs,
        HorizonReusableEvaluationInputs, GoverningReusableIdentificationInputs,
        RegimeReusableClassificationInputs, GraphReusableConstructionInputs,
        PiReusableConstructionInputs, GovernanceReentryPlan,
        GovernanceReusableArtifactBundle, GovernanceReusableArtifactBundleAssessment,
        PhiReusableEvaluationInputs,
    )
    violations=[]
    if not plan.valid: violations.append("re-entry plan must be valid")
    if plan.recompute_from_stage != "PPP": violations.append("memory-conditioned PPP re-entry requires PPP boundary")
    if plan.reusable_upstream_stages: violations.append("memory-conditioned PPP re-entry may not claim reusable canonical upstream stages")
    if not bundle_assessment.valid: violations.append("reusable-artifact bundle assessment must be valid")
    if bundle_assessment.bundle_id != bundle.bundle_id: violations.append("bundle assessment identity does not match supplied bundle")
    if tuple(bundle_assessment.reusable_stage_ids) != tuple(plan.reusable_upstream_stages): violations.append("bundle assessment stage coverage does not match re-entry plan")
    if not isinstance(perception_inputs,MemoryConditionedPPPReentryInputs): violations.append("memory-conditioned PPP re-entry requires explicit licensed perception inputs")
    if not isinstance(horizon_inputs,HorizonReusableEvaluationInputs): violations.append("memory-conditioned PPP re-entry requires explicit reusable H configuration input")
    if not isinstance(governing_inputs,GoverningReusableIdentificationInputs): violations.append("memory-conditioned PPP re-entry requires explicit reusable governing input")
    if not isinstance(regime_inputs,RegimeReusableClassificationInputs): violations.append("memory-conditioned PPP re-entry requires explicit reusable regime input")
    if not isinstance(graph_inputs,GraphReusableConstructionInputs): violations.append("memory-conditioned PPP re-entry requires explicit reusable Graph input")
    if not isinstance(pi_inputs,PiReusableConstructionInputs): violations.append("memory-conditioned PPP re-entry requires explicit reusable Pi input")
    if violations:
        return GovernanceReentryExecutionResult(False,"PPP","invalid_memory_conditioned_ppp_reentry",reused_stage_ids=tuple(plan.reusable_upstream_stages),violations=tuple(violations))
    actual=perception_inputs.actual_state
    if actual.state_id != bundle.initial_state_id:
        return GovernanceReentryExecutionResult(False,"PPP","memory_conditioned_ppp_reentry_not_executable",violations=("actual-state identity does not match re-entry bundle initial state",))
    try:
        snapshot=runtime.prepare_memory_conditioned_cycle_snapshot(
            actual, perception_inputs.memory_state,
            query=perception_inputs.query, context=perception_inputs.context,
            governing_concerns=perception_inputs.governing_concerns,
            expectation_state=perception_inputs.expectation_state,
            request_trace=perception_inputs.request_trace,
        )
        perceived=snapshot.perceived_decision_state
        if perceived is None:
            raise ValueError("fresh memory-conditioned perception boundary did not return typed PerceivedDecisionState")
        baseline=runtime._baseline_continuation(snapshot.represented_state)
    except Exception as exc:
        return GovernanceReentryExecutionResult(False,"PPP","memory_conditioned_ppp_reentry_not_executable",violations=(f"licensed retrieval/perception/baseline construction failed: {exc}",))
    fresh_hi=replace(horizon_inputs,perceived_state=snapshot.represented_state,baseline_state=baseline)
    fresh_fi=PhiReusableEvaluationInputs(snapshot.represented_state,baseline,runtime.registry.phi_substrate_identity(),("v0.100 state boundary refreshed by licensed memory-conditioned PPP perception",))
    downstream_plan=GovernanceReentryPlan(True,"Phi",("PPP",),("Phi","H","G","R","Graph/Seed","Pi","Pi Completeness","Constraints","Domain Framing","Joint Recovery Feasibility","Adequacy","Sigma","epsilon"),tuple(plan.signal_ids),tuple(plan.invalidated_artifact_ids),False,(),("v0.100 internal bounded handoff from fresh memory-conditioned PPP",))
    db=GovernanceReusableArtifactBundle(bundle.bundle_id+":mppp",bundle.cycle_id,bundle.initial_state_id,bundle.configuration_id,(("PPP",perceived),),tuple(bundle.provenance_ids),("v0.100 licensed retrieval-conditioned P_i(t) accepted as Phi upstream boundary",))
    dba=GovernanceReusableArtifactBundleAssessment(True,db.bundle_id,db.cycle_id,db.initial_state_id,db.configuration_id,("PPP",),(),("fresh memory-conditioned PPP accepted as Phi reusable boundary",))
    result=execute_phi_reentry(runtime,downstream_plan,db,dba,snapshot.represented_state,request,fresh_fi,fresh_hi,governing_inputs,regime_inputs,graph_inputs,pi_inputs)
    if result.decision is not None:
        result=replace(result,recompute_from_stage="PPP",recomputed_stage_ids=("PPP",)+tuple(result.recomputed_stage_ids),reused_stage_ids=(),notes=("v0.100 reacquired P_i(t) through licensed memory retrieval; raw retained M_i(t) was not exposed to the perception adapter",)+tuple(result.notes))
    return result


def refresh_graph_reachability_and_plan_reentry(registry, request):
    """Apply one bounded reachability refresh and explicitly trigger Graph-stage re-entry when material.

    v0.102 is deliberately orchestration-only after the v0.101 registry refresh. It does not
    perform Graph reconstruction itself and it does not admit new structure. A changed registered
    reachability fact invalidates the prior Graph/Seed result explicitly; unchanged observations
    create no invalidation and rejected refreshes create no re-entry authority.
    """
    from .models import GraphReachabilityGovernanceTrigger, GovernanceInvalidationSignal

    refresh = registry.refresh_graph_reachability(request)
    if refresh.status != "APPLIED":
        return GraphReachabilityGovernanceTrigger(
            False, refresh, violations=refresh.violations,
            notes=("rejected reachability refresh creates no governance invalidation or re-entry plan",),
        )
    if not refresh.changed_transformation_ids:
        return GraphReachabilityGovernanceTrigger(
            True, refresh,
            notes=("reachability refresh was a no-op; prior Graph substrate remains current and no re-entry is triggered",),
        )

    evidence_ids = tuple(
        dict.fromkeys(
            obs.provenance_id for obs in request.observations
            if obs.transformation_id in refresh.changed_transformation_ids
        )
    )
    signal = GovernanceInvalidationSignal(
        signal_id=f"graph-reachability:{request.refresh_id}",
        invalidated_stage="Graph/Seed",
        reason="represented Graph reachability changed",
        source_kind="graph_reachability_refresh",
        evidence_ids=evidence_ids,
        artifact_ids=(refresh.prior_graph_substrate_identity,),
        notes=(
            "invalidation is caused only by an applied material reachability refresh of already-represented structure",
            "no novel transformation or structural admission is implied",
        ),
    )
    assessment = assess_governance_reentry((signal,))
    plan = plan_governance_reentry(assessment, (signal,))
    if not assessment.valid or not plan.valid or plan.recompute_from_stage != "Graph/Seed":
        return GraphReachabilityGovernanceTrigger(
            False, refresh, signal, assessment, plan,
            violations=tuple(assessment.violations) + tuple(plan.violations),
            notes=("material refresh could not establish a valid Graph/Seed re-entry plan",),
        )
    return GraphReachabilityGovernanceTrigger(
        True, refresh, signal, assessment, plan,
        notes=(
            "material represented-structure reachability refresh explicitly invalidated Graph/Seed",
            "caller may now use the established Graph-stage executor with post-refresh construction inputs",
        ),
    )

# v0.103 — close represented reachability refresh -> Graph re-entry execution loop
def execute_graph_reachability_refresh_reentry(runtime, trigger, bundle, bundle_assessment, state, request, graph_inputs, pi_inputs):
    """Execute the established Graph-stage re-entry after a material v0.102 reachability trigger.

    The caller supplies the pre-refresh authorized Graph declarations/configuration.  This bridge
    verifies that those inputs were bound to the trigger's prior substrate identity, then advances
    only the substrate identity to the exact post-refresh identity.  It does not admit structure,
    alter Graph declarations, or bypass the ordinary Graph re-entry executor.
    """
    from dataclasses import replace
    from .models import (
        GovernanceReentryExecutionResult, GraphReachabilityGovernanceTrigger,
        GraphReusableConstructionInputs, PiReusableConstructionInputs,
    )
    violations=[]
    if not isinstance(trigger, GraphReachabilityGovernanceTrigger):
        violations.append("reachability execution requires an explicit governance trigger")
    else:
        if not trigger.valid: violations.append("reachability governance trigger must be valid")
        if trigger.refresh_assessment.status != "APPLIED": violations.append("reachability refresh must be applied")
        if not trigger.refresh_assessment.changed_transformation_ids: violations.append("reachability refresh must contain a material change")
        if trigger.invalidation_signal is None or trigger.reentry_plan is None: violations.append("material refresh must carry explicit invalidation and re-entry plan")
        elif trigger.reentry_plan.recompute_from_stage != "Graph/Seed": violations.append("reachability refresh re-entry must begin at Graph/Seed")
    if not isinstance(graph_inputs, GraphReusableConstructionInputs): violations.append("reachability execution requires explicit Graph construction inputs")
    if not isinstance(pi_inputs, PiReusableConstructionInputs): violations.append("reachability execution requires explicit Pi construction inputs")
    if isinstance(trigger, GraphReachabilityGovernanceTrigger) and isinstance(graph_inputs, GraphReusableConstructionInputs):
        ra=trigger.refresh_assessment
        if graph_inputs.graph_substrate_identity != ra.prior_graph_substrate_identity:
            violations.append("Graph construction inputs are not bound to the pre-refresh substrate identity")
        if runtime.registry.graph_substrate_identity() != ra.resulting_graph_substrate_identity:
            violations.append("current Graph substrate identity no longer matches the applied refresh result")
    if violations:
        return GovernanceReentryExecutionResult(False,"Graph/Seed","graph_reachability_reentry_not_executable",violations=tuple(violations))
    post_graph_inputs=replace(graph_inputs, graph_substrate_identity=trigger.refresh_assessment.resulting_graph_substrate_identity,
                              notes=tuple(graph_inputs.notes)+("v0.103 substrate identity advanced only by the applied represented-reachability refresh",))
    result=execute_graph_reentry(runtime,trigger.reentry_plan,bundle,bundle_assessment,state,request,post_graph_inputs,pi_inputs)
    if result.decision is not None:
        result=replace(result,notes=("v0.103 executed Graph-stage re-entry from the exact post-refresh represented substrate",)+tuple(result.notes))
    return result

# v0.105 — explicit structural admission -> Graph-stage invalidation/re-entry planning
def admit_graph_transformation_and_plan_reentry(registry, request):
    """Admit one explicitly governed Graph transformation and plan required Graph-stage re-entry.

    This is deliberately planning-only after admission.  It does not execute the admitted action,
    construct Graph/Pi, or imply Sigma/epsilon authority.  Rejected admission creates no governance
    authority.  A successful configuration change invalidates the prior Graph/Seed substrate.
    """
    from .models import GraphStructuralAdmissionGovernanceTrigger, GovernanceInvalidationSignal

    admission = registry.admit_graph_transformation(request)
    if admission.status != "ADMITTED":
        return GraphStructuralAdmissionGovernanceTrigger(
            False, admission, violations=admission.violations,
            notes=("rejected structural admission creates no governance invalidation or re-entry plan",),
        )
    signal = GovernanceInvalidationSignal(
        signal_id=f"graph-admission:{request.admission_id}",
        invalidated_stage="Graph/Seed",
        reason="represented Graph structure changed by explicit controlled admission",
        source_kind="graph_structural_admission",
        evidence_ids=(request.provenance_id,),
        artifact_ids=(admission.prior_graph_substrate_identity,),
        notes=(
            f"configuration_version={request.configuration_version}",
            f"admitted_transformation_id={admission.admitted_transformation_id}",
            "structural admission changes represented configuration but grants no execution authority",
        ),
    )
    assessment = assess_governance_reentry((signal,))
    plan = plan_governance_reentry(assessment, (signal,))
    if not assessment.valid or not plan.valid or plan.recompute_from_stage != "Graph/Seed":
        return GraphStructuralAdmissionGovernanceTrigger(
            False, admission, signal, assessment, plan,
            violations=tuple(assessment.violations)+tuple(plan.violations),
            notes=("successful admission could not establish a valid Graph/Seed re-entry plan",),
        )
    return GraphStructuralAdmissionGovernanceTrigger(
        True, admission, signal, assessment, plan,
        notes=(
            "explicit versioned structural admission invalidated the prior Graph/Seed substrate",
            "the admitted transformation remains unselected and unlicensed pending ordinary downstream governance",
        ),
    )

# v0.127 — explicit Graph structural revision/removal -> Graph-stage invalidation/re-entry planning
def revise_graph_transformation_and_plan_reentry(registry, request):
    from .models import GraphStructuralRevisionGovernanceTrigger, GovernanceInvalidationSignal
    revision=registry.revise_graph_transformation(request)
    if revision.status != "REVISED":
        return GraphStructuralRevisionGovernanceTrigger(False,revision,violations=revision.violations,notes=("rejected structural revision creates no governance invalidation or re-entry plan",))
    signal=GovernanceInvalidationSignal(
        signal_id=f"graph-revision:{request.revision_id}", invalidated_stage="Graph/Seed",
        reason="represented Graph structure changed by explicit controlled revision",
        source_kind="graph_structural_revision", evidence_ids=(request.provenance_id,),
        artifact_ids=(revision.prior_graph_substrate_identity,),
        notes=(f"configuration_version={request.configuration_version}",f"operation={request.operation}",f"transformation_id={request.transformation_id}","structural lifecycle change grants no execution authority"))
    assessment=assess_governance_reentry((signal,)); plan=plan_governance_reentry(assessment,(signal,))
    if not assessment.valid or not plan.valid or plan.recompute_from_stage != "Graph/Seed":
        return GraphStructuralRevisionGovernanceTrigger(False,revision,signal,assessment,plan,violations=tuple(assessment.violations)+tuple(plan.violations),notes=("successful structural revision could not establish a valid Graph/Seed re-entry plan",))
    return GraphStructuralRevisionGovernanceTrigger(True,revision,signal,assessment,plan,notes=("explicit Graph lifecycle change invalidated the prior Graph/Seed substrate","replacement/removal remains subject to ordinary downstream governance",))

# v0.106 — close controlled structural admission -> Graph re-entry execution loop
def execute_graph_structural_admission_reentry(runtime, trigger, bundle, bundle_assessment, state, request, graph_inputs, pi_inputs):
    """Execute Graph-stage re-entry after an explicit v0.105 structural-admission trigger.

    The caller supplies the pre-admission authorized Graph declarations/configuration. This bridge
    verifies their prior-substrate binding, verifies the live registry is exactly the admitted
    post-configuration substrate, and advances only the substrate identity before delegating to the
    established Graph re-entry executor. Admission itself remains representation, not authorization.
    """
    from dataclasses import replace
    from .models import (
        GovernanceReentryExecutionResult, GraphStructuralAdmissionGovernanceTrigger,
        GraphReusableConstructionInputs, PiReusableConstructionInputs,
    )
    violations=[]
    if not isinstance(trigger, GraphStructuralAdmissionGovernanceTrigger):
        violations.append("structural-admission execution requires an explicit governance trigger")
    else:
        aa=trigger.admission_assessment
        if not trigger.valid: violations.append("structural-admission governance trigger must be valid")
        if aa.status != "ADMITTED": violations.append("structural transformation must have been admitted")
        if not aa.admitted_transformation_id: violations.append("admission must identify the admitted transformation")
        if not aa.configuration_version or not aa.provenance_id: violations.append("admission configuration/provenance must be explicit")
        if trigger.invalidation_signal is None or trigger.reentry_plan is None:
            violations.append("successful admission must carry explicit invalidation and re-entry plan")
        elif trigger.reentry_plan.recompute_from_stage != "Graph/Seed":
            violations.append("structural-admission re-entry must begin at Graph/Seed")
    if not isinstance(graph_inputs, GraphReusableConstructionInputs):
        violations.append("structural-admission execution requires explicit Graph construction inputs")
    if not isinstance(pi_inputs, PiReusableConstructionInputs):
        violations.append("structural-admission execution requires explicit Pi construction inputs")
    if isinstance(trigger, GraphStructuralAdmissionGovernanceTrigger) and isinstance(graph_inputs, GraphReusableConstructionInputs):
        aa=trigger.admission_assessment
        if graph_inputs.graph_substrate_identity != aa.prior_graph_substrate_identity:
            violations.append("Graph construction inputs are not bound to the pre-admission substrate identity")
        if runtime.registry.graph_substrate_identity() != aa.resulting_graph_substrate_identity:
            violations.append("current Graph substrate identity no longer matches the admitted configuration result")
        if aa.admitted_transformation_id not in runtime.registry.graph_transformations:
            violations.append("admitted transformation is no longer represented in the current Graph substrate")
    if violations:
        return GovernanceReentryExecutionResult(False,"Graph/Seed","graph_structural_admission_reentry_not_executable",violations=tuple(violations))
    post_graph_inputs=replace(
        graph_inputs,
        graph_substrate_identity=trigger.admission_assessment.resulting_graph_substrate_identity,
        notes=tuple(graph_inputs.notes)+(
            "v0.106 substrate identity advanced only by the explicit controlled structural admission",
            f"configuration_version={trigger.admission_assessment.configuration_version}",
            f"admitted_transformation_id={trigger.admission_assessment.admitted_transformation_id}",
            f"admission_provenance_id={trigger.admission_assessment.provenance_id}",
        ),
    )
    result=execute_graph_reentry(runtime,trigger.reentry_plan,bundle,bundle_assessment,state,request,post_graph_inputs,pi_inputs)
    if result.decision is not None:
        result=replace(result,notes=(
            "v0.106 executed Graph-stage re-entry from the exact post-admission represented substrate",
            "structural admission itself granted no execution authority",
        )+tuple(result.notes))
    return result

# v0.108 — structural coverage evidence -> explicit Graph/Seed invalidation and planning
def assess_graph_structural_coverage_and_plan_reentry(registry, observation):
    """Qualify structural coverage and create Graph-stage re-entry authority only when material.

    Known incompleteness and unresolved structural uncertainty both invalidate the authority of the
    current Graph/Seed result. Neither case invents or admits missing structure. Sufficient coverage
    creates no governance work.
    """
    from .models import GraphStructuralCoverageGovernanceTrigger, GovernanceInvalidationSignal

    coverage = registry.assess_graph_structural_coverage(observation)
    if not coverage.valid:
        return GraphStructuralCoverageGovernanceTrigger(
            False, coverage, violations=coverage.violations,
            notes=("invalid structural-coverage evidence creates no governance invalidation or re-entry authority",),
        )
    if coverage.structurally_sufficient:
        return GraphStructuralCoverageGovernanceTrigger(
            True, coverage,
            notes=("structural coverage is sufficient for the assessed Graph substrate; no re-entry is triggered",),
        )

    if coverage.material_gap_present:
        reason = "material Graph structural coverage gap identified"
        source_kind = "graph_structural_coverage_incomplete"
        detail_ids = tuple(dict.fromkeys(
            coverage.missing_family_ids + coverage.missing_path_class_ids + coverage.missing_composition_ids
        ))
        detail_note = "known missing structure remains unrepresented until separately defined and admitted"
    else:
        reason = "material Graph structural coverage uncertainty identified"
        source_kind = "graph_structural_coverage_uncertain"
        detail_ids = tuple(coverage.uncertainty_markers)
        detail_note = "unresolved structural uncertainty does not identify or admit any missing transformation semantics"

    signal = GovernanceInvalidationSignal(
        signal_id=f"graph-coverage:{coverage.observation_id}",
        invalidated_stage="Graph/Seed",
        reason=reason,
        source_kind=source_kind,
        evidence_ids=(coverage.provenance_id,),
        artifact_ids=(coverage.graph_substrate_identity,),
        notes=(detail_note,) + tuple(f"coverage-detail:{x}" for x in detail_ids),
    )
    assessment = assess_governance_reentry((signal,))
    plan = plan_governance_reentry(assessment, (signal,))
    if not assessment.valid or not plan.valid or plan.recompute_from_stage != "Graph/Seed":
        return GraphStructuralCoverageGovernanceTrigger(
            False, coverage, signal, assessment, plan,
            violations=tuple(assessment.violations) + tuple(plan.violations),
            notes=("material structural-coverage evidence could not establish a valid Graph/Seed re-entry plan",),
        )
    return GraphStructuralCoverageGovernanceTrigger(
        True, coverage, signal, assessment, plan,
        notes=(
            "material structural-coverage evidence explicitly invalidated prior Graph/Seed authority",
            detail_note,
            "trigger performs no discovery, structural admission, Graph mutation, Sigma selection, epsilon, or Layer-1 transition",
        ),
    )

# v0.109 — structural coverage block / unsupported disposition before Graph reconstruction
def disposition_graph_structural_coverage(trigger):
    """Resolve structural-coverage evidence without falsely reconstructing a known-incomplete Graph.

    Known incompleteness creates a non-authorizing handoff toward a separate definition/admission
    workflow. Unresolved structural uncertainty remains explicitly unsupported. Neither case may
    execute Graph re-entry until coverage authority is repaired by a separately governed event.
    """
    from .models import GraphStructuralCoverageDisposition, GraphStructuralCoverageAdmissionHandoff

    cov = trigger.coverage_assessment
    if not trigger.valid or not cov.valid:
        return GraphStructuralCoverageDisposition(
            False, "invalid", True, trigger,
            violations=tuple(trigger.violations) + tuple(cov.violations),
            notes=("invalid structural-coverage evidence creates no Graph reconstruction or admission authority",),
        )
    if cov.structurally_sufficient:
        return GraphStructuralCoverageDisposition(
            True, "coverage_sufficient", False, trigger,
            notes=("assessed Graph substrate is structurally sufficient; no coverage block or admission handoff is required",),
        )
    if cov.material_gap_present:
        handoff = GraphStructuralCoverageAdmissionHandoff(
            cov.observation_id, cov.graph_substrate_identity, cov.source_id, cov.provenance_id,
            cov.missing_family_ids, cov.missing_path_class_ids, cov.missing_composition_ids,
            notes=(
                "known missing structure requires a complete separately supplied definition before controlled admission",
                "this handoff is not a GraphTransformationAdmissionRequest and grants no structural or execution authority",
            ),
        )
        return GraphStructuralCoverageDisposition(
            True, "admission_definition_required", True, trigger, handoff,
            notes=(
                "Graph reconstruction is blocked because the represented substrate is known materially incomplete",
                "coverage evidence is handed off toward controlled structural definition/admission without inventing semantics",
            ),
        )
    if cov.structural_uncertainty_present:
        return GraphStructuralCoverageDisposition(
            True, "unsupported_uncertain", True, trigger,
            notes=(
                "Graph reconstruction is blocked by unresolved material structural uncertainty",
                "no admission handoff is created because the missing structure is not sufficiently identified",
            ),
        )
    return GraphStructuralCoverageDisposition(
        False, "invalid", True, trigger,
        violations=("valid structural-coverage trigger has no recognized disposition",),
        notes=("no Graph reconstruction or admission authority was created",),
    )

# v0.110 — provenance-bearing security evidence qualification foundation
def assess_security_evidence_observation(observation):
    """Validate epistemic metadata without turning evidence qualification into governance.

    Authoritative/corroborated evidence may be admitted as governance evidence. Provisional
    evidence requires independent confirmation; disputed/untrusted evidence is preserved but
    is not admitted as current governance evidence. This function does not infer re-entry.
    """
    from .models import SecurityEvidenceAssessment
    violations=[]
    for name in ("observation_id","fact_id","source_id","provenance_id"):
        if not str(getattr(observation,name,"" )).strip(): violations.append(f"{name} must be nonempty")
    allowed={"authoritative","corroborated","provisional","disputed","untrusted"}
    if observation.authority_status not in allowed: violations.append("unsupported authority_status")
    if observation.confidence is not None and not (0.0 <= observation.confidence <= 1.0): violations.append("confidence must be within [0,1]")
    if observation.distortion_risk not in {"low","medium","high","unknown"}: violations.append("unsupported distortion_risk")
    ids=tuple(observation.independent_confirmation_ids)
    if any(not str(x).strip() for x in ids): violations.append("independent confirmation identity must be nonempty")
    if len(ids)!=len(set(ids)): violations.append("independent confirmation identities must be unique")
    valid=not violations
    requires=valid and observation.authority_status=="provisional" and not ids
    usable=valid and observation.authority_status in {"authoritative","corroborated"}
    if valid and observation.authority_status=="provisional" and ids:
        # Confirmation identifiers are evidence links, not self-validating authority.
        usable=False
    notes=("evidence qualification creates no feasibility, adequacy, Sigma, epsilon, execution, or re-entry authority",)
    if requires: notes += ("provisional evidence requires independent confirmation before governance use",)
    if valid and observation.authority_status in {"disputed","untrusted"}: notes += ("evidence retained for traceability but is not usable as current governance evidence",)
    return SecurityEvidenceAssessment(valid, observation.observation_id, observation.fact_id,
        observation.source_id, observation.provenance_id, observation.authority_status,
        usable, requires, observation.confidence, observation.distortion_risk,
        tuple(violations), notes)

# v0.111 — evidence-source authority/control and fact dependency qualification
def assess_evidence_dependency_authority(dependency, source_state, *, as_of=None):
    """Determine whether an explicit fact-to-source dependency still has epistemic authority.

    The check is intentionally stage-neutral. Loss of source authority is an epistemic fact;
    mapping that loss to the earliest invalidated canonical stage is a later operation.
    """
    from .models import EvidenceDependencyAuthorityAssessment
    violations=[]
    for name in ("dependency_id","fact_id","observation_id","source_id","source_provenance_id"):
        if not str(getattr(dependency,name,"" )).strip(): violations.append(f"{name} must be nonempty")
    if dependency.dependency_role not in {"primary","supporting","corroborating"}:
        violations.append("unsupported dependency_role")
    for name in ("source_id","provenance_id"):
        if not str(getattr(source_state,name,"" )).strip(): violations.append(f"source {name} must be nonempty")
    if source_state.authority_state not in {"trusted","degraded","compromised","revoked","stale"}:
        violations.append("unsupported source authority_state")
    if source_state.control_state not in {"independent","governed_agent","descendant","unknown"}:
        violations.append("unsupported source control_state")
    if dependency.source_id != source_state.source_id:
        violations.append("dependency source_id does not match source state")
    if dependency.source_provenance_id != source_state.provenance_id:
        violations.append("dependency source provenance does not match source state")
    if source_state.valid_until is not None and source_state.valid_until < source_state.assessed_at:
        violations.append("source valid_until precedes assessed_at")
    valid=not violations
    loss=None
    if valid:
        if source_state.authority_state in {"compromised","revoked","stale"}:
            loss=f"source_{source_state.authority_state}"
        elif source_state.control_state in {"governed_agent","descendant"}:
            loss=f"source_controlled_by_{source_state.control_state}"
        elif as_of is not None and source_state.valid_until is not None and as_of > source_state.valid_until:
            loss="source_expired"
        elif source_state.authority_state == "degraded" or source_state.control_state == "unknown":
            loss="source_authority_unresolved"
    retains=valid and loss is None
    notes=("source/dependency qualification does not infer canonical invalidation stage or create re-entry authority",)
    if valid and loss is not None:
        notes += ("previously admitted evidence dependency no longer retains current epistemic authority",)
    return EvidenceDependencyAuthorityAssessment(valid, dependency.dependency_id, dependency.fact_id,
        dependency.source_id, dependency.source_provenance_id, retains, loss,
        tuple(violations), notes)

# v0.112 — evidence authority loss -> explicit canonical artifact invalidation/re-entry.
def derive_evidence_authority_governance_invalidations(authority_assessments, artifact_dependencies):
    """Map lost evidence authority to canonical stages only through declared dependencies.

    No stage is inferred from fact names, source names, values, or stage order.  A valid
    authority assessment that retains authority creates no invalidation.  A valid assessment
    that has lost/unresolved authority invalidates only explicitly bound canonical artifacts.
    """
    from .models import EvidenceAuthorityGovernanceInvalidationAssessment
    violations=[]
    assessment_ids=[a.dependency_id for a in authority_assessments]
    dep_ids=[d.dependency_id for d in artifact_dependencies]
    if len(assessment_ids)!=len(set(assessment_ids)):
        violations.append("evidence dependency authority assessments must have unique dependency_id values")
    if len(dep_ids)!=len(set(dep_ids)):
        violations.append("artifact dependency_id values must be unique")
    for a in authority_assessments:
        if not a.valid:
            violations.append(f"authority assessment must be valid: {a.dependency_id}")
        if not str(a.dependency_id).strip() or not str(a.fact_id).strip():
            violations.append("authority assessment dependency_id/fact_id must be nonempty")
        if not a.retains_epistemic_authority and not str(a.loss_reason or "").strip():
            violations.append(f"lost authority requires loss_reason: {a.dependency_id}")
    for d in artifact_dependencies:
        if not all(str(getattr(d,n,"" )).strip() for n in ("dependency_id","evidence_dependency_id","fact_id","artifact_id")):
            violations.append(f"artifact dependency identities must be nonempty: {d.dependency_id}")
        if d.stage not in CANONICAL_REENTRY_STAGE_ORDER:
            violations.append(f"unsupported artifact dependency stage: {d.stage}")
        if len(d.provenance_ids)!=len(set(d.provenance_ids)) or any(not str(x).strip() for x in d.provenance_ids):
            violations.append(f"artifact dependency provenance identities must be unique/nonempty: {d.dependency_id}")
    if violations:
        empty=GovernanceReentryAssessment(False,(),(),None,False,("invalid evidence authority/artifact dependency input",),())
        return EvidenceAuthorityGovernanceInvalidationAssessment(False,tuple(assessment_ids),(),(),empty,None,tuple(violations),())

    signals=[]; matched=[]
    for a in authority_assessments:
        if a.retains_epistemic_authority:
            continue
        for d in artifact_dependencies:
            if d.evidence_dependency_id==a.dependency_id and d.fact_id==a.fact_id:
                matched.append(d.dependency_id)
                evidence_ids=tuple(dict.fromkeys((a.source_provenance_id,)+tuple(d.provenance_ids)))
                signals.append(GovernanceInvalidationSignal(
                    signal_id=f"evidence-authority:{a.dependency_id}:{d.dependency_id}",
                    invalidated_stage=d.stage,
                    reason=f"evidence dependency lost epistemic authority: {a.loss_reason}",
                    source_kind="evidence_source_authority_loss",
                    evidence_ids=evidence_ids,
                    artifact_ids=(d.artifact_id,),
                    notes=("derived only from explicit evidence-to-canonical-artifact dependency",),
                ))
    if signals:
        reentry=assess_governance_reentry(tuple(signals))
        plan=plan_governance_reentry(reentry,tuple(signals))
    else:
        reentry=GovernanceReentryAssessment(True,(),(),None,False,(),(
            "no lost-authority assessment matched an explicit canonical artifact dependency",
            "no canonical stage invalidation inferred",
        ))
        plan=plan_governance_reentry(reentry,())
    return EvidenceAuthorityGovernanceInvalidationAssessment(
        True,tuple(assessment_ids),tuple(dict.fromkeys(matched)),tuple(signals),reentry,plan,(),(
            "canonical invalidation is identity-based and requires explicit declared evidence/artifact dependency",
            "no dependency is inferred from source, fact, artifact, or stage semantics",
        ))

# v0.113 — source-state change -> preserved epistemic dependency chain -> re-entry planning.
def orchestrate_epistemic_invalidation_reentry(source_state, evidence_dependencies, artifact_dependencies, *, as_of=None):
    """Run the explicit epistemic invalidation chain without canonical recomputation.

    Only fact-to-source dependencies naming the supplied source/provenance are evaluated.
    Their authority assessments are then mapped to canonical artifacts solely through the
    v0.112 declared dependency mechanism.  Every intermediate assessment is returned.
    """
    from .models import EpistemicInvalidationOrchestrationAssessment
    violations=[]
    if not str(getattr(source_state,"source_id","")).strip():
        violations.append("source source_id must be nonempty")
    if not str(getattr(source_state,"provenance_id","")).strip():
        violations.append("source provenance_id must be nonempty")
    dep_ids=[getattr(d,"dependency_id","") for d in evidence_dependencies]
    if len(dep_ids)!=len(set(dep_ids)):
        violations.append("evidence dependency_id values must be unique")
    matched=[]
    for d in evidence_dependencies:
        if d.source_id==source_state.source_id and d.source_provenance_id==source_state.provenance_id:
            matched.append(d)
    if violations:
        return EpistemicInvalidationOrchestrationAssessment(False,getattr(source_state,"source_id",""),
            getattr(source_state,"provenance_id",""),tuple(dep_ids),(),None,tuple(violations),())

    assessments=tuple(assess_evidence_dependency_authority(d,source_state,as_of=as_of) for d in matched)
    bad=[a.dependency_id for a in assessments if not a.valid]
    if bad:
        return EpistemicInvalidationOrchestrationAssessment(False,source_state.source_id,source_state.provenance_id,
            tuple(d.dependency_id for d in matched),assessments,None,
            tuple(f"invalid evidence dependency authority assessment: {x}" for x in bad),())
    governance=derive_evidence_authority_governance_invalidations(assessments,artifact_dependencies)
    if not governance.valid:
        return EpistemicInvalidationOrchestrationAssessment(False,source_state.source_id,source_state.provenance_id,
            tuple(d.dependency_id for d in matched),assessments,governance,governance.violations,())
    return EpistemicInvalidationOrchestrationAssessment(True,source_state.source_id,source_state.provenance_id,
        tuple(d.dependency_id for d in matched),assessments,governance,(),(
            "source-state change was propagated only through explicit fact/source and artifact dependencies",
            "orchestration stops at governance re-entry planning; no canonical recomputation or execution occurs",
        ))

# v0.114 — controlled dispatch of epistemically generated plans to existing executors.
def execute_epistemic_reentry_plan(runtime, orchestration, *, bundle=None, bundle_assessment=None,
                                    state=None, request=None, ppp_inputs=None, phi_inputs=None,
                                    horizon_inputs=None, governing_inputs=None, regime_inputs=None,
                                    graph_inputs=None, pi_inputs=None):
    """Dispatch a valid v0.113 epistemic plan to the exact existing stage executor.

    No generic recomputation path is introduced.  Required reconstruction inputs are
    checked at the dispatch boundary; unsupported canonical entry stages fail closed.
    """
    from .models import EpistemicReentryExecutionAssessment
    violations=[]
    if not getattr(orchestration,"valid",False):
        violations.append("epistemic orchestration assessment must be valid")
    gov=getattr(orchestration,"governance_invalidation",None)
    if gov is None or not getattr(gov,"valid",False):
        violations.append("valid governance invalidation assessment is required")
    plan=getattr(gov,"plan",None) if gov is not None else None
    if plan is None or not getattr(plan,"valid",False):
        violations.append("valid epistemic governance re-entry plan is required")
    stage=getattr(plan,"recompute_from_stage",None) if plan is not None else None
    if stage is None:
        violations.append("epistemic plan establishes no canonical recomputation stage")
    if violations:
        return EpistemicReentryExecutionAssessment(False,stage,"epistemic_reentry_not_executable",None,tuple(violations),())

    # Every supported branch delegates to the already banked stage-specific executor.
    common=(bundle,bundle_assessment)
    if stage=="Sigma":
        if bundle is None or bundle_assessment is None:
            violations.append("Sigma re-entry requires reusable artifact bundle and assessment")
        else: result=execute_sigma_reentry(runtime,plan,*common)
    elif stage=="Domain Framing":
        if None in (bundle,bundle_assessment,state,request):
            violations.append("Domain Framing re-entry requires bundle, assessment, state, and request")
        else: result=execute_domain_framing_reentry(runtime,plan,*common,state,request)
    elif stage=="Adequacy":
        if bundle is None or bundle_assessment is None:
            violations.append("Adequacy re-entry requires reusable artifact bundle and assessment")
        else: result=execute_adequacy_reentry(runtime,plan,*common)
    elif stage=="Joint Recovery Feasibility":
        if None in (bundle,bundle_assessment,state,request):
            violations.append("Joint Recovery re-entry requires bundle, assessment, state, and request")
        else: result=execute_joint_recovery_reentry(runtime,plan,*common,state,request)
    elif stage=="Constraints":
        if None in (bundle,bundle_assessment,state,request):
            violations.append("Constraints re-entry requires bundle, assessment, state, and request")
        else: result=execute_constraints_reentry(runtime,plan,*common,state,request)
    elif stage=="Pi Completeness":
        if None in (bundle,bundle_assessment,state,request):
            violations.append("Pi Completeness re-entry requires bundle, assessment, state, and request")
        else: result=execute_pi_completeness_reentry(runtime,plan,*common,state,request)
    elif stage=="Pi":
        if None in (bundle,bundle_assessment,state,request,pi_inputs):
            violations.append("Pi re-entry requires bundle, assessment, state, request, and Pi inputs")
        else: result=execute_pi_reentry(runtime,plan,*common,state,request,pi_inputs)
    elif stage=="Graph/Seed":
        if None in (bundle,bundle_assessment,state,request,graph_inputs,pi_inputs):
            violations.append("Graph re-entry requires bundle, assessment, state, request, Graph inputs, and Pi inputs")
        else: result=execute_graph_reentry(runtime,plan,*common,state,request,graph_inputs,pi_inputs)
    elif stage=="R":
        if None in (bundle,bundle_assessment,state,request,regime_inputs,graph_inputs,pi_inputs):
            violations.append("R re-entry requires bundle, assessment, state, request, R, Graph, and Pi inputs")
        else: result=execute_regime_reentry(runtime,plan,*common,state,request,regime_inputs,graph_inputs,pi_inputs)
    elif stage=="G":
        if None in (bundle,bundle_assessment,state,request,governing_inputs,regime_inputs,graph_inputs,pi_inputs):
            violations.append("G re-entry requires bundle, assessment, state, request, G, R, Graph, and Pi inputs")
        else: result=execute_governing_reentry(runtime,plan,*common,state,request,governing_inputs,regime_inputs,graph_inputs,pi_inputs)
    elif stage=="H":
        if None in (bundle,bundle_assessment,state,request,horizon_inputs,governing_inputs,regime_inputs,graph_inputs,pi_inputs):
            violations.append("H re-entry requires bundle, assessment, state, request, H, G, R, Graph, and Pi inputs")
        else: result=execute_horizon_reentry(runtime,plan,*common,state,request,horizon_inputs,governing_inputs,regime_inputs,graph_inputs,pi_inputs)
    elif stage=="Phi":
        if None in (bundle,bundle_assessment,state,request,phi_inputs,horizon_inputs,governing_inputs,regime_inputs,graph_inputs,pi_inputs):
            violations.append("Phi re-entry requires bundle, assessment, state, request, Phi, H, G, R, Graph, and Pi inputs")
        else: result=execute_phi_reentry(runtime,plan,*common,state,request,phi_inputs,horizon_inputs,governing_inputs,regime_inputs,graph_inputs,pi_inputs)
    elif stage=="PPP":
        if None in (bundle,bundle_assessment,request,ppp_inputs,governing_inputs,regime_inputs,graph_inputs,pi_inputs):
            violations.append("PPP re-entry requires bundle, assessment, request, PPP, G, R, Graph, and Pi inputs")
        else: result=execute_ppp_reentry(runtime,plan,*common,request,ppp_inputs,governing_inputs,regime_inputs,graph_inputs,pi_inputs)
    else:
        violations.append(f"no existing bounded stage-specific executor is registered for epistemic re-entry stage: {stage}")
    if violations:
        return EpistemicReentryExecutionAssessment(False,stage,"epistemic_reentry_not_executable",None,tuple(violations),(
            "no generic fallback executor was used",))
    return EpistemicReentryExecutionAssessment(bool(result.valid),stage,
        "epistemic_reentry_dispatched" if result.valid else "epistemic_reentry_executor_rejected",
        result,tuple(result.violations) if not result.valid else (),(
            "dispatch delegated to the existing stage-specific re-entry executor",
            "no epsilon or Layer-1 authority is added by this orchestration boundary",
        ))

# v0.116 — provenance-bearing capability-change observation qualification.
def validate_capability_change_observation(observation):
    """Validate explicit capability-change evidence without inferring capability semantics.

    This is evidence qualification only.  It does not compute PP, project a capability
    trajectory, refresh Graph/Pi, invalidate a canonical stage, or create execution authority.
    """
    from .models import CapabilityChangeValidationAssessment

    violations = []
    allowed = {"gained", "lost", "increased", "decreased", "reconfigured", "uncertain"}
    if not observation.observation_id.strip():
        violations.append("observation_id must be nonempty")
    if not observation.entity_id.strip():
        violations.append("entity_id must be nonempty")
    if not observation.capability_id.strip():
        violations.append("capability_id must be nonempty")
    if observation.observed_at < 0:
        violations.append("observed_at must be nonnegative")
    if observation.change_kind not in allowed:
        violations.append(f"unsupported capability change_kind: {observation.change_kind}")
    if not observation.source_id.strip():
        violations.append("source_id must be nonempty")
    if not observation.provenance_id.strip():
        violations.append("provenance_id must be nonempty")
    if observation.confidence is not None and not (0.0 <= observation.confidence <= 1.0):
        violations.append("confidence must be within [0,1]")
    if len(observation.evidence_ids) != len(set(observation.evidence_ids)):
        violations.append("evidence_ids must be unique")
    if any(not x.strip() for x in observation.evidence_ids):
        violations.append("evidence_ids must be nonempty")
    if len(observation.configuration_ids) != len(set(observation.configuration_ids)):
        violations.append("configuration_ids must be unique")
    if any(not x.strip() for x in observation.configuration_ids):
        violations.append("configuration_ids must be nonempty")

    # Definite change claims require before/after identity sufficient for audit.
    definite = observation.change_kind in {"gained", "lost", "increased", "decreased", "reconfigured"}
    if definite and not observation.current_snapshot_id:
        violations.append("definite capability change requires current_snapshot_id")
    if observation.change_kind in {"increased", "decreased", "reconfigured"} and not observation.prior_snapshot_id:
        violations.append(f"{observation.change_kind} capability change requires prior_snapshot_id")
    if observation.prior_snapshot_id is not None and not observation.prior_snapshot_id.strip():
        violations.append("prior_snapshot_id must be nonempty when supplied")
    if observation.current_snapshot_id is not None and not observation.current_snapshot_id.strip():
        violations.append("current_snapshot_id must be nonempty when supplied")
    if observation.prior_snapshot_id and observation.current_snapshot_id and observation.prior_snapshot_id == observation.current_snapshot_id:
        violations.append("prior_snapshot_id and current_snapshot_id must differ for a reported capability change")

    valid = not violations
    return CapabilityChangeValidationAssessment(
        valid=valid,
        observation_id=observation.observation_id,
        entity_id=observation.entity_id,
        capability_id=observation.capability_id,
        change_kind=observation.change_kind,
        material_change_reported=bool(valid and definite),
        violations=tuple(violations),
        notes=(
            "capability state remains non-scalar and opaque at this evidence boundary",
            "validation does not infer PP magnitude, Graph/Pi change, canonical invalidation, or execution authority",
        ),
    )

# v0.117 — cumulative capability-trajectory projection.
def project_capability_trajectory(trajectory_id, observations, *, as_of=None):
    """Build an ordered non-scalar trajectory from explicit validated change observations.

    The function preserves evidence order, snapshot continuity, provenance, uncertainty,
    and configuration context. It does not infer capability magnitude or Graph/Pi effects.
    """
    from .models import CapabilityTrajectoryProjection, CapabilityTrajectoryProjectionAssessment

    violations=[]
    observations=tuple(observations)
    if not str(trajectory_id).strip():
        violations.append("trajectory_id must be nonempty")
    if not observations:
        violations.append("at least one capability-change observation is required")
        return CapabilityTrajectoryProjectionAssessment(False,None,tuple(violations),(
            "no Graph/Pi mutation or execution authority is created",))

    assessments=[validate_capability_change_observation(o) for o in observations]
    for a in assessments:
        if not a.valid:
            violations.append(f"invalid capability-change observation: {a.observation_id}")
    entity_ids={o.entity_id for o in observations}; capability_ids={o.capability_id for o in observations}
    if len(entity_ids)!=1: violations.append("all observations must concern the same entity_id")
    if len(capability_ids)!=1: violations.append("all observations must concern the same capability_id")
    obs_ids=[o.observation_id for o in observations]
    if len(obs_ids)!=len(set(obs_ids)): violations.append("observation_ids must be unique")
    times=[o.observed_at for o in observations]
    if times != sorted(times) or len(times)!=len(set(times)):
        violations.append("observations must be in strict observed_at order")
    effective_as_of=max(times) if as_of is None else as_of
    if effective_as_of < 0: violations.append("as_of must be nonnegative")
    if any(o.observed_at > effective_as_of for o in observations):
        violations.append("trajectory cannot include observations after as_of")

    # For definite sequential claims, preserve auditable snapshot continuity. Uncertain
    # observations do not invent a snapshot and therefore do not break or repair the chain.
    definite=[o for o in observations if o.change_kind != "uncertain"]
    for prev,cur in zip(definite, definite[1:]):
        if prev.current_snapshot_id and cur.prior_snapshot_id and prev.current_snapshot_id != cur.prior_snapshot_id:
            violations.append(f"snapshot chain discontinuity between {prev.observation_id} and {cur.observation_id}")

    if violations:
        return CapabilityTrajectoryProjectionAssessment(False,None,tuple(violations),(
            "trajectory projection fails closed and does not infer missing capability state",))

    snaps=[]
    for o in definite:
        if o.prior_snapshot_id and (not snaps or snaps[-1] != o.prior_snapshot_id): snaps.append(o.prior_snapshot_id)
        if o.current_snapshot_id and (not snaps or snaps[-1] != o.current_snapshot_id): snaps.append(o.current_snapshot_id)
    cfg=[]
    for o in observations:
        for c in o.configuration_ids:
            if c not in cfg: cfg.append(c)
    trajectory=CapabilityTrajectoryProjection(
        trajectory_id=str(trajectory_id), entity_id=observations[0].entity_id,
        capability_id=observations[0].capability_id, as_of=effective_as_of,
        observation_ids=tuple(obs_ids), ordered_change_kinds=tuple(o.change_kind for o in observations),
        snapshot_chain=tuple(snaps), source_ids=tuple(o.source_id for o in observations),
        provenance_ids=tuple(o.provenance_id for o in observations), configuration_ids=tuple(cfg),
        uncertain_observation_ids=tuple(o.observation_id for o in observations if o.change_kind=="uncertain"),
        notes=("trajectory is temporal and non-scalar; no universal PP aggregation is performed",
               "projection does not modify Graph/Pi or create canonical/execution authority"),)
    return CapabilityTrajectoryProjectionAssessment(True,trajectory,(),(
        "all component observations were independently validated",))

# v0.118 — capability-driven represented-Graph reachability refresh.
def refresh_graph_from_capability_trajectory(registry, trajectory_assessment, dependencies, *, refresh_id):
    """Refresh existing Graph reachability only through explicit capability dependencies.

    A valid non-scalar trajectory supplies the current definite capability snapshot. The
    application must separately declare the exact represented transformation and resulting
    reachability fact. Unknown/new structure is never invented here; the existing v0.101
    refresh boundary and v0.102 Graph/Pi re-entry planning remain authoritative.
    """
    from .models import (CapabilityTrajectoryProjectionAssessment,
        CapabilityGraphReachabilityDependency, CapabilityDrivenGraphRefreshAssessment,
        GraphReachabilityObservation, GraphReachabilityRefreshRequest)
    violations=[]
    deps=tuple(dependencies)
    if not isinstance(trajectory_assessment, CapabilityTrajectoryProjectionAssessment) or not trajectory_assessment.valid or trajectory_assessment.trajectory is None:
        violations.append("valid capability trajectory assessment is required")
        tid=""
        return CapabilityDrivenGraphRefreshAssessment(False,tid,violations=tuple(violations),notes=("no Graph mutation occurred",))
    tr=trajectory_assessment.trajectory; tid=tr.trajectory_id
    if not str(refresh_id).strip(): violations.append("refresh_id must be nonempty")
    if not deps: violations.append("at least one explicit capability-to-Graph dependency is required")
    ids=[]
    current_snapshot=tr.snapshot_chain[-1] if tr.snapshot_chain else None
    for dep in deps:
        if not isinstance(dep, CapabilityGraphReachabilityDependency):
            violations.append("all dependencies must be CapabilityGraphReachabilityDependency records"); continue
        ids.append(dep.dependency_id)
        if not dep.dependency_id.strip(): violations.append("dependency_id must be nonempty")
        if dep.entity_id != tr.entity_id or dep.capability_id != tr.capability_id:
            violations.append(f"dependency does not match trajectory entity/capability: {dep.dependency_id}")
        if not dep.transformation_id.strip(): violations.append(f"transformation_id must be nonempty: {dep.dependency_id}")
        if not dep.capability_snapshot_id.strip(): violations.append(f"capability_snapshot_id must be nonempty: {dep.dependency_id}")
        if dep.reachability_status not in {"reachable","unreachable","uncertain"}: violations.append(f"invalid reachability status: {dep.dependency_id}")
        if dep.reachability_status=="uncertain" and not dep.uncertainty_note.strip(): violations.append(f"uncertain dependency requires uncertainty_note: {dep.dependency_id}")
        if not dep.source_id.strip() or not dep.provenance_id.strip(): violations.append(f"source/provenance must be explicit: {dep.dependency_id}")
    if len(ids)!=len(set(ids)): violations.append("dependency_id values must be unique")
    if current_snapshot is None: violations.append("trajectory has no definite current capability snapshot")
    matched=tuple(d for d in deps if isinstance(d,CapabilityGraphReachabilityDependency) and current_snapshot is not None and d.capability_snapshot_id==current_snapshot and d.entity_id==tr.entity_id and d.capability_id==tr.capability_id)
    if not matched and not violations: violations.append("no declared Graph dependency matches the trajectory current capability snapshot")
    if violations:
        return CapabilityDrivenGraphRefreshAssessment(False,tid,tuple(d.dependency_id for d in matched),violations=tuple(violations),notes=("capability evidence did not authorize a Graph refresh",))
    observations=tuple(GraphReachabilityObservation(
        d.transformation_id,d.reachability_status,tr.as_of,d.source_id,d.provenance_id,d.uncertainty_note,
        {"capability_trajectory_id":tr.trajectory_id,"capability_snapshot_id":current_snapshot,"dependency_id":d.dependency_id,"declared_evidence":dict(d.evidence)}) for d in matched)
    req=GraphReachabilityRefreshRequest(registry.graph_substrate_identity(),observations,str(refresh_id),(
        "v0.118 refresh derived only from explicit capability-to-represented-Graph dependencies",))
    trigger=refresh_graph_reachability_and_plan_reentry(registry,req)
    valid=bool(trigger.valid)
    return CapabilityDrivenGraphRefreshAssessment(valid,tid,tuple(d.dependency_id for d in matched),req,trigger,
        tuple(trigger.violations) if not valid else (),(
        "represented Graph reachability only; no transformation admission or semantic discovery occurred",
        "material reachability change routes through existing Graph/Seed invalidation and Pi/downstream re-entry planning",))

# v0.119 — capability-formation prediction error -> explicit canonical re-entry planning.
def assess_capability_formation_prediction_error(expectation, trajectory_assessment, artifact_dependencies, *, error_id):
    """Compare a prior non-scalar capability expectation with later validated evidence.

    A mismatch invalidates only canonical artifacts explicitly declared as depending on the
    expectation.  No PP magnitude, missing capability, Graph structure, or dependency is inferred.
    """
    from .models import (CapabilityFormationExpectation, CapabilityFormationPredictionError,
        CapabilityPredictionArtifactDependency, CapabilityFormationPredictionErrorAssessment,
        CapabilityTrajectoryProjectionAssessment)
    violations=[]; deps=tuple(artifact_dependencies)
    if not isinstance(expectation, CapabilityFormationExpectation):
        violations.append("CapabilityFormationExpectation is required")
    if not isinstance(trajectory_assessment, CapabilityTrajectoryProjectionAssessment) or not trajectory_assessment.valid or trajectory_assessment.trajectory is None:
        violations.append("valid capability trajectory assessment is required")
    if not str(error_id).strip(): violations.append("error_id must be nonempty")
    if violations:
        return CapabilityFormationPredictionErrorAssessment(False,getattr(expectation,"expectation_id",""),"",violations=tuple(violations),notes=("no canonical invalidation occurred",))
    tr=trajectory_assessment.trajectory
    for name in ("expectation_id","entity_id","capability_id","expected_snapshot_id","source_id","provenance_id"):
        if not str(getattr(expectation,name,"" )).strip(): violations.append(f"{name} must be nonempty")
    if expectation.expected_at < 0: violations.append("expected_at must be nonnegative")
    if expectation.expected_at > tr.as_of: violations.append("trajectory does not yet reach expected_at")
    if expectation.entity_id != tr.entity_id or expectation.capability_id != tr.capability_id:
        violations.append("expectation entity/capability does not match trajectory")
    observed=tr.snapshot_chain[-1] if tr.snapshot_chain else None
    if observed is None: violations.append("trajectory has no definite observed capability snapshot")
    dep_ids=[]
    for d in deps:
        if not isinstance(d,CapabilityPredictionArtifactDependency): violations.append("all artifact dependencies must be CapabilityPredictionArtifactDependency records"); continue
        dep_ids.append(d.dependency_id)
        if not d.dependency_id.strip() or not d.expectation_id.strip() or not d.artifact_id.strip(): violations.append("prediction artifact dependency identities must be nonempty")
        if d.stage not in CANONICAL_REENTRY_STAGE_ORDER: violations.append(f"unsupported prediction artifact dependency stage: {d.stage}")
        if len(d.provenance_ids)!=len(set(d.provenance_ids)) or any(not str(x).strip() for x in d.provenance_ids): violations.append(f"prediction dependency provenance must be unique/nonempty: {d.dependency_id}")
    if len(dep_ids)!=len(set(dep_ids)): violations.append("prediction artifact dependency_id values must be unique")
    if violations:
        return CapabilityFormationPredictionErrorAssessment(False,expectation.expectation_id,tr.trajectory_id,violations=tuple(violations),notes=("prediction-error assessment failed closed",))
    if observed == expectation.expected_snapshot_id:
        empty=GovernanceReentryAssessment(True,(),(),None,False,(),("capability expectation matched later validated evidence",))
        return CapabilityFormationPredictionErrorAssessment(True,expectation.expectation_id,tr.trajectory_id,None,(),(),empty,plan_governance_reentry(empty,()),(),(
            "no capability-formation prediction error; no canonical invalidation created",))
    err=CapabilityFormationPredictionError(str(error_id),expectation.expectation_id,tr.trajectory_id,tr.entity_id,tr.capability_id,
        expectation.expected_snapshot_id,observed,tr.as_of,expectation.source_id,expectation.provenance_id,
        tuple(dict.fromkeys(expectation.configuration_ids+tr.configuration_ids)),(
            "non-scalar snapshot-identity mismatch; magnitude is not inferred",))
    matched=tuple(d for d in deps if d.expectation_id==expectation.expectation_id)
    signals=[]
    for d in matched:
        evid=tuple(dict.fromkeys((expectation.provenance_id,)+d.provenance_ids+tr.provenance_ids))
        signals.append(GovernanceInvalidationSignal(
            signal_id=f"capability-prediction-error:{error_id}:{d.dependency_id}", invalidated_stage=d.stage,
            reason="capability-formation prediction error invalidated an explicitly dependent artifact",
            source_kind="capability_formation_prediction_error", evidence_ids=evid, artifact_ids=(d.artifact_id,),
            configuration_id=expectation.configuration_ids[0] if expectation.configuration_ids else None,
            notes=("dependency was explicitly declared; no canonical dependency was inferred",)))
    if signals:
        rea=assess_governance_reentry(tuple(signals)); plan=plan_governance_reentry(rea,tuple(signals))
    else:
        rea=GovernanceReentryAssessment(True,(),(),None,False,(),("prediction error has no explicitly declared canonical artifact dependency",))
        plan=plan_governance_reentry(rea,())
    return CapabilityFormationPredictionErrorAssessment(True,expectation.expectation_id,tr.trajectory_id,err,
        tuple(d.dependency_id for d in matched),tuple(signals),rea,plan,(),(
            "prediction error is provenance-bearing evidence and does not infer PP magnitude",
            "canonical invalidation occurs only through explicit expectation-to-artifact dependencies",))

# v0.121 — atomic novel function/action + first Graph transformation admission -> Graph re-entry planning
def admit_novel_function_and_plan_reentry(registry, request):
    """Admit explicit host-defined novel consequential structure and plan Graph-stage re-entry.

    No semantic discovery occurs here. Rejection is fail-closed at this boundary: neither the new
    action nor transformation is registered, and no governance/execution authority is created.
    """
    from .models import NovelFunctionAdmissionGovernanceTrigger, GovernanceInvalidationSignal
    admission=registry.admit_novel_function(request)
    if admission.status != "ADMITTED":
        return NovelFunctionAdmissionGovernanceTrigger(False,admission,violations=admission.violations,notes=("rejected novel-function admission creates no governance or execution authority",))
    signal=GovernanceInvalidationSignal(
        signal_id=f"novel-function-admission:{request.admission_id}", invalidated_stage="Graph/Seed",
        reason="represented action/function vocabulary and Graph structure changed by explicit controlled admission",
        source_kind="novel_function_structural_admission", evidence_ids=(request.provenance_id,),
        artifact_ids=(admission.prior_action_registry_identity,admission.prior_graph_substrate_identity),
        notes=(f"configuration_version={request.configuration_version}",f"admitted_action_id={admission.admitted_action_id}",f"admitted_transformation_id={admission.admitted_transformation_id}","admission grants no execution authority"))
    assessment=assess_governance_reentry((signal,)); plan=plan_governance_reentry(assessment,(signal,))
    if not assessment.valid or not plan.valid or plan.recompute_from_stage != "Graph/Seed":
        return NovelFunctionAdmissionGovernanceTrigger(False,admission,signal,assessment,plan,violations=tuple(assessment.violations)+tuple(plan.violations),notes=("admission occurred but a valid Graph/Seed re-entry plan could not be established",))
    return NovelFunctionAdmissionGovernanceTrigger(True,admission,signal,assessment,plan,notes=("atomic novel-function admission invalidated prior Graph/Seed authority","ordinary downstream governance remains required before selection or execution"))

# v0.122 — dynamic recovery-necessity topology admission -> G re-entry planning
def admit_recovery_necessity_and_plan_reentry(registry, request):
    """Admit an explicit recovery-necessity relation and invalidate prior G authority."""
    from .models import RecoveryNecessityAdmissionGovernanceTrigger, GovernanceInvalidationSignal
    admission=registry.admit_recovery_necessity(request)
    if admission.status != "ADMITTED":
        return RecoveryNecessityAdmissionGovernanceTrigger(False,admission,violations=admission.violations,notes=("rejected dependency admission creates no governance or execution authority",))
    signal=GovernanceInvalidationSignal(
        signal_id=f"recovery-necessity-admission:{request.admission_id}", invalidated_stage="G",
        reason="registered recovery-necessity topology changed by explicit controlled admission",
        source_kind="recovery_necessity_structural_admission", evidence_ids=(request.provenance_id,),
        artifact_ids=(admission.prior_governing_substrate_identity,),
        notes=(f"configuration_version={request.configuration_version}",f"admitted_relation_id={admission.admitted_relation_id}","admission grants no selection or execution authority"))
    assessment=assess_governance_reentry((signal,)); plan=plan_governance_reentry(assessment,(signal,))
    if not assessment.valid or not plan.valid or plan.recompute_from_stage != "G":
        return RecoveryNecessityAdmissionGovernanceTrigger(False,admission,signal,assessment,plan,violations=tuple(assessment.violations)+tuple(plan.violations),notes=("admission occurred but valid G re-entry planning failed",))
    return RecoveryNecessityAdmissionGovernanceTrigger(True,admission,signal,assessment,plan,notes=("dynamic governing dependency topology invalidated prior G authority","normal downstream governance remains required",))


# v0.123 — recovery-necessity topology revision/removal -> G re-entry planning
def revise_recovery_necessity_and_plan_reentry(registry, request):
    """Revise/remove an explicit recovery-necessity relation and invalidate prior G authority."""
    from .models import RecoveryNecessityRevisionGovernanceTrigger, GovernanceInvalidationSignal
    revision=registry.revise_recovery_necessity(request)
    if revision.status != "REVISED":
        return RecoveryNecessityRevisionGovernanceTrigger(False,revision,violations=revision.violations,notes=("rejected topology revision creates no governance or execution authority",))
    signal=GovernanceInvalidationSignal(
        signal_id=f"recovery-necessity-revision:{request.revision_id}", invalidated_stage="G",
        reason=f"registered recovery-necessity topology changed by explicit controlled {request.operation}",
        source_kind="recovery_necessity_structural_revision", evidence_ids=(request.provenance_id,),
        artifact_ids=(revision.prior_governing_substrate_identity,),
        notes=(f"configuration_version={request.configuration_version}",f"affected_relation_id={request.relation_id}",f"operation={request.operation}","revision grants no selection or execution authority"))
    assessment=assess_governance_reentry((signal,)); plan=plan_governance_reentry(assessment,(signal,))
    if not assessment.valid or not plan.valid or plan.recompute_from_stage != "G":
        return RecoveryNecessityRevisionGovernanceTrigger(False,revision,signal,assessment,plan,violations=tuple(assessment.violations)+tuple(plan.violations),notes=("revision occurred but valid G re-entry planning failed",))
    return RecoveryNecessityRevisionGovernanceTrigger(True,revision,signal,assessment,plan,notes=("topology revision invalidated prior G authority","normal downstream governance remains required",))

# v0.124 — explicit dynamic control/provenance topology qualification.
def assess_control_provenance_topology(relations, *, topology_id, as_of, governed_agent_ids=()):
    """Validate explicit control/provenance edges and derive only bounded control facts.

    The runtime does not discover edges or infer semantic authority from names.  It derives
    governed-agent control and descendant status only from explicit active relations supplied
    by the host.  The result creates no canonical invalidation or execution authority by itself.
    """
    from .models import ControlProvenanceTopologyAssessment
    violations=[]
    if not str(topology_id).strip(): violations.append("topology_id must be nonempty")
    if as_of is None: violations.append("as_of is required")
    allowed={"creates","controls","delegates","revokes","terminates","descends_from"}
    ids=[]
    for r in relations:
        ids.append(r.relation_id)
        for name in ("relation_id","subject_id","object_id","source_id","provenance_id"):
            if not str(getattr(r,name,"" )).strip(): violations.append(f"relation {name} must be nonempty")
        if r.relation_type not in allowed: violations.append("unsupported control/provenance relation_type")
        if r.subject_id == r.object_id: violations.append("control/provenance relation cannot be self-referential")
        if as_of is not None and r.observed_at > as_of: violations.append("relation observation cannot be later than topology as_of")
        if len(r.evidence_ids)!=len(set(r.evidence_ids)): violations.append("relation evidence_ids must be unique")
    if len(ids)!=len(set(ids)): violations.append("relation_id values must be unique")
    agents=set(governed_agent_ids)
    controlled=set(); descendants=set()
    if not violations:
        active=[r for r in relations if r.active]
        # Explicit control/create/delegation by the governed agent establishes bounded control.
        for r in active:
            if r.subject_id in agents and r.relation_type in {"controls","creates","delegates"}:
                controlled.add(r.object_id)
            if r.relation_type == "descends_from" and r.subject_id in agents:
                descendants.add(r.object_id)
        # Descendant closure uses only explicit descends_from edges.
        changed=True
        while changed:
            changed=False
            parents=agents|descendants
            for r in active:
                if r.relation_type == "descends_from" and r.subject_id in parents and r.object_id not in descendants:
                    descendants.add(r.object_id); changed=True
        controlled |= descendants
    notes=("topology qualification records explicit control/provenance facts only; it does not infer canonical stage invalidation or execution authority",)
    return ControlProvenanceTopologyAssessment(not violations,topology_id,as_of,tuple(relations),tuple(sorted(controlled)),tuple(sorted(descendants)),tuple(violations),notes)

def qualify_evidence_source_from_control_topology(source_state, topology_assessment, *, governed_agent_ids=()):
    """Return an EvidenceSourceAuthorityState whose control status reflects validated topology.

    Existing source authority/provenance is preserved.  Only control_state is refined, so the
    mature evidence-dependency authority and epistemic re-entry chain can consume the result.
    """
    from dataclasses import replace
    if not topology_assessment.valid:
        raise ValueError("control/provenance topology assessment must be valid")
    agents=set(governed_agent_ids)
    if source_state.source_id in topology_assessment.descendant_objects:
        return replace(source_state, control_state="descendant", notes=tuple(source_state.notes)+("control status derived from explicit validated descendant topology",))
    if source_state.source_id in topology_assessment.controlled_by_governed_agent or source_state.source_id in agents:
        return replace(source_state, control_state="governed_agent", notes=tuple(source_state.notes)+("control status derived from explicit validated governed-agent topology",))
    return replace(source_state, control_state="independent", notes=tuple(source_state.notes)+("no active explicit governed-agent control path represented in validated topology",))

# v0.125 — controlled lifecycle/update of explicit control/provenance topology.
def control_provenance_topology_identity(topology_assessment):
    """Deterministic identity for a validated topology snapshot; ordering is non-semantic."""
    import hashlib, json
    if not topology_assessment.valid:
        raise ValueError("control/provenance topology assessment must be valid")
    rows=[]
    for r in topology_assessment.relations:
        rows.append({
            "relation_id":r.relation_id,"subject_id":r.subject_id,"object_id":r.object_id,
            "relation_type":r.relation_type,"observed_at":r.observed_at,"source_id":r.source_id,
            "provenance_id":r.provenance_id,"active":r.active,
            "evidence_ids":sorted(r.evidence_ids),"notes":list(r.notes),
        })
    payload={"topology_id":topology_assessment.topology_id,"as_of":topology_assessment.as_of,
             "relations":sorted(rows,key=lambda x:x["relation_id"])}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

def update_control_provenance_topology(prior_assessment, request):
    """Validate an exact-bound replacement snapshot and expose its explicit structural delta.

    This is a configuration lifecycle operation, not topology discovery.  It does not itself
    infer canonical invalidation; callers may route changed evidence-source control through the
    existing evidence dependency/epistemic re-entry machinery.
    """
    from .models import ControlProvenanceTopologyUpdateAssessment
    violations=[]
    if not prior_assessment.valid: violations.append("prior topology assessment must be valid")
    for name in ("update_id","prior_topology_identity","topology_id","configuration_version","source_id","provenance_id","rationale"):
        if not str(getattr(request,name,"" )).strip(): violations.append(f"{name} must be nonempty")
    prior_identity=""
    if prior_assessment.valid:
        prior_identity=control_provenance_topology_identity(prior_assessment)
        if request.prior_topology_identity != prior_identity:
            violations.append("prior_topology_identity does not match current topology")
        if request.as_of < prior_assessment.as_of:
            violations.append("topology update as_of cannot move backward")
    next_assessment=assess_control_provenance_topology(request.relations,topology_id=request.topology_id,as_of=request.as_of,governed_agent_ids=request.governed_agent_ids)
    if not next_assessment.valid: violations.extend(next_assessment.violations)
    if violations:
        return ControlProvenanceTopologyUpdateAssessment(False,"REJECTED",request.update_id,prior_identity,
            topology_assessment=None,configuration_version=request.configuration_version,source_id=request.source_id,
            provenance_id=request.provenance_id,violations=tuple(violations),notes=("rejected topology update creates no governance or execution authority",))
    old={r.relation_id:r for r in prior_assessment.relations}; new={r.relation_id:r for r in next_assessment.relations}
    added=tuple(sorted(set(new)-set(old))); removed=tuple(sorted(set(old)-set(new)))
    changed=tuple(sorted(i for i in set(old)&set(new) if old[i] != new[i]))
    resulting=control_provenance_topology_identity(next_assessment)
    status="NO_CHANGE" if resulting==prior_identity else "UPDATED"
    return ControlProvenanceTopologyUpdateAssessment(True,status,request.update_id,prior_identity,resulting,next_assessment,
        added,removed,changed,request.configuration_version,request.source_id,request.provenance_id,(),
        ("explicit host-supplied topology snapshot lifecycle validated","update itself grants no canonical invalidation, selection, or execution authority"))

# v0.126 — explicit control/provenance topology dependencies -> canonical invalidation/re-entry.
def derive_control_provenance_governance_invalidations(update, dependencies):
    """Map an accepted topology delta to canonical artifacts only through declared relation dependencies."""
    from .models import (ControlProvenanceGovernanceInvalidationAssessment,
        GovernanceArtifactDependency, GovernanceDependencyChange)
    violations=[]
    if not update.valid or update.status != "UPDATED" or update.topology_assessment is None:
        violations.append("an accepted topology update is required")
    dep_ids=[d.dependency_id for d in dependencies]
    if len(dep_ids)!=len(set(dep_ids)):
        violations.append("dependency_id values must be unique")
    supported={"creates","controls","delegates","revokes","terminates","descends_from"}
    for d in dependencies:
        if not d.dependency_id.strip() or not d.artifact_id.strip() or not d.relation_ids:
            violations.append(f"dependency identity/artifact/relation_ids required: {d.dependency_id}")
        if d.stage not in CANONICAL_REENTRY_STAGE_ORDER:
            violations.append(f"unsupported dependency stage: {d.stage}")
        if len(d.relation_ids)!=len(set(d.relation_ids)) or len(d.relation_types)!=len(set(d.relation_types)):
            violations.append(f"duplicate relation/type identity: {d.dependency_id}")
        if any(t not in supported for t in d.relation_types):
            violations.append(f"unsupported relation type: {d.dependency_id}")
    empty=GovernanceReentryAssessment(True,(),(),None,False,(),("no canonical invalidation established",))
    if violations:
        return ControlProvenanceGovernanceInvalidationAssessment(False,getattr(update,"update_id",""),(),(),(),empty,None,tuple(violations),())
    changed=tuple(dict.fromkeys(update.added_relation_ids+update.removed_relation_ids+update.changed_relation_ids))
    if not changed:
        return ControlProvenanceGovernanceInvalidationAssessment(True,update.update_id,(),(),(),empty,plan_governance_reentry(empty,()),(),("topology update contained no relation delta; no invalidation inferred",))
    # Relation types are taken from both prior-delta semantics available in the accepted new snapshot and declared dependency filters.
    current={r.relation_id:r.relation_type for r in update.topology_assessment.relations}
    matched=[]; signals=[]
    for d in dependencies:
        ids=set(changed).intersection(d.relation_ids)
        if not ids: continue
        # A type filter constrains relations still present; removed relations remain matchable by explicit relation identity.
        if d.relation_types:
            ids={i for i in ids if i not in current or current[i] in d.relation_types}
        if not ids: continue
        matched.append(d.dependency_id)
        signals.append(GovernanceInvalidationSignal(
            signal_id=f"control-topology:{update.update_id}:{d.dependency_id}", invalidated_stage=d.stage,
            reason="explicit control/provenance topology relation changed",
            source_kind="control_provenance_topology_change", evidence_ids=(update.provenance_id,),
            artifact_ids=(d.artifact_id,), configuration_id=update.configuration_version,
            notes=("derived only from explicit topology relation-to-artifact dependency",f"changed_relation_ids={','.join(sorted(ids))}")))
    reentry=assess_governance_reentry(tuple(signals)) if signals else empty
    plan=plan_governance_reentry(reentry,tuple(signals))
    return ControlProvenanceGovernanceInvalidationAssessment(True,update.update_id,changed,tuple(matched),tuple(signals),reentry,plan,(),
        ("no dependency is inferred from topology semantics or stage order","earliest re-entry stage is selected only from explicitly matched artifact dependencies"))

# v0.128 — capability-driven Graph constructibility through explicit structural admission.
def construct_graph_from_capability_trajectory(registry, trajectory_assessment, dependency, *, admission_id):
    """Admit one explicitly specified new represented Graph path supported by capability evidence.

    This closes the constructibility side of capability-driven Graph change without semantic
    discovery.  A valid trajectory supplies only the current definite capability snapshot.  The
    host must provide the complete transformation and its exact dependency/provenance.  Admission
    is delegated to the existing controlled Graph admission boundary and therefore remains subject
    to normal Graph/Pi/downstream governance before any selection or execution.
    """
    from .models import (CapabilityTrajectoryProjectionAssessment,
        CapabilityGraphConstructibilityDependency, CapabilityDrivenGraphConstructibilityAssessment,
        GraphTransformationAdmissionRequest)
    violations=[]
    if not isinstance(trajectory_assessment, CapabilityTrajectoryProjectionAssessment) or not trajectory_assessment.valid or trajectory_assessment.trajectory is None:
        return CapabilityDrivenGraphConstructibilityAssessment(False,"",violations=("valid capability trajectory assessment is required",),notes=("no Graph mutation occurred",))
    tr=trajectory_assessment.trajectory; current=tr.snapshot_chain[-1] if tr.snapshot_chain else None
    if not isinstance(dependency, CapabilityGraphConstructibilityDependency):
        violations.append("explicit CapabilityGraphConstructibilityDependency is required")
    else:
        if not dependency.dependency_id.strip(): violations.append("dependency_id must be nonempty")
        if dependency.entity_id != tr.entity_id or dependency.capability_id != tr.capability_id: violations.append("dependency does not match trajectory entity/capability")
        if not dependency.capability_snapshot_id.strip(): violations.append("capability_snapshot_id must be nonempty")
        elif current is None or dependency.capability_snapshot_id != current: violations.append("dependency must bind to the trajectory current definite capability snapshot")
        if not dependency.configuration_version.strip(): violations.append("configuration_version must be explicit")
        if not dependency.source_id.strip() or not dependency.provenance_id.strip(): violations.append("source/provenance must be explicit")
        if not dependency.rationale.strip(): violations.append("rationale must be explicit")
    if not str(admission_id).strip(): violations.append("admission_id must be nonempty")
    if current is None: violations.append("trajectory has no definite current capability snapshot")
    if violations:
        return CapabilityDrivenGraphConstructibilityAssessment(False,tr.trajectory_id,getattr(dependency,"dependency_id",""),violations=tuple(violations),notes=("capability evidence did not authorize structural admission", "no Graph mutation occurred"))
    req=GraphTransformationAdmissionRequest(
        admission_id=str(admission_id), expected_graph_substrate_identity=registry.graph_substrate_identity(),
        transformation=dependency.transformation, configuration_version=dependency.configuration_version,
        source_id=dependency.source_id, provenance_id=dependency.provenance_id, rationale=dependency.rationale,
        evidence={"capability_trajectory_id":tr.trajectory_id,"capability_snapshot_id":current,
                  "capability_constructibility_dependency_id":dependency.dependency_id,"declared_evidence":dict(dependency.evidence)})
    trigger=admit_graph_transformation_and_plan_reentry(registry,req)
    return CapabilityDrivenGraphConstructibilityAssessment(bool(trigger.valid),tr.trajectory_id,dependency.dependency_id,req,trigger,
        tuple(trigger.violations) if not trigger.valid else (),(
            "constructibility used only an explicit host-supplied transformation; no path or action semantics were invented",
            "successful admission invalidates Graph/Seed and remains unselected/unlicensed pending ordinary downstream governance",))
