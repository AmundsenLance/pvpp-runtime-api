from __future__ import annotations

import threading
import time

import pytest

from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision.continuation import ContinuationService, ContinuationReconciliationRequired
from pvpp_runtime.supervision.dependency import DependencyService
from pvpp_runtime.supervision.store import ConcurrencyConflict
from r22_trust_fixture import trusted_store, proof
from test_r22_phase6_control import prepared
from test_r22_phase21_v0162_round7_hardening import _long_running_services


def _open_residue(store, aeid):
    return store._conn.execute(
        "SELECT status FROM continuation_intents WHERE active_execution_id=? "
        "AND status IN ('prepared','reconciliation_required','terminally_fenced') ORDER BY rowid",
        (aeid,),
    ).fetchall()


def test_v0165_01_identical_replay_returns_same_assessment(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    observation=ExecutionObservation('evt-identical',staged=True,realized_pv_bundle={'a':1,'b':2},information={'x':'y'})
    first=cont.checkpoint(active_execution_id=rec.active_execution_id,observation=observation,checkpoint_at='2026-10-02T21:00:00+00:00')
    step=bridge.episode_step(rec.episode_id)
    second=cont.checkpoint(active_execution_id=rec.active_execution_id,observation=observation,checkpoint_at='2026-10-02T21:00:01+00:00')
    assert second.assessment_id==first.assessment_id
    assert bridge.episode_step(rec.episode_id)==step


@pytest.mark.parametrize('changed',[
    ExecutionObservation('evt-changed',emergency=True),
    ExecutionObservation('evt-changed',failed=True),
    ExecutionObservation('evt-changed',completed=True),
    ExecutionObservation('evt-changed',staged=True,realized_pv_bundle={'new':1}),
    ExecutionObservation('evt-changed',staged=True,information={'new':'fact'}),
])
def test_v0165_02_reused_event_id_with_changed_content_is_identity_conflict(tmp_path,changed):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    first=cont.checkpoint(active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation('evt-changed',staged=True),checkpoint_at='2026-10-02T21:05:00+00:00')
    step=bridge.episode_step(rec.episode_id)
    before=store._conn.execute("SELECT count(*) FROM continuation_intents WHERE active_execution_id=?",(rec.active_execution_id,)).fetchone()[0]
    with pytest.raises(ConcurrencyConflict,match='identity_conflict: execution observation event_id reused with changed content'):
        cont.checkpoint(active_execution_id=rec.active_execution_id,observation=changed,checkpoint_at='2026-10-02T21:05:01+00:00')
    assert bridge.episode_step(rec.episode_id)==step
    assert store._conn.execute("SELECT count(*) FROM continuation_intents WHERE active_execution_id=?",(rec.active_execution_id,)).fetchone()[0]==before
    assert first.continuation_posture=='continue'


def test_v0165_03_concurrent_duplicate_rechecked_before_intent_and_advance(tmp_path,monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    store2=trusted_store(tmp_path/'s.db'); dep2=DependencyService(store2); cont2=ContinuationService(store2,dep2,bridge)
    ready=threading.Event(); release=threading.Event(); calls={'n':0}
    real=cont2._existing_observation_assessment
    # v0.164 performs two unsafe outside-transaction lookups (checkpoint + evaluate);
    # v0.165 removes the checkpoint lookup, so the evaluate fast lookup is call 1 and
    # the serialized _prepare_intent recheck is call 2. Pause the final unsafe miss in
    # each implementation so A can commit before B proceeds.
    cols={r['name'] for r in store2._conn.execute('PRAGMA table_info(continuation_observation_commits)').fetchall()}
    unsafe_call=1 if 'observation_digest' in cols else 2
    def gated(*args,**kwargs):
        result=real(*args,**kwargs)
        calls['n']+=1
        if calls['n']==unsafe_call and not cont2._c.in_transaction and result is None:
            ready.set(); assert release.wait(5)
        return result
    monkeypatch.setattr(cont2,'_existing_observation_assessment',gated)
    out=[]; err=[]
    def run_b():
        try:
            out.append(cont2.checkpoint(active_execution_id=rec.active_execution_id,
                observation=ExecutionObservation('dup-race',staged=True),checkpoint_at='2026-10-02T21:10:01+00:00'))
        except Exception as exc:err.append(exc)
    tb=threading.Thread(target=run_b); tb.start(); assert ready.wait(5)
    first=cont.checkpoint(active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation('dup-race',staged=True),checkpoint_at='2026-10-02T21:10:00+00:00')
    assert bridge.episode_step(rec.episode_id)==1
    release.set(); tb.join(5)
    assert not tb.is_alive()
    # The hardened implementation must re-read the committed identity under the
    # intent transaction and resolve B to A's assessment without another advance.
    assert not err and out
    assert out[0].assessment_id==first.assessment_id
    assert bridge.episode_step(rec.episode_id)==1
    assert _open_residue(store,rec.active_execution_id)==[]
    store2.close()


def test_v0165_04_two_service_same_event_stress_never_double_advances(tmp_path):
    bridge,store,dep,cont,store2,dep2,cont2,rec=_long_running_services(tmp_path)
    for i in range(20):
        event=f'dup-stress-{i}'
        barrier=threading.Barrier(2)
        results=[]; errors=[]; lock=threading.Lock()
        def submit(svc,label):
            try:
                barrier.wait(5)
                a=svc.checkpoint(active_execution_id=rec.active_execution_id,
                    observation=ExecutionObservation(event,staged=True),
                    checkpoint_at=f'2026-10-02T21:{20+i//60:02d}:{i%60:02d}+00:00')
                with lock:results.append(a.assessment_id)
            except (ConcurrencyConflict,ContinuationReconciliationRequired) as exc:
                with lock:errors.append((label,exc))
            except Exception as exc:
                with lock:errors.append((label,exc))
        t1=threading.Thread(target=submit,args=(cont,'A')); t2=threading.Thread(target=submit,args=(cont2,'B'))
        t1.start(); t2.start(); t1.join(5); t2.join(5)
        assert not t1.is_alive() and not t2.is_alive()
        # Any retryable contender must resolve to the committed identical assessment
        # after the winner completes; no second canonical advance is permitted.
        if errors:
            assert all(isinstance(exc,ConcurrencyConflict) and not isinstance(exc,ContinuationReconciliationRequired) for _,exc in errors)
            replay=cont.checkpoint(active_execution_id=rec.active_execution_id,
                observation=ExecutionObservation(event,staged=True),
                checkpoint_at=f'2026-10-02T22:{i//60:02d}:{i%60:02d}+00:00')
            results.append(replay.assessment_id)
        assert results and len(set(results))==1
        assert bridge.episode_step(rec.episode_id)==i+1
        assert _open_residue(store,rec.active_execution_id)==[]
    store2.close(); store.close()


def test_v0165_05_fenced_execution_never_returns_historical_replay(tmp_path,monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    old=cont.checkpoint(active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation('old-event',staged=True),checkpoint_at='2026-10-02T21:40:00+00:00')
    real=cont._persist
    monkeypatch.setattr(cont,'_persist',lambda a: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError):
        cont.checkpoint(active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('true-divergence',staged=True),checkpoint_at='2026-10-02T21:40:01+00:00')
    monkeypatch.setattr(cont,'_persist',real)
    result=cont.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,
        authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T21:40:02+00:00')
    assert result['outcome']=='terminally_fenced'
    with pytest.raises(ContinuationReconciliationRequired,match='terminally_fenced'):
        cont.checkpoint(active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('old-event',staged=True),checkpoint_at='2026-10-02T21:40:03+00:00')
    assert old.continuation_posture=='continue'


def test_v0165_06_reconcile_lock_is_typed_concurrency_conflict(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    store2=trusted_store(tmp_path/'s.db'); dep2=DependencyService(store2); cont2=ContinuationService(store2,dep2,bridge)
    store._conn.execute('BEGIN IMMEDIATE')
    try:
        # Force an immediate busy response instead of waiting for SQLite's default timeout.
        store2._conn.execute('PRAGMA busy_timeout=0')
        with pytest.raises(ConcurrencyConflict,match='reconciliation transaction in progress'):
            cont2.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,
                authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T21:50:00+00:00')
    finally:
        store._conn.execute('ROLLBACK'); store2.close()
