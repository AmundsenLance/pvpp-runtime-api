import pytest

from pvpp_runtime import GovernanceInvalidationSignal, assess_governance_reentry


def sig(sid, stage, *, reason="new evidence", source="execution_feedback", evidence=(), artifacts=()):
    return GovernanceInvalidationSignal(sid, stage, reason, source, evidence, artifacts)


def test_single_explicit_invalidation_selects_that_stage():
    a=assess_governance_reentry((sig("i1","Constraints"),))
    assert a.valid and a.recompute_from_stage == "Constraints" and a.return_to_governance


def test_multiple_invalidations_choose_earliest_canonical_stage_not_input_order():
    a=assess_governance_reentry((sig("i1","Sigma"),sig("i2","H"),sig("i3","Adequacy")))
    assert a.valid and a.recompute_from_stage == "H"
    assert a.invalidated_stages == ("Sigma","H","Adequacy")


def test_execution_feedback_does_not_automatically_invalidate_earlier_stage():
    a=assess_governance_reentry((sig("i1","epsilon",source="execution_feedback"),))
    assert a.valid and a.recompute_from_stage == "epsilon"
    assert "PPP" not in a.invalidated_stages


def test_unknown_stage_fails_closed_without_reentry_target():
    a=assess_governance_reentry((sig("i1","Made Up Stage"),))
    assert not a.valid and a.recompute_from_stage is None and not a.return_to_governance


def test_empty_signal_set_does_not_manufacture_reentry():
    a=assess_governance_reentry(())
    assert not a.valid and a.recompute_from_stage is None and not a.return_to_governance


def test_duplicate_signal_identity_fails_closed():
    a=assess_governance_reentry((sig("same","G"),sig("same","Sigma")))
    assert not a.valid


def test_duplicate_evidence_or_artifact_identity_fails_closed():
    a=assess_governance_reentry((sig("i1","Pi",evidence=("e","e")),))
    assert not a.valid
    b=assess_governance_reentry((sig("i2","Graph/Seed",artifacts=("a","a")),))
    assert not b.valid


def test_missing_reason_or_source_kind_fails_closed():
    assert not assess_governance_reentry((sig("i1","G",reason=""),)).valid
    assert not assess_governance_reentry((sig("i2","G",source=""),)).valid


def test_assessment_is_decision_only_and_has_no_recomputed_artifacts():
    a=assess_governance_reentry((sig("i1","Phi"),))
    assert a.recompute_from_stage == "Phi"
    assert not hasattr(a,"recomputed_cycle")
    assert not hasattr(a,"replacement_artifact")
