from __future__ import annotations

import threading
import pytest

from r22_trust_fixture import trusted_store, proof
from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision.continuation import ContinuationService, ContinuationReconciliationRequired
from pvpp_runtime.supervision.observation import ObservationService, ExternalObservation
from pvpp_runtime.supervision.effect import EffectService
from test_r22_phase6_control import prepared
from test_r3_phase2_canonical_bridge import setup as bridge_setup


def _latest_intent(store, active_execution_id):
    return store._conn.execute(
        "SELECT * FROM continuation_intents WHERE active_execution_id=? ORDER BY rowid DESC LIMIT 1",
        (active_execution_id,),
    ).fetchone()


def test_v0159_01_pre_advance_exception_abandons_intent_and_fresh_checkpoint_succeeds(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T13:00:00+00:00')
    before=bridge.episode_step(rec.episode_id)
    original=bridge.authorize_supervised_advance
    def transient(*args, **kwargs):
        raise RuntimeError('transient pre-advance failure')
    monkeypatch.setattr(bridge,'authorize_supervised_advance',transient)
    with pytest.raises(RuntimeError, match='transient pre-advance failure'):
        cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,
            observation=ExecutionObservation('pre-advance-fail'),assessed_at='2026-10-02T13:00:01+00:00')
    monkeypatch.setattr(bridge,'authorize_supervised_advance',original)
    assert bridge.episode_step(rec.episode_id)==before
    row=_latest_intent(store,rec.active_execution_id)
    assert row['status']=='abandoned'
    assert not store.continuation_reconciliation_required(rec.active_execution_id)
    fresh=cont.checkpoint(active_execution_id=rec.active_execution_id,observation=ExecutionObservation('fresh-after-abandon'),checkpoint_at='2026-10-02T13:00:02+00:00')
    assert fresh.canonical_step==before+1


def test_v0159_02_threaded_snapshot_conflict_is_abandoned_not_terminally_fenced(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T13:10:00+00:00')
    before=bridge.episode_step(rec.episode_id)
    prepared_evt=threading.Event(); changed_evt=threading.Event()
    original_prepare=cont._prepare_intent
    def prepare_then_pause(*args, **kwargs):
        intent_id=original_prepare(*args, **kwargs)
        prepared_evt.set()
        assert changed_evt.wait(timeout=5), 'second connection did not commit change'
        return intent_id
    monkeypatch.setattr(cont,'_prepare_intent',prepare_then_pause)
    error=[]
    def checkpoint_thread():
        try:
            cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,
                observation=ExecutionObservation('threaded-conflict'),assessed_at='2026-10-02T13:10:01+00:00')
        except Exception as exc:
            error.append(exc)
    th=threading.Thread(target=checkpoint_thread)
    th.start()
    assert prepared_evt.wait(timeout=5), 'continuation intent was not committed'
    store2=trusted_store(tmp_path/'s.db')
    obs2=ObservationService(store2)
    o=ExternalObservation('o-thread','src','reachability','net','sub','cfg','down',None,
        '2026-10-02T13:10:01+00:00','2026-10-02T13:10:01+00:00','2026-10-02T13:10:01+00:00',{})
    obs2.submit_observation(o)
    a=obs2.assess_observation(o,assessed_at='2026-10-02T13:10:01+00:00')
    obs2.commit_admission_change(o,a,committed_at='2026-10-02T13:10:01+00:00')
    store2.close(); changed_evt.set(); th.join(timeout=5)
    assert not th.is_alive(), 'checkpoint thread hung'
    assert error and 'snapshot_conflict' in str(error[0])
    assert bridge.episode_step(rec.episode_id)==before
    row=_latest_intent(store,rec.active_execution_id)
    assert row['status']=='abandoned'
    with pytest.raises(ValueError,match='continuation_reconciliation_not_required'):
        cont.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,
            authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T13:10:02+00:00')
    assert _latest_intent(store,rec.active_execution_id)['status']=='closed'
    # Fresh current-view snapshot must be able to continue.
    fresh=cont.checkpoint(active_execution_id=rec.active_execution_id,observation=ExecutionObservation('fresh-after-conflict'),checkpoint_at='2026-10-02T13:10:03+00:00')
    assert fresh.canonical_step==before+1


def test_v0159_03_true_post_advance_persist_failure_still_terminally_fences(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T13:20:00+00:00')
    before=bridge.episode_step(rec.episode_id)
    original=cont._persist
    monkeypatch.setattr(cont,'_persist',lambda a: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError, match='disk full'):
        cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,
            observation=ExecutionObservation('advance-before-fail'),assessed_at='2026-10-02T13:20:01+00:00')
    monkeypatch.setattr(cont,'_persist',original)
    assert bridge.episode_step(rec.episode_id)==before+1
    row=_latest_intent(store,rec.active_execution_id)
    assert row['status']=='reconciliation_required'
    result=cont.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,
        authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T13:20:02+00:00')
    assert result['outcome']=='terminally_fenced'


@pytest.mark.parametrize('prior_status',['prepared','abandoned','reconciliation_required'])
def test_v0159_04_reconciliation_closes_unchanged_step_regardless_prior_status(tmp_path, prior_status):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T13:30:00+00:00')
    episode=bridge.current_episode(rec.episode_id)
    intent_id=cont._prepare_intent(rec.active_execution_id,episode,snap,'2026-10-02T13:30:01+00:00')
    store._conn.execute('UPDATE continuation_intents SET status=? WHERE intent_id=?',(prior_status,intent_id))
    if prior_status=='abandoned':
        with pytest.raises(ValueError,match='continuation_reconciliation_not_required'):
            cont.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,
                authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T13:30:02+00:00')
    else:
        result=cont.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,
            authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T13:30:02+00:00')
        assert result['outcome']=='reconciled_closed'
    row=store._conn.execute('SELECT status FROM continuation_intents WHERE intent_id=?',(intent_id,)).fetchone()
    assert row['status']=='closed'


def test_v0159_05_direct_runtime_consumption_blocks_late_retry_contract(tmp_path):
    rt,bridge,bindings,ep,auth,store=bridge_setup(tmp_path)
    handle=bridge.resolve_canonical_execution(auth,configuration_id='cfg-A')
    rec=bridge.register_active_execution(store,handle,execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id),registered_at='2026-10-02T13:40:00+00:00')
    rt.invoke_authorized_native(auth,bindings,configuration_id='cfg-A')
    assert rt.native_execution_authorization_status(auth.authorization_id)=='consumed'
    eff=EffectService(store,ObservationService(store))
    with pytest.raises(ValueError, match='retry contract must be pre-execution'):
        eff.register_retry_contract(active_execution_id=rec.active_execution_id,idempotent=True,reconciliation_required=False,registered_at='2026-10-02T13:40:01+00:00')
