"""Tests for Chapter 12. Run: PVPP_RUNTIME_PATH=<runtime folder> python3 -m pytest -q"""

import pytest
from supervised_failover import (  # first: ops_model puts the runtime on the path
    start_supervised_failover,
    revoke_credential,
    stop,
    reconcile,
    govern_again,
    report_credential,
    at,
    CFG,
    AGENT,
)
from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision import (
    CanonicalResolutionError,
    ConcurrencyConflict,
    ObservationIdentityConflict,
    StaleOwner,
)


def test_revocation_mid_rollout_is_governed_and_the_rollout_stopped():
    s = start_supervised_failover()
    assert s.decision == "graph:failover" and s.tick.continuation_posture == "continue"
    a = revoke_credential(s)
    assert s.affected == (s.aid,)
    assert a.continuation_posture == "reauthorization_required" and a.authority_fence_required
    e = stop(s, a, "cancel")
    assert s.attempt.mapped_command == "abort_rollout"
    assert (e.outcome, e.attestation_status) == ("completed", "verified")
    assert s.orch.rollouts[s.rollout] == "aborted"


def test_enforcement_is_not_effect_and_the_agent_is_governed_again():
    s = start_supervised_failover()
    stop(s, revoke_credential(s), "cancel")
    assert reconcile(s).state == "no_material_effect_evidenced"
    assert reconcile(s, "effect_unknown").unresolved  # unknown stays unresolved
    assert govern_again() == "graph:escalate"


def test_terminate_needs_an_abort_or_emergency_decision():
    s = start_supervised_failover()
    with pytest.raises(ValueError, match="control_not_permitted_by_continuation_posture"):
        stop(s, revoke_credential(s), "terminate")
    s2 = start_supervised_failover()  # the orchestrator reports data corruption
    emergency = s2.cont.checkpoint(
        active_execution_id=s2.aid,
        checkpoint_at=at(4),
        observation=ExecutionObservation("replica-corrupting", emergency=True),
    )
    assert emergency.continuation_posture == "emergency_return"
    assert stop(s2, emergency, "terminate").outcome == "completed"
    assert s2.orch.rollouts[s2.rollout] == "killed"


def test_a_healthy_rollout_cannot_be_stopped_by_governance():
    s = start_supervised_failover()
    with pytest.raises(ValueError, match="control_not_permitted_by_continuation_posture"):
        stop(s, s.tick, "cancel")


def test_a_stale_supervisor_cannot_issue_a_stop():
    s = start_supervised_failover()
    a = revoke_credential(s)
    newer = s.ctl.acquire_ownership(
        active_execution_id=s.aid, owner_id="supervisor-2", acquired_at=at(5)
    )
    assert newer.owner_fence == s.owner.owner_fence + 1
    with pytest.raises(StaleOwner):
        stop(s, a, "cancel")  # supervisor-1 still holds the old fence


def test_a_report_from_an_unregistered_source_changes_nothing():
    s = start_supervised_failover()
    assert report_credential(s, "rumor-1", "revoked", at(3), source="chat-bot") is None
    view = s.obs.read_current_fact_view(
        configuration_id=CFG, subject_id=AGENT, fact_kind="write_credential", fact_id="deploy"
    )
    assert view.value == "granted"


def test_checkpoint_replay_is_idempotent_and_reuse_with_new_content_is_refused():
    s = start_supervised_failover()
    again = s.cont.checkpoint(
        active_execution_id=s.aid,
        checkpoint_at=at(2),
        observation=ExecutionObservation("rollout-25pct"),
    )
    assert again.assessment_id == s.tick.assessment_id
    with pytest.raises(ObservationIdentityConflict):
        s.cont.checkpoint(
            active_execution_id=s.aid,
            checkpoint_at=at(3),
            observation=ExecutionObservation("rollout-25pct", information={"pct": 30}),
        )


def test_a_stale_snapshot_is_refused():
    s = start_supervised_failover()
    snap = s.deps.capture_governance_snapshot(s.aid, created_at=at(3))
    report_credential(s, "cred-2", "revoked", at(4))  # a material fact changes
    with pytest.raises(ConcurrencyConflict):
        s.cont.evaluate_continuation(
            active_execution_id=s.aid,
            snapshot=snap,
            assessed_at=at(4),
            observation=ExecutionObservation("rollout-50pct"),
        )


def test_after_native_call_entry_the_runtime_can_no_longer_checkpoint():
    s = start_supervised_failover()
    s.bridge.invoke_registered_native(s.store, s.aid, s.auth, s.bindings, configuration_id=CFG)
    assert s.rt.native_execution_authorization_status(s.auth.authorization_id) == "consumed"
    with pytest.raises(CanonicalResolutionError, match="consumed"):
        revoke_credential(s)
