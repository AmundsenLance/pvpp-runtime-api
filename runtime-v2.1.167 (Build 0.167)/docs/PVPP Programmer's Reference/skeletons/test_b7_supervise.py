"""Banked expectations for B.7. Run with the other skeleton tests (Listing B.11)."""

import pytest
from pvpp_runtime.supervision import ObservationIdentityConflict, StaleOwner
from pvpp_runtime.supervision import SourceRegistration, ExternalObservation
from b7_supervise import Supervisor, interrupted, completed, at, CFG, SUBJECT, ROOT, PROOF


def test_withdrawal_stops_the_running_job_and_fences_unused_authority():
    s, a, attempt, enforcement, _ = interrupted()
    assert a.continuation_posture == "reauthorization_required" and a.authority_fence_required
    assert s.rt.native_execution_authorization_status(s.auth.authorization_id) == "invalidated"
    assert attempt.mapped_command == "dock_stop"
    assert (enforcement.outcome, enforcement.attestation_status) == ("completed", "verified")


def test_effect_is_reconciled_separately_and_settles_retry():
    s, *_, effect = interrupted()
    assert effect.state == "no_material_effect_evidenced" and not effect.unresolved
    assert s.eff.assert_retry_safe(active_execution_id=s.aid)


def test_completion_records_finality_effect_and_layer1():
    s, done, finality, effect, layer1 = completed()
    assert done.continuation_posture == "continue" and done.epsilon_status == "completed"
    assert finality.epsilon_terminal_status == "completed" and finality.immutable
    assert layer1.canonical_finality_ref == finality.canonical_finality_id
    with pytest.raises(ValueError, match="layer1_conflict"):  # the host verifier refuses
        s.eff.record_layer1_transition(
            active_execution_id=s.aid, effect_reconciliation_ref=effect.effect_record_id,
            prior_actual_state_ref="x", next_actual_state_ref="y", transition_time=at(12),
            evidence_ref="forged", provenance="none", configuration_id=CFG,
            authority_evidence="unsigned")


def test_checkpoint_replay_is_idempotent_and_reuse_with_new_content_is_refused():
    s = Supervisor()
    first = s.tick("charge-10pct", 2)
    assert s.tick("charge-10pct", 3).assessment_id == first.assessment_id
    with pytest.raises(ObservationIdentityConflict):
        s.tick("charge-10pct", 4, information={"pct": 11})


def test_a_superseded_owner_is_refused():
    s = Supervisor()
    (a,) = s.withdraw()
    s.ctl.register_supervisory_owner(owner_id="sup-2", configuration_id=CFG,
                                     registration_authority=ROOT, authority_proof=PROOF,
                                     registered_at=at(5))
    s.ctl.acquire_ownership(active_execution_id=s.aid, owner_id="sup-2", acquired_at=at(5))
    with pytest.raises(StaleOwner):
        s.stop(a)


def test_a_continue_posture_authorizes_no_control():
    s = Supervisor()
    with pytest.raises(ValueError, match="control_not_permitted_by_continuation_posture"):
        s.stop(s.tick("charge-10pct", 2), control="hold")


def test_fact_kinds_must_be_written_in_canonical_form():
    s = Supervisor()  # the fact view keeps the kind as written; a dependency lower-cases it
    s.obs.register_source(SourceRegistration(
        "reg-m2", "door-monitor", ("observation",), ("Door_State",), (SUBJECT,), (CFG,),
        ("governance",), "signed", None, None, "current", ROOT, 1), authority_proof=PROOF)
    o = ExternalObservation("door-1", "door-monitor", "Door_State", "bay", SUBJECT, CFG, "shut",
                            None, at(1), at(1), at(1), {})
    s.obs.submit_observation(o)
    s.obs.commit_admission_change(o, s.obs.assess_observation(o, assessed_at=at(1)),
                                  committed_at=at(1))
    s.deps.register_dependency_binding(
        active_execution_id=s.aid, configuration_id=CFG, subject_id=SUBJECT,
        fact_kind="Door_State", fact_id="bay", registration_authority=ROOT,
        authority_proof=PROOF, registered_at=at(1))
    with pytest.raises(ValueError, match="missing current governed fact"):
        s.tick("charge-10pct", 2)  # fails closed: there is no view under "door_state"


def test_observation_times_are_compared_as_written():
    s = Supervisor()
    s.report("permit-2", "withdrawn", at(5))  # 12:05 UTC
    # 13:01+01:00 is 12:01 UTC, older than the withdrawal, but it sorts later as text.
    assert s.report("permit-3", "granted", "2026-10-07T13:01:00+01:00") is not None
    view = s.obs.read_current_fact_view(configuration_id=CFG, subject_id=SUBJECT,
                                        fact_kind="charge_permit", fact_id="site")
    assert view.value == "granted"
