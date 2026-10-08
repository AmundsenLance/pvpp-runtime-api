from pvpp_runtime import GraphStructuralCoverageObservation
from pvpp_runtime.registry import PVPPRegistry


def obs(rt, status="sufficient", **kw):
    return GraphStructuralCoverageObservation(
        observation_id="cov-1", expected_graph_substrate_identity=rt.registry.graph_substrate_identity(),
        coverage_status=status, source_id="host-model-a", provenance_id="ev-107", observed_at=1.0, **kw)


def test_sufficient_coverage_is_first_class_and_nonmutating():
    rt=type("R",(),{"registry":PVPPRegistry()})(); before=rt.registry.graph_substrate_identity()
    a=rt.registry.assess_graph_structural_coverage(obs(rt))
    assert a.valid and a.structurally_sufficient and not a.material_gap_present and not a.structural_uncertainty_present
    assert rt.registry.graph_substrate_identity()==before


def test_incomplete_requires_explicit_missing_structure():
    rt=type("R",(),{"registry":PVPPRegistry()})()
    bad=rt.registry.assess_graph_structural_coverage(obs(rt,"incomplete"))
    assert not bad.valid
    good=rt.registry.assess_graph_structural_coverage(obs(rt,"incomplete",missing_family_ids=("novel-transfer",)))
    assert good.valid and good.material_gap_present and good.missing_family_ids==("novel-transfer",)


def test_uncertain_requires_explicit_structural_marker():
    rt=type("R",(),{"registry":PVPPRegistry()})()
    bad=rt.registry.assess_graph_structural_coverage(obs(rt,"uncertain")); assert not bad.valid
    good=rt.registry.assess_graph_structural_coverage(obs(rt,"uncertain",uncertainty_markers=("composition-depth-not-established",)))
    assert good.valid and good.structural_uncertainty_present


def test_known_gap_cannot_be_hidden_as_uncertainty():
    rt=type("R",(),{"registry":PVPPRegistry()})()
    a=rt.registry.assess_graph_structural_coverage(obs(rt,"uncertain",missing_path_class_ids=("escape-path",),uncertainty_markers=("maybe",)))
    assert not a.valid and any("incomplete" in x for x in a.violations)


def test_sufficient_cannot_carry_gap_or_uncertainty():
    rt=type("R",(),{"registry":PVPPRegistry()})()
    a=rt.registry.assess_graph_structural_coverage(obs(rt,"sufficient",missing_composition_ids=("c-new",)))
    assert not a.valid


def test_stale_graph_identity_fails_closed():
    rt=type("R",(),{"registry":PVPPRegistry()})()
    o=GraphStructuralCoverageObservation("cov", "stale", "sufficient", "src", "prov", 1.0)
    a=rt.registry.assess_graph_structural_coverage(o)
    assert not a.valid and any("identity changed" in x for x in a.violations)


def test_provenance_is_mandatory():
    rt=type("R",(),{"registry":PVPPRegistry()})()
    o=GraphStructuralCoverageObservation("cov",rt.registry.graph_substrate_identity(),"sufficient","","",1.0)
    a=rt.registry.assess_graph_structural_coverage(o)
    assert not a.valid and len(a.violations)>=2


def test_coverage_assessment_does_not_admit_reported_missing_structure():
    rt=type("R",(),{"registry":PVPPRegistry()})(); before=set(rt.registry.graph_transformations)
    a=rt.registry.assess_graph_structural_coverage(obs(rt,"incomplete",missing_family_ids=("unknown-family",)))
    assert a.valid and set(rt.registry.graph_transformations)==before
