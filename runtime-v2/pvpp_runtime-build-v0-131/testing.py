
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class BoundedViabilityWitness:
    """Testing-only evidence that a modeled ecology admits a viable bounded path.

    This is benchmark ground truth. It is never passed to Pi, Sigma, adequacy,
    projection, or any other PV-PP decision operator.
    """
    feasible: bool
    horizon_steps: int
    action_path: tuple[str, ...] = ()
    state_path: tuple[Any, ...] = ()
    visited_state_count: int = 0
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SequenceDiagnostics:
    """Observational diagnostics only; none of these values affect selection."""
    item_count: int
    switch_count: int
    distinct_item_count: int
    repeated_period: int | None = None
    repeated_period_repetitions: int = 0
    strict_cycle_detected: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MultidomainStressClassification:
    """Testing-layer outcome classification; not a regime or runtime operator."""
    outcome: str
    structurally_feasible: bool
    collapsed: bool
    recovered: bool
    oscillatory: bool
    minimum_margin_initial: float
    minimum_margin_final: float
    policy_diagnostics: SequenceDiagnostics
    governing_diagnostics: SequenceDiagnostics
    notes: tuple[str, ...] = ()


def bounded_viability_oracle(initial_state: Any,
                             action_ids: Sequence[str],
                             transition: Callable[[Any, str], Any],
                             viable: Callable[[Any], bool],
                             horizon_steps: int, *,
                             state_key: Callable[[Any], Any] | None = None,
                             success: Callable[[Any], bool] | None = None,
                             max_visited_states: int = 250_000) -> BoundedViabilityWitness:
    """Breadth-first bounded viability precheck for small deterministic test worlds.

    The oracle proves only that at least one bounded path exists under the supplied
    testing model. It does not certify a PV-PP policy or feed information upstream.
    """
    if horizon_steps < 0:
        raise ValueError("horizon_steps must be nonnegative")
    actions=tuple(action_ids)
    if not actions and horizon_steps:
        return BoundedViabilityWitness(
            False,horizon_steps,visited_state_count=1,
            notes=("no actions supplied to testing-only viability oracle",)
        )
    key=state_key or (lambda s:s)
    if not viable(initial_state):
        return BoundedViabilityWitness(
            False,horizon_steps,state_path=(initial_state,),visited_state_count=1,
            notes=("initial test state is already non-viable",)
        )
    if success is not None and success(initial_state):
        return BoundedViabilityWitness(
            True,horizon_steps,(),(initial_state,),1,
            ("success condition already satisfied at initial state",)
        )

    # (state, actions_so_far, states_so_far)
    frontier=[(initial_state,(),(initial_state,))]
    visited={(0,key(initial_state))}
    visited_count=1
    for depth in range(horizon_steps):
        nxt_frontier=[]
        for state,path,states in frontier:
            for aid in actions:
                nxt=transition(state,aid)
                if not viable(nxt):
                    continue
                npath=path+(aid,)
                nstates=states+(nxt,)
                if success is not None and success(nxt):
                    return BoundedViabilityWitness(
                        True,horizon_steps,npath,nstates,visited_count,
                        ("testing-only witness reached explicit success condition",)
                    )
                token=(depth+1,key(nxt))
                if token in visited:
                    continue
                visited.add(token); visited_count+=1
                if visited_count > max_visited_states:
                    raise RuntimeError("bounded viability oracle exceeded max_visited_states")
                nxt_frontier.append((nxt,npath,nstates))
        frontier=nxt_frontier
        if not frontier:
            return BoundedViabilityWitness(
                False,horizon_steps,visited_state_count=visited_count,
                notes=("no viable path survives through requested bounded horizon",)
            )

    if frontier:
        state,path,states=frontier[0]
        return BoundedViabilityWitness(
            True,horizon_steps,path,states,visited_count,
            ("at least one path remains viable through the requested bounded horizon",)
        )
    return BoundedViabilityWitness(False,horizon_steps,visited_state_count=visited_count)


def analyze_sequence(items: Iterable[Any], *, max_period: int = 12,
                     min_repetitions: int = 3) -> SequenceDiagnostics:
    """Detect simple repeated signatures without calling repetition pathological."""
    xs=tuple(items)
    switches=sum(a != b for a,b in zip(xs,xs[1:]))
    distinct=len(set(xs))
    best_period=None; best_reps=0
    n=len(xs)
    for p in range(1,min(max_period,n//min_repetitions)+1):
        pattern=xs[-p:]
        reps=0
        cursor=n
        while cursor >= p and xs[cursor-p:cursor] == pattern:
            reps += 1
            cursor -= p
        if reps >= min_repetitions:
            best_period=p; best_reps=reps
            break
    return SequenceDiagnostics(
        n,switches,distinct,best_period,best_reps,best_period is not None,
        (
            "periodicity is observational evidence only",
            "no anti-oscillation penalty or selection effect is produced",
        )
    )


def classify_multidomain_stress(*, structurally_feasible: bool,
                                collapsed: bool, recovered: bool,
                                margins: Sequence[Mapping[str,float]],
                                policies: Sequence[str],
                                governing_sets: Sequence[Sequence[str]]) -> MultidomainStressClassification:
    if not margins:
        raise ValueError("at least one margin snapshot required")
    initial=min(float(v) for v in margins[0].values())
    final=min(float(v) for v in margins[-1].values())
    pd=analyze_sequence(policies)
    gd=analyze_sequence(tuple(tuple(x) for x in governing_sets))
    oscillatory=bool(pd.strict_cycle_detected and gd.strict_cycle_detected and
                     not recovered and not collapsed)
    if recovered:
        outcome="recovery"
    elif collapsed:
        outcome="forced_or_observed_collapse" if not structurally_feasible else "collapse_despite_viable_alternative"
    elif oscillatory:
        outcome=("periodic_survival_cycling_with_viable_recovery_path"
                 if structurally_feasible else
                 "structurally_forced_periodic_survival_cycling")
    else:
        outcome="bounded_nonterminal_survival"
    return MultidomainStressClassification(
        outcome,structurally_feasible,collapsed,recovered,oscillatory,
        initial,final,pd,gd,
        (
            "classification is testing-layer evidence, not a new PV-PP regime",
            "oscillation alone is not labeled architectural failure without structural-feasibility evidence",
        )
    )


@dataclass(frozen=True)
class ContaminatedSubstratePairedAssessment:
    """Testing-only comparison of reference and epistemically contaminated cycles.

    The reference side is diagnostic evidence only. No field from this assessment
    may be fed back into Graph, Pi, Constraints, Adequacy, Sigma, or epsilon.
    """
    status: str
    reference_policy_class_ids: tuple[str, ...] = ()
    contaminated_policy_class_ids: tuple[str, ...] = ()
    omitted_reference_class_ids: tuple[str, ...] = ()
    extra_contaminated_class_ids: tuple[str, ...] = ()
    reference_graph_seed_ids: tuple[str, ...] = ()
    contaminated_graph_seed_ids: tuple[str, ...] = ()
    omitted_graph_seed_ids: tuple[str, ...] = ()
    extra_graph_seed_ids: tuple[str, ...] = ()
    reference_pi_complete: bool | None = None
    contaminated_pi_complete: bool | None = None
    apparent_completeness_laundering: bool = False
    adequacy_diverged: bool = False
    selection_diverged: bool = False
    governing_diverged: bool = False
    reference_selected_policy_id: str | None = None
    contaminated_selected_policy_id: str | None = None
    notes: tuple[str, ...] = ()


def _cycle_policy_classes(cycle) -> tuple[str, ...]:
    pi=getattr(cycle,"pi_construction",None)
    ps=getattr(pi,"policy_space",None) if pi is not None else None
    if ps is None:
        return ()
    return tuple(sorted({cid for c in ps.candidates for cid in c.policy_class_ids}))


def _cycle_graph_seeds(cycle) -> tuple[str, ...]:
    graph=getattr(cycle,"graph_assessment",None)
    if graph is None:
        return ()
    return tuple(sorted(s.id for s in getattr(graph,"policy_seeds",()) if getattr(s,"visible",True)))


def compare_contaminated_substrate_cycles(reference_cycle, contaminated_cycle, *,
                                          materially_relevant_reference_class_ids=()
                                          ) -> ContaminatedSubstratePairedAssessment:
    """Compare two completed/partial cycles without granting reference-world authority.

    The caller is responsible for constructing the paired condition (same world/
    substrate as appropriate, different epistemic state). This function observes
    differences only. It never repairs the contaminated cycle or changes any
    runtime object.
    """
    ref_classes=_cycle_policy_classes(reference_cycle)
    con_classes=_cycle_policy_classes(contaminated_cycle)
    ref_seeds=_cycle_graph_seeds(reference_cycle)
    con_seeds=_cycle_graph_seeds(contaminated_cycle)

    omitted_classes=tuple(sorted(set(ref_classes)-set(con_classes)))
    extra_classes=tuple(sorted(set(con_classes)-set(ref_classes)))
    omitted_seeds=tuple(sorted(set(ref_seeds)-set(con_seeds)))
    extra_seeds=tuple(sorted(set(con_seeds)-set(ref_seeds)))

    ref_complete=(getattr(reference_cycle,"pi_completeness",None).complete
                  if getattr(reference_cycle,"pi_completeness",None) is not None else None)
    con_complete=(getattr(contaminated_cycle,"pi_completeness",None).complete
                  if getattr(contaminated_cycle,"pi_completeness",None) is not None else None)

    material=set(materially_relevant_reference_class_ids)
    material_omission=bool(material.intersection(omitted_classes))
    laundering=bool(material_omission and con_complete is True)

    ref_ad=getattr(reference_cycle,"adequacy",None)
    con_ad=getattr(contaminated_cycle,"adequacy",None)
    ref_a=tuple(getattr(ref_ad,"adequate_policy_ids",())) if ref_ad is not None else ()
    con_a=tuple(getattr(con_ad,"adequate_policy_ids",())) if con_ad is not None else ()
    adequacy_diverged=(ref_a != con_a)

    ref_sel=getattr(getattr(reference_cycle,"selection",None),"selected_policy_id",None)
    con_sel=getattr(getattr(contaminated_cycle,"selection",None),"selected_policy_id",None)
    selection_diverged=(ref_sel != con_sel)

    ref_g=tuple(getattr(getattr(reference_cycle,"governing_assessment",None),"governing_domain_ids",()))
    con_g=tuple(getattr(getattr(contaminated_cycle,"governing_assessment",None),"governing_domain_ids",()))
    governing_diverged=(ref_g != con_g)

    if laundering:
        status="material_omission_with_apparent_completeness"
    elif extra_classes or extra_seeds:
        status="contaminated_extra_structure_observed"
    elif omitted_classes or omitted_seeds:
        status="contaminated_omission_observed"
    elif adequacy_diverged or selection_diverged or governing_diverged:
        status="downstream_epistemic_divergence_observed"
    else:
        status="no_structural_or_downstream_divergence_observed"

    return ContaminatedSubstratePairedAssessment(
        status,ref_classes,con_classes,omitted_classes,extra_classes,
        ref_seeds,con_seeds,omitted_seeds,extra_seeds,
        ref_complete,con_complete,laundering,adequacy_diverged,
        selection_diverged,governing_diverged,ref_sel,con_sel,
        (
            "reference cycle is diagnostic evidence only and is not an omniscient runtime input",
            "omission means present on reference side but absent on contaminated side; it does not by itself prove runtime error",
            "extra contaminated structure is observational evidence only until substrate licensing establishes fabrication",
            "no field from this paired assessment is consumed by any decision operator",
        )
    )


@dataclass(frozen=True)
class ProjectionCausalStateConsistencyDeclaration:
    """Host/domain declarations used only by the cross-cycle diagnostic harness.

    The runtime does not infer semantic staleness or contradiction from opaque values.
    A caller may identify inputs it already knows are stale and groups of input
    identities that are mutually contradictory for the modeled projection.
    """
    stale_input_ids: tuple[str, ...] = ()
    contradiction_groups: tuple[tuple[str, ...], ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectionCausalStateCrossCycleAssessment:
    """Testing/integration-only comparison of represented causal inputs across cycles."""
    status: str
    prior_time: float
    current_time: float
    appeared_input_ids: tuple[str, ...] = ()
    disappeared_input_ids: tuple[str, ...] = ()
    updated_input_ids: tuple[str, ...] = ()
    unchanged_input_ids: tuple[str, ...] = ()
    representation_time_regression_ids: tuple[str, ...] = ()
    same_time_value_change_ids: tuple[str, ...] = ()
    host_declared_stale_present_ids: tuple[str, ...] = ()
    contradiction_groups_present: tuple[tuple[str, ...], ...] = ()
    violations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


def compare_projection_causal_state_across_cycles(prior, current, *, declaration=None
                                                   ) -> ProjectionCausalStateCrossCycleAssessment:
    """Observe cross-cycle causal-state consistency without adding decision authority.

    Mechanical invariants are limited to actor/time progression, identity uniqueness,
    non-regression of an input's own represented timestamp, and avoiding two different
    opaque values under the same identity and same represented timestamp. Semantic
    staleness and contradiction are reported only when explicitly declared by the host.
    Disappearance or legitimate timestamped value change is not itself an error.
    """
    decl=declaration or ProjectionCausalStateConsistencyDeclaration()
    violations=[]
    try:
        pt=float(prior.time); ct=float(current.time)
    except Exception as exc:
        raise ValueError("perceived decision-state times must be numeric") from exc
    if getattr(prior,"actor_id",None) != getattr(current,"actor_id",None):
        violations.append("cross-cycle comparison requires the same actor_id")
    if ct < pt:
        violations.append("current perceived decision-state time may not precede prior time")

    pitems=tuple(getattr(prior,"projection_causal_inputs",()) or ())
    citems=tuple(getattr(current,"projection_causal_inputs",()) or ())
    pids=[getattr(x,"input_id",None) for x in pitems]
    cids=[getattr(x,"input_id",None) for x in citems]
    if len(pids) != len(set(pids)):
        violations.append("prior projection causal input ids must be unique")
    if len(cids) != len(set(cids)):
        violations.append("current projection causal input ids must be unique")
    p={x.input_id:x for x in pitems}
    c={x.input_id:x for x in citems}

    appeared=tuple(sorted(set(c)-set(p)))
    disappeared=tuple(sorted(set(p)-set(c)))
    updated=[]; unchanged=[]; regressed=[]; same_time_changed=[]
    for iid in sorted(set(p).intersection(c)):
        a=p[iid]; b=c[iid]
        art=float(a.represented_time); brt=float(b.represented_time)
        av=repr(a.value); bv=repr(b.value)
        if brt < art:
            regressed.append(iid)
        if brt == art and av != bv:
            same_time_changed.append(iid)
        elif av != bv:
            updated.append(iid)
        else:
            unchanged.append(iid)

    stale_decl=tuple(decl.stale_input_ids or ())
    if len(stale_decl) != len(set(stale_decl)):
        violations.append("host-declared stale input ids must be unique")
    stale_present=tuple(sorted(set(stale_decl).intersection(c)))

    present_groups=[]
    for group in tuple(decl.contradiction_groups or ()):
        g=tuple(group)
        if len(g) < 2 or len(g) != len(set(g)) or any(not str(x).strip() for x in g):
            violations.append("each host-declared contradiction group must contain at least two unique nonblank input ids")
            continue
        hit=tuple(sorted(set(g).intersection(c)))
        if len(hit) >= 2:
            present_groups.append(hit)

    flags=[]
    if violations: flags.append("invalid_comparison")
    if regressed: flags.append("representation_time_regression")
    if same_time_changed: flags.append("same_timestamp_value_change")
    if stale_present: flags.append("host_declared_stale_inputs_present")
    if present_groups: flags.append("host_declared_contradiction_present")
    if not flags:
        flags.append("consistent_progression_with_updates" if (appeared or disappeared or updated) else "consistent_progression")
    status="+".join(flags)
    return ProjectionCausalStateCrossCycleAssessment(
        status,pt,ct,appeared,disappeared,tuple(updated),tuple(unchanged),tuple(regressed),
        tuple(same_time_changed),stale_present,tuple(present_groups),tuple(violations),(
            "cross-cycle causal-state comparison is a testing/integration diagnostic only",
            "semantic staleness and contradiction are host/domain declared, never inferred from opaque values",
            "a timestamped value change, appearance, or disappearance may be a legitimate next-cycle information update",
            "no result from this assessment is fed into Graph, Pi, Constraints, Adequacy, Sigma, epsilon, or Layer 1",
        ) + tuple(decl.notes or ())
    )

# v0.63 — testing-only cross-cycle attribution of changes in authoritative Q.
# This intentionally reports co-change, not causation.

def _stable_diagnostic_value(value):
    """Convert runtime values to a deterministic comparison form for diagnostics only."""
    from dataclasses import fields, is_dataclass
    if is_dataclass(value):
        return (value.__class__.__name__, tuple((f.name, _stable_diagnostic_value(getattr(value, f.name))) for f in fields(value)))
    if isinstance(value, Mapping):
        return ("mapping", tuple(sorted(((repr(k), _stable_diagnostic_value(v)) for k, v in value.items()), key=lambda x: x[0])))
    if isinstance(value, (tuple, list)):
        return (value.__class__.__name__, tuple(_stable_diagnostic_value(v) for v in value))
    if isinstance(value, (set, frozenset)):
        return (value.__class__.__name__, tuple(sorted((_stable_diagnostic_value(v) for v in value), key=repr)))
    return (value.__class__.__name__, repr(value))


@dataclass(frozen=True)
class ProjectionAttributionSnapshot:
    """Testing-only snapshot of authoritative inputs/outputs around one Q cycle.

    Signatures are opaque comparison artifacts. They are not semantic hashes,
    model-quality measures, state truth, or decision inputs.
    """
    cycle_time: float
    represented_state_identity: tuple[Any, ...]
    represented_state_signature: Any
    causal_input_signature: Any
    graph_context_signature: Any
    candidate_policy_ids: tuple[str, ...]
    projection_horizons: tuple[float, ...]
    model_authority_signature: Any
    projection_record_signature: Any
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectionCrossCycleAttributionAssessment:
    """Observational attribution of Q change to coincident authoritative-input changes."""
    status: str
    projection_changed: bool
    represented_state_changed: bool
    causal_inputs_changed: bool
    graph_context_changed: bool
    candidate_policy_set_changed: bool
    projection_horizon_changed: bool
    predictive_model_authority_changed: bool
    changed_input_classes: tuple[str, ...] = ()
    determinism_anomaly: bool = False
    notes: tuple[str, ...] = ()


def capture_projection_attribution_snapshot(perceived, cycle) -> ProjectionAttributionSnapshot:
    """Capture a testing-only comparison snapshot from one completed canonical cycle.

    The diagnostic uses only already-represented runtime objects. It neither reads
    Layer-1 objective future state nor supplies anything back to the decision stack.
    """
    if perceived is None:
        raise ValueError("projection attribution snapshot requires the represented perceived decision state used for the cycle")
    records=tuple(getattr(cycle, "projection_records", ()) or ())
    if not records:
        raise ValueError("projection attribution snapshot requires authoritative projection records")
    cycle_time=float(getattr(perceived, "time"))
    state=getattr(perceived, "represented_state")
    state_identity=(str(getattr(perceived,"actor_id","")), str(getattr(perceived,"state_id","")), cycle_time)
    causal=tuple(getattr(perceived,"projection_causal_inputs",()) or ())
    graph=getattr(cycle,"graph_assessment",None)
    if graph is None:
        graph_signature=None
    else:
        graph_signature=_stable_diagnostic_value((
            graph.status,graph.preservation_object_id,graph.regime,graph.governing_domain_ids,
            graph.validated_transformation_ids,graph.excluded_transformation_ids,graph.uncertain_transformation_ids,
            graph.composition_ids,graph.represented_families,graph.missing_required_families,graph.seed_ids,
            graph.failure_codes,graph.policy_seeds,graph.invalid_composition_ids,graph.missing_required_path_class_ids,
            graph.open_uncertainty_markers,graph.uncertain_family_presence_ids,graph.uncertain_only_viable_path_ids,
            graph.safe_to_handoff,
        ))
    policies=tuple(sorted(str(r.policy_id) for r in records))
    horizons=tuple(sorted(set(float(r.projection_horizon) for r in records if r.projection_horizon is not None)))
    model_sig=tuple(sorted({
        (str(getattr(r,"model_id","")), str(getattr(r,"model_version","")),
         str(getattr(r,"model_configuration_id","")), str(getattr(r,"model_parameter_set_id","")))
        for r in records
    }))
    # Exclude state identity/time and model/horizon from the Q-output comparison so
    # the output flag means projected content changed, not merely provenance changed.
    q_payload=[]
    for r in sorted(records,key=lambda x:str(x.policy_id)):
        q_payload.append((
            str(r.policy_id), bool(r.feasible), _stable_diagnostic_value(r.terminal_state),
            _stable_diagnostic_value(r.projected_horizons), _stable_diagnostic_value(r.recovery_corridors),
            _stable_diagnostic_value(r.closure_annotations), _stable_diagnostic_value(r.reopening_annotations),
            _stable_diagnostic_value(r.projected_domain_trajectories), _stable_diagnostic_value(r.reachable_viable),
            tuple(r.right_censored_domain_ids), _stable_diagnostic_value(r.information_quality_trace),
            _stable_diagnostic_value(r.information_quality_claims), tuple(r.reasons), _stable_diagnostic_value(r.metadata),
        ))
    return ProjectionAttributionSnapshot(
        cycle_time,
        state_identity,
        _stable_diagnostic_value(state),
        _stable_diagnostic_value(causal),
        graph_signature,
        policies,
        horizons,
        _stable_diagnostic_value(model_sig),
        _stable_diagnostic_value(tuple(q_payload)),
        (
            "snapshot is testing/integration evidence only and is never consumed by a PV-PP decision operator",
            "comparison signatures preserve represented structure without interpreting domain semantics",
            "projection output content is separated from model/horizon/state provenance for attribution diagnostics",
        ),
    )


def compare_projection_attribution_across_cycles(prior, current) -> ProjectionCrossCycleAttributionAssessment:
    """Report which authoritative-input classes changed alongside authoritative Q.

    This is co-change attribution only. Except for the canonical determinism invariant
    under identical authoritative inputs/model version, no causal claim is inferred.
    """
    if float(current.cycle_time) < float(prior.cycle_time):
        raise ValueError("current attribution snapshot may not precede prior snapshot")
    state_changed=(prior.represented_state_signature != current.represented_state_signature or
                   prior.represented_state_identity != current.represented_state_identity)
    causal_changed=prior.causal_input_signature != current.causal_input_signature
    graph_changed=prior.graph_context_signature != current.graph_context_signature
    policies_changed=prior.candidate_policy_ids != current.candidate_policy_ids
    horizon_changed=prior.projection_horizons != current.projection_horizons
    model_changed=prior.model_authority_signature != current.model_authority_signature
    projection_changed=prior.projection_record_signature != current.projection_record_signature
    classes=[]
    for name,flag in (
        ("represented_state",state_changed),
        ("projection_causal_inputs",causal_changed),
        ("graph_context",graph_changed),
        ("candidate_policy_set",policies_changed),
        ("projection_horizon",horizon_changed),
        ("predictive_model_authority",model_changed),
    ):
        if flag: classes.append(name)
    anomaly=bool(projection_changed and not classes)
    if anomaly:
        status="projection_changed_without_observed_authoritative_input_change"
    elif projection_changed:
        status="projection_changed_with_observed_authoritative_input_change"
    elif classes:
        status="projection_unchanged_with_observed_authoritative_input_change"
    else:
        status="projection_and_observed_authoritative_inputs_unchanged"
    return ProjectionCrossCycleAttributionAssessment(
        status,projection_changed,state_changed,causal_changed,graph_changed,policies_changed,
        horizon_changed,model_changed,tuple(classes),anomaly,(
            "changed_input_classes identify coincident authoritative-input differences, not inferred causes",
            "a changed input may legitimately leave Q unchanged; the runtime does not require sensitivity",
            "a Q change with no observed authoritative-input/model-version change is flagged only because canonical Q is deterministic for identical authoritative inputs and model version",
            "this assessment is testing/integration-only and is not fed into Graph, Pi, Constraints, Adequacy, Sigma, epsilon, or Layer 1",
        )
    )
