from pvpp_runtime import (
    PVPPRuntime, GoverningAssessment, GraphConstructionAssessment,
    CanonicalDecisionCycleAssessment,
)


def _governing(order):
    return GoverningAssessment(
        seed_domain_ids=(order[0],),
        governing_domain_ids=tuple(order),
    )


def _cycle(g, graph):
    return CanonicalDecisionCycleAssessment(
        status="test",
        stopped_at="Sigma",
        pipeline_trace=("G", "Graph/Seed"),
        governing_assessment=g,
        graph_assessment=graph,
    )


def test_cycle_integrity_treats_governing_identity_as_set_not_tuple_order():
    rt = object.__new__(PVPPRuntime)  # audit is pure over the supplied cycle
    g = _governing(("z_primary", "a_support"))
    graph = GraphConstructionAssessment(
        "PASS", "pres", "normal", ("a_support", "z_primary")
    )
    audit = rt.audit_cycle_artifact_integrity(_cycle(g, graph))
    assert "Graph governing-domain identity does not match G" not in audit.violations


def test_cycle_integrity_still_rejects_true_governing_membership_mismatch():
    rt = object.__new__(PVPPRuntime)
    g = _governing(("z_primary", "a_support"))
    graph = GraphConstructionAssessment("PASS", "pres", "normal", ("z_primary",))
    audit = rt.audit_cycle_artifact_integrity(_cycle(g, graph))
    assert "Graph governing-domain identity does not match G" in audit.violations
