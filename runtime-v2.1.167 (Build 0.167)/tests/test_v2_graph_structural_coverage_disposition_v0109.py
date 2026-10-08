from pvpp_runtime import (
    GraphStructuralCoverageObservation,
    assess_graph_structural_coverage_and_plan_reentry,
    disposition_graph_structural_coverage,
    GraphTransformationAdmissionRequest,
)
from pvpp_runtime.registry import PVPPRegistry


def obs(reg,status,**kw):
    return GraphStructuralCoverageObservation(
        "cov109",reg.graph_substrate_identity(),status,"coverage-source","coverage-prov",6.0,**kw
    )


def trigger(reg,status,**kw):
    return assess_graph_structural_coverage_and_plan_reentry(reg,obs(reg,status,**kw))


def test_known_gap_is_explicitly_blocked_and_requires_definition_admission():
    r=PVPPRegistry(); d=disposition_graph_structural_coverage(trigger(r,"incomplete",missing_family_ids=("novel-family",)))
    assert d.valid and d.status=="admission_definition_required" and d.graph_reentry_blocked
    assert d.admission_handoff.missing_family_ids==("novel-family",)


def test_handoff_preserves_graph_identity_and_provenance():
    r=PVPPRegistry(); gid=r.graph_substrate_identity()
    d=disposition_graph_structural_coverage(trigger(r,"incomplete",missing_path_class_ids=("p",)))
    h=d.admission_handoff
    assert h.graph_substrate_identity==gid and h.source_id=="coverage-source" and h.provenance_id=="coverage-prov"


def test_handoff_is_not_an_admission_request_and_grants_no_definition():
    r=PVPPRegistry(); d=disposition_graph_structural_coverage(trigger(r,"incomplete",missing_composition_ids=("c",)))
    assert not isinstance(d.admission_handoff,GraphTransformationAdmissionRequest)
    assert not hasattr(d.admission_handoff,"transformation")


def test_uncertainty_is_explicitly_unsupported_and_has_no_admission_handoff():
    r=PVPPRegistry(); d=disposition_graph_structural_coverage(trigger(r,"uncertain",uncertainty_markers=("unknown-depth",)))
    assert d.valid and d.status=="unsupported_uncertain" and d.graph_reentry_blocked
    assert d.admission_handoff is None


def test_sufficient_coverage_is_not_blocked():
    r=PVPPRegistry(); d=disposition_graph_structural_coverage(trigger(r,"sufficient"))
    assert d.valid and d.status=="coverage_sufficient" and not d.graph_reentry_blocked
    assert d.admission_handoff is None


def test_invalid_coverage_remains_fail_closed():
    r=PVPPRegistry(); o=GraphStructuralCoverageObservation("bad","stale","sufficient","s","p",1.0)
    t=assess_graph_structural_coverage_and_plan_reentry(r,o)
    d=disposition_graph_structural_coverage(t)
    assert not d.valid and d.status=="invalid" and d.graph_reentry_blocked


def test_known_gap_disposition_is_nonmutating():
    r=PVPPRegistry(); before=r.graph_substrate_identity()
    d=disposition_graph_structural_coverage(trigger(r,"incomplete",missing_family_ids=("x",)))
    assert d.graph_reentry_blocked and r.graph_substrate_identity()==before
    assert all(x.transformation_id!="x" for x in r.graph_transformations)


def test_blocked_dispositions_do_not_create_new_governance_or_execution_authority():
    r=PVPPRegistry(); t=trigger(r,"incomplete",missing_family_ids=("x",)); d=disposition_graph_structural_coverage(t)
    assert d.trigger.reentry_plan is t.reentry_plan
    assert d.graph_reentry_blocked
    assert not hasattr(d,"execution_license") and not hasattr(d,"epsilon")
