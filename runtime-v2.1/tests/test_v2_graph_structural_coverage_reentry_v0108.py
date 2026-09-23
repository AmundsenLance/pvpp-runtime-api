from pvpp_runtime import GraphStructuralCoverageObservation, assess_graph_structural_coverage_and_plan_reentry
from pvpp_runtime.registry import PVPPRegistry

def rt2():
    return type("R",(),{"registry":PVPPRegistry()})()


def obs(rt,status="sufficient",**kw):
    return GraphStructuralCoverageObservation(
        "cov108", rt.registry.graph_substrate_identity(), status, "coverage-source", "coverage-prov", 5.0, **kw
    )


def test_incomplete_coverage_triggers_graph_stage_reentry():
    rt=rt2(); t=assess_graph_structural_coverage_and_plan_reentry(rt.registry,obs(rt,"incomplete",missing_family_ids=("missing-family",)))
    assert t.valid and t.invalidation_signal.invalidated_stage=="Graph/Seed"
    assert t.invalidation_signal.source_kind=="graph_structural_coverage_incomplete"
    assert t.reentry_plan.recompute_from_stage=="Graph/Seed"


def test_uncertain_coverage_triggers_graph_stage_reentry_without_inventing_structure():
    rt=rt2(); before=rt.registry.graph_substrate_identity()
    t=assess_graph_structural_coverage_and_plan_reentry(rt.registry,obs(rt,"uncertain",uncertainty_markers=("composition-depth-unknown",)))
    assert t.valid and t.invalidation_signal.source_kind=="graph_structural_coverage_uncertain"
    assert rt.registry.graph_substrate_identity()==before
    assert "composition-depth-unknown" in t.invalidation_signal.notes[-1]


def test_sufficient_coverage_creates_no_governance_work():
    rt=rt2(); t=assess_graph_structural_coverage_and_plan_reentry(rt.registry,obs(rt))
    assert t.valid and t.invalidation_signal is None and t.reentry_plan is None


def test_invalid_coverage_creates_no_governance_authority():
    rt=rt2(); bad=GraphStructuralCoverageObservation("cov108","stale","sufficient","src","prov",1.0)
    t=assess_graph_structural_coverage_and_plan_reentry(rt.registry,bad)
    assert not t.valid and t.invalidation_signal is None and t.reentry_plan is None


def test_provenance_and_prior_graph_identity_are_preserved():
    rt=rt2(); identity=rt.registry.graph_substrate_identity()
    t=assess_graph_structural_coverage_and_plan_reentry(rt.registry,obs(rt,"incomplete",missing_path_class_ids=("escape-path",)))
    assert t.invalidation_signal.evidence_ids==("coverage-prov",)
    assert t.invalidation_signal.artifact_ids==(identity,)


def test_graph_scope_preserves_only_upstream_stages():
    rt=rt2(); t=assess_graph_structural_coverage_and_plan_reentry(rt.registry,obs(rt,"incomplete",missing_composition_ids=("comp-x",)))
    assert t.reentry_plan.reusable_upstream_stages==("PPP","Phi","H","G","R")
    assert "Graph/Seed" in t.reentry_plan.nonreusable_stages and "Sigma" in t.reentry_plan.nonreusable_stages


def test_known_gap_and_uncertainty_remain_distinct_sources():
    rt=rt2(); a=assess_graph_structural_coverage_and_plan_reentry(rt.registry,obs(rt,"incomplete",missing_family_ids=("f",)))
    rt=rt2(); b=assess_graph_structural_coverage_and_plan_reentry(rt.registry,obs(rt,"uncertain",uncertainty_markers=("u",)))
    assert a.invalidation_signal.source_kind != b.invalidation_signal.source_kind
    assert "known missing structure" in a.invalidation_signal.notes[0]
    assert "does not identify or admit" in b.invalidation_signal.notes[0]


def test_trigger_is_planning_only_and_nonmutating():
    rt=rt2(); before=rt.registry.graph_substrate_identity()
    t=assess_graph_structural_coverage_and_plan_reentry(rt.registry,obs(rt,"incomplete",missing_family_ids=("not-admitted",)))
    assert t.reentry_plan is not None and rt.registry.graph_substrate_identity()==before
    assert all(x.transformation_id != "not-admitted" for x in rt.registry.graph_transformations)
