"""Tests for step 6. Run: PVPP_RUNTIME_PATH=<runtime folder> python3 -m pytest -q"""

import pytest
from pvpp_runtime import ExecutionObservation
from step6_supervise import start_supervised_charge, withdraw_permit, stop, report, at


def test_withdrawn_permit_stops_the_running_charge():
    s = start_supervised_charge()
    a = withdraw_permit(s)
    assert s.affected == (s.active.active_execution_id,)
    assert a.continuation_posture == "reauthorization_required" and a.authority_fence_required
    e = stop(s)
    assert s.attempt.mapped_command == "stop_charge"
    assert e.outcome == "completed" and e.attestation_status == "verified"
    assert s.charger.jobs[s.job] == "stopped"


def test_fence_invalidates_authority_not_yet_used():
    s = start_supervised_charge()
    withdraw_permit(s)
    stop(s)
    assert s.invalidated == (s.auth.authorization_id,)
    assert s.rt.native_execution_authorization_status(s.auth.authorization_id) == "invalidated"


def test_posture_limits_the_stop_the_host_may_request():
    s = start_supervised_charge()
    withdraw_permit(s)
    with pytest.raises(ValueError, match="control_not_permitted_by_continuation_posture"):
        stop(s, control="terminate")          # terminate needs abort or emergency return


def test_report_from_an_unregistered_source_changes_nothing():
    s = start_supervised_charge()
    assert report(s, "rumor-1", "withdrawn", at(5), source="unknown-tool") is None
    view = s.obs.read_current_fact_view(configuration_id="battery-site", subject_id="sensor-A",
                                        fact_kind="charge_permit", fact_id="site")
    assert view.value == "granted"


def test_a_stop_that_arrives_too_late_is_recorded_as_too_late():
    s = start_supervised_charge()
    withdraw_permit(s)
    s.charger.jobs[s.job] = "finished"        # the job ended before the stop arrived
    assert stop(s).outcome == "too_late"


def test_progress_and_completion_are_reported_through_checkpoints():
    s = start_supervised_charge()
    aid = s.active.active_execution_id
    tick = s.cont.checkpoint(active_execution_id=aid, checkpoint_at=at(5),
                             observation=ExecutionObservation("charge-tick-1"))
    assert tick.continuation_posture == "continue" and tick.epsilon_status == "active"
    done = s.cont.checkpoint(active_execution_id=aid, checkpoint_at=at(20),
                             observation=ExecutionObservation("charge-done", completed=True))
    assert done.continuation_posture == "continue" and done.epsilon_status == "completed"


def test_a_healthy_execution_cannot_be_stopped_by_governance():
    s = start_supervised_charge()
    s.assessment = s.cont.checkpoint(active_execution_id=s.active.active_execution_id,
                                     checkpoint_at=at(5),
                                     observation=ExecutionObservation("charge-tick-1"))
    with pytest.raises(ValueError, match="control_not_permitted_by_continuation_posture"):
        stop(s)                               # posture "continue" permits no stop at all
    assert s.rt.native_execution_authorization_status(s.auth.authorization_id) == "issued"
