from pvpp_runtime import (
    CANONICAL_REENTRY_STAGE_ORDER,
    GovernanceInvalidationSignal,
    GovernanceReentryAssessment,
    assess_governance_reentry,
    plan_governance_reentry,
)


def sig(sid, stage, artifacts=()):
    return GovernanceInvalidationSignal(sid, stage, "changed dependency", "test", artifact_ids=artifacts)


def test_plan_marks_earliest_and_all_downstream_nonreusable():
    signals=(sig("s1","Adequacy",("a1",)), sig("s2","Pi",("p1",)))
    a=assess_governance_reentry(signals)
    p=plan_governance_reentry(a, signals)
    i=CANONICAL_REENTRY_STAGE_ORDER.index("Pi")
    assert p.valid and p.recompute_from_stage == "Pi"
    assert p.reusable_upstream_stages == CANONICAL_REENTRY_STAGE_ORDER[:i]
    assert p.nonreusable_stages == CANONICAL_REENTRY_STAGE_ORDER[i:]
    assert p.invalidated_artifact_ids == ("a1","p1")


def test_sigma_invalidation_preserves_upstream_scope():
    signals=(sig("s1","Sigma"),)
    p=plan_governance_reentry(assess_governance_reentry(signals), signals)
    assert p.reusable_upstream_stages[-1] == "Adequacy"
    assert p.nonreusable_stages == ("Sigma","epsilon")


def test_ppp_invalidation_makes_entire_canonical_chain_nonreusable():
    signals=(sig("s1","PPP"),)
    p=plan_governance_reentry(assess_governance_reentry(signals), signals)
    assert p.reusable_upstream_stages == ()
    assert p.nonreusable_stages == CANONICAL_REENTRY_STAGE_ORDER


def test_no_invalidation_creates_no_recomputation_scope():
    a=GovernanceReentryAssessment(True,(),(),None,False,(),("none",))
    p=plan_governance_reentry(a)
    assert p.valid and p.recompute_from_stage is None
    assert p.nonreusable_stages == ()
    assert p.reusable_upstream_stages == CANONICAL_REENTRY_STAGE_ORDER


def test_invalid_assessment_fails_closed():
    a=GovernanceReentryAssessment(False,("x",),(),None,False,("bad",),())
    p=plan_governance_reentry(a)
    assert not p.valid and p.nonreusable_stages == ()


def test_signal_identity_mismatch_fails_closed():
    signals=(sig("s1","G"),)
    a=assess_governance_reentry(signals)
    p=plan_governance_reentry(a,(sig("other","G"),))
    assert not p.valid


def test_plan_is_decision_only():
    signals=(sig("s1","Constraints"),)
    p=plan_governance_reentry(assess_governance_reentry(signals),signals)
    assert p.execute_reentry is False
    assert not hasattr(p,"recomputed_cycle")
    assert not hasattr(p,"replacement_artifacts")


def test_artifact_identity_collection_is_stable_and_deduplicated():
    signals=(sig("s1","G",("a","b")), sig("s2","Sigma",("b","c")))
    p=plan_governance_reentry(assess_governance_reentry(signals),signals)
    assert p.invalidated_artifact_ids == ("a","b","c")
