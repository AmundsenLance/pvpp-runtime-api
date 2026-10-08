from __future__ import annotations

import pytest

from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision.continuation import ContinuationReconciliationRequired
from test_r22_phase6_control import prepared


def test_v0164_01_checkpoint_audit_failure_is_not_post_commit_success(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    start=bridge.episode_step(rec.episode_id)
    real=store.record_supervisory_operation
    def fail_only_assessed(kind,*args,**kwargs):
        if kind=='continuation_assessed':
            raise OSError('audit sink failure')
        return real(kind,*args,**kwargs)
    monkeypatch.setattr(store,'record_supervisory_operation',fail_only_assessed)
    with pytest.raises(OSError,match='audit sink failure'):
        cont.checkpoint(active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('audit-fail-x',staged=True),checkpoint_at='2026-10-02T20:00:00+00:00')
    assert bridge.episode_step(rec.episode_id)==start+1
    assert store._conn.execute("SELECT count(*) FROM continuation_assessments WHERE active_execution_id=?",(rec.active_execution_id,)).fetchone()[0]==1  # fixture only
    assert store._conn.execute("SELECT count(*) FROM audit_events WHERE event_kind='continuation_assessed' AND subject_id=?",(rec.active_execution_id,)).fetchone()[0]==1  # fixture only
    row=store._conn.execute("SELECT status FROM continuation_intents WHERE active_execution_id=? ORDER BY rowid DESC LIMIT 1",(rec.active_execution_id,)).fetchone()
    assert row['status']=='reconciliation_required'
    monkeypatch.setattr(store,'record_supervisory_operation',real)
    with pytest.raises(ContinuationReconciliationRequired):
        cont.checkpoint(active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('audit-fail-x',staged=True),checkpoint_at='2026-10-02T20:00:01+00:00')
    assert bridge.episode_step(rec.episode_id)==start+1


def test_v0164_02_same_committed_event_is_idempotent(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    first=cont.checkpoint(active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation('idem-x',staged=True),checkpoint_at='2026-10-02T20:10:00+00:00')
    step=bridge.episode_step(rec.episode_id)
    second=cont.checkpoint(active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation('idem-x',staged=True),checkpoint_at='2026-10-02T20:10:01+00:00')
    assert second.assessment_id==first.assessment_id
    assert bridge.episode_step(rec.episode_id)==step
    assert store._conn.execute("SELECT count(*) FROM continuation_observation_commits WHERE active_execution_id=? AND event_id=?",(rec.active_execution_id,'idem-x')).fetchone()[0]==1


@pytest.mark.parametrize('bad',['t','2026-13-45T99:00:00',''])
def test_v0164_03_invalid_checkpoint_time_rejected_before_intent(tmp_path,bad):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    before=store._conn.execute("SELECT count(*) FROM continuation_intents WHERE active_execution_id=?",(rec.active_execution_id,)).fetchone()[0]
    step=bridge.episode_step(rec.episode_id)
    with pytest.raises(ValueError,match='invalid consequential operation timestamp'):
        cont.checkpoint(active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('bad-time-'+repr(bad),staged=True),checkpoint_at=bad)
    assert store._conn.execute("SELECT count(*) FROM continuation_intents WHERE active_execution_id=?",(rec.active_execution_id,)).fetchone()[0]==before
    assert bridge.episode_step(rec.episode_id)==step


def test_v0164_04_valid_offset_checkpoint_time_accepted(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    a=cont.checkpoint(active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation('good-offset',staged=True),checkpoint_at='2026-10-02T15:30:00-05:00')
    assert a.assessed_at=='2026-10-02T15:30:00-05:00'
    assert a.canonical_step==1
