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


def _open_statuses(store, aeid):
    return [r['status'] for r in store._conn.execute(
        "SELECT status FROM continuation_intents WHERE active_execution_id=? "
        "AND status IN ('prepared','reconciliation_required','terminally_fenced') ORDER BY rowid",
        (aeid,),
    ).fetchall()]


def test_v0163_01_admin_reconcile_cannot_overwrite_concurrent_success(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    store2=trusted_store(tmp_path/'s.db'); dep2=DependencyService(store2); cont2=ContinuationService(store2,dep2,bridge)

    paused=threading.Event(); release=threading.Event()
    real_persist=cont._persist
    def pause_after_advance(a):
        paused.set()
        assert release.wait(5)
        return real_persist(a)
    monkeypatch.setattr(cont,'_persist',pause_after_advance)

    a_result=[]; a_error=[]; b_result=[]; b_error=[]
    def run_a():
        try:
            a_result.append(cont.checkpoint(active_execution_id=rec.active_execution_id,
                observation=ExecutionObservation('A-step',staged=True),checkpoint_at='2026-10-02T16:00:00+00:00'))
        except Exception as exc:a_error.append(exc)
    def run_b():
        try:
            b_result.append(cont2.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,
                authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T16:00:01+00:00'))
        except Exception as exc:b_error.append(exc)

    ta=threading.Thread(target=run_a); ta.start(); assert paused.wait(5)
    tb=threading.Thread(target=run_b); tb.start(); time.sleep(0.05)
    release.set(); ta.join(5); tb.join(5)
    assert not a_error and a_result and a_result[0].canonical_step==1
    assert not ta.is_alive() and not tb.is_alive()
    # Reconciliation racing the live commit must re-read the durable result and
    # report no work required, never terminally fence the now-healthy execution.
    assert not b_result
    assert b_error and 'continuation_reconciliation_not_required' in str(b_error[0])
    row=store._conn.execute("SELECT status FROM continuation_intents WHERE active_execution_id=? ORDER BY rowid DESC LIMIT 1",(rec.active_execution_id,)).fetchone()
    assert row['status']=='closed'
    assert _open_statuses(store,rec.active_execution_id)==[]
    fresh=cont.checkpoint(active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation('after-admin-race',staged=True),checkpoint_at='2026-10-02T16:00:02+00:00')
    assert fresh.canonical_step==2
    store2.close()


def test_v0163_02_reconcile_checkpoint_stress_has_no_false_fence(tmp_path):
    # Repeatedly interleave two checkpoint services with an administrator reconciliation loop.
    for round_no in range(20):
        sub=tmp_path/f'r{round_no}'; sub.mkdir()
        bridge,store,dep,cont,store2,dep2,cont2,rec=_long_running_services(sub)
        successes=[]; failures=[]; reconcile_outcomes=[]; unexpected=[]; reconcile_attempts=[]; reconcile_during_workers=[]; lock=threading.Lock(); stop=threading.Event(); start=threading.Barrier(3); workers_active={'n':0}

        def worker(label,svc):
            n=0; attempts=0
            with lock: workers_active['n']+=1
            start.wait(5)
            try:
                while n<10 and attempts<400:
                    attempts+=1
                    try:
                        a=svc.checkpoint(active_execution_id=rec.active_execution_id,
                            observation=ExecutionObservation(f'{label}-{round_no}-{attempts}',staged=True),
                            checkpoint_at=f'2026-10-02T16:{10+round_no%30:02d}:{attempts%60:02d}+00:00')
                        with lock: successes.append(a.canonical_step)
                        n+=1
                    except (ConcurrencyConflict,ContinuationReconciliationRequired) as exc:
                        with lock: failures.append(str(exc))
                        time.sleep(0.0005)
            finally:
                with lock: workers_active['n']-=1

        def reconciler():
            i=0
            start.wait(5)
            while not stop.is_set():
                i+=1
                with lock:
                    reconcile_attempts.append(i)
                    if workers_active['n']>0: reconcile_during_workers.append(i)
                try:
                    out=cont2.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,
                        authority_id='admin',authority_proof=proof('admin'),
                        reconciled_at=f'2026-10-02T17:{round_no%50:02d}:{i%60:02d}+00:00')
                    with lock: reconcile_outcomes.append(out.get('outcome'))
                except ValueError as exc:
                    if 'continuation_reconciliation_not_required' not in str(exc):
                        with lock: failures.append(f'reconcile:{exc}')
                except (ConcurrencyConflict,ContinuationReconciliationRequired) as exc:
                    with lock: failures.append(f'reconcile:{exc}')
                except Exception as exc:
                    with lock: unexpected.append(exc)
                    return
                time.sleep(0.0005)

        tr=threading.Thread(target=reconciler); t1=threading.Thread(target=worker,args=('A',cont)); t2=threading.Thread(target=worker,args=('B',cont2))
        tr.start(); t1.start(); t2.start(); t1.join(20); t2.join(20); stop.set(); tr.join(5)
        assert not t1.is_alive() and not t2.is_alive() and not tr.is_alive()
        assert unexpected==[]
        assert reconcile_attempts, f'reconciler did not execute in round {round_no}'
        assert reconcile_during_workers, f'reconciler never overlapped checkpoint workers in round {round_no}'
        assert len(successes)==20
        assert len(set(successes))==20
        assert sorted(successes)==list(range(1,21))
        assert 'terminally_fenced' not in reconcile_outcomes
        residue=store._conn.execute("SELECT status FROM continuation_intents WHERE active_execution_id=? AND status IN ('reconciliation_required','terminally_fenced')",(rec.active_execution_id,)).fetchall()
        assert residue==[]
        store2.close(); store.close()


def test_v0163_03_terminal_or_reconciliation_status_beats_retry_message(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    real_persist=cont._persist
    def fail_after_advance(a):
        raise OSError('disk full')
    monkeypatch.setattr(cont,'_persist',fail_after_advance)
    with pytest.raises(OSError):
        cont.checkpoint(active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('diverge',staged=True),checkpoint_at='2026-10-02T18:00:00+00:00')
    monkeypatch.setattr(cont,'_persist',real_persist)
    result=cont.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,
        authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T18:00:01+00:00')
    assert result['outcome']=='terminally_fenced'
    # Add a later assessment event to prove status takes precedence over the old
    # "assessment already committed; retry" branch.
    store._conn.execute("INSERT INTO continuation_events(active_execution_id,event_kind,ref_id) VALUES(?,?,?)",
        (rec.active_execution_id,'assessment','synthetic-later-assessment'))
    with pytest.raises(ContinuationReconciliationRequired,match='terminally_fenced|reconciliation'):
        cont.checkpoint(active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('never',staged=True),checkpoint_at='2026-10-02T18:00:02+00:00')


def test_v0163_04_same_service_stale_prepared_requires_reconciliation(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    monkeypatch.setattr(bridge,'authorize_supervised_advance',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('transient pre-advance')))
    monkeypatch.setattr(cont,'_classify_failed_intent',lambda intent_id: (_ for _ in ()).throw(RuntimeError('classification failed')))
    with pytest.raises(RuntimeError,match='transient pre-advance'):
        cont.checkpoint(active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('transient',staged=True),checkpoint_at='2026-10-02T18:10:00+00:00')
    row=store._conn.execute("SELECT status FROM continuation_intents WHERE active_execution_id=? ORDER BY rowid DESC LIMIT 1",(rec.active_execution_id,)).fetchone()
    assert row['status']=='prepared'
    # Same ContinuationService created this intent, but it is no longer in flight.
    with pytest.raises(ContinuationReconciliationRequired,match='prepared intent not in flight.*reconciliation required'):
        cont.checkpoint(active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('same-service-retry',staged=True),checkpoint_at='2026-10-02T18:10:01+00:00')


def test_v0163_05_other_service_prepared_conflict_explains_reconciliation_path(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    monkeypatch.setattr(bridge,'authorize_supervised_advance',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('transient pre-advance')))
    monkeypatch.setattr(cont,'_classify_failed_intent',lambda intent_id: (_ for _ in ()).throw(RuntimeError('classification failed')))
    with pytest.raises(RuntimeError):
        cont.checkpoint(active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('transient-other',staged=True),checkpoint_at='2026-10-02T18:20:00+00:00')
    store2=trusted_store(tmp_path/'s.db'); dep2=DependencyService(store2); cont2=ContinuationService(store2,dep2,bridge)
    with pytest.raises(ConcurrencyConflict,match='checkpoint.*in flight.*if no checkpoint is in flight.*reconciliation required'):
        cont2.checkpoint(active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('other-service-retry',staged=True),checkpoint_at='2026-10-02T18:20:01+00:00')
    store2.close()
