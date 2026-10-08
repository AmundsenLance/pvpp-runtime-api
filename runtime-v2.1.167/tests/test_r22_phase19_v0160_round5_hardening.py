from __future__ import annotations

import threading
import pytest

from pvpp_runtime import ExecutionObservation, ExecutionBindingIdentity
from pvpp_runtime.execution import ExecutionBindingRegistry
from pvpp_runtime.supervision import CanonicalRuntimeBridge
from pvpp_runtime.supervision.continuation import ContinuationService
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.observation import ObservationService, ExternalObservation
from r22_real_cycle_fixture import new_runtime_and_license
from r22_trust_fixture import trusted_store, proof
from test_r22_phase6_control import prepared
from test_r3_phase2_canonical_bridge import setup as bridge_setup


def _latest_intent(store, active_execution_id):
    return store._conn.execute(
        "SELECT * FROM continuation_intents WHERE active_execution_id=? ORDER BY rowid DESC LIMIT 1",
        (active_execution_id,),
    ).fetchone()


def test_v0160_01_late_reconcile_after_abandon_then_success_is_not_required(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T14:00:00+00:00')
    original=bridge.authorize_supervised_advance
    monkeypatch.setattr(bridge,'authorize_supervised_advance',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('transient')))
    with pytest.raises(RuntimeError,match='transient'):
        cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,
            observation=ExecutionObservation('first'),assessed_at='2026-10-02T14:00:01+00:00')
    monkeypatch.setattr(bridge,'authorize_supervised_advance',original)
    assert _latest_intent(store,rec.active_execution_id)['status']=='abandoned'
    fresh=cont.checkpoint(active_execution_id=rec.active_execution_id,observation=ExecutionObservation('second'),checkpoint_at='2026-10-02T14:00:02+00:00')
    assert fresh.canonical_step==1
    with pytest.raises(ValueError,match='continuation_reconciliation_not_required'):
        cont.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T14:00:03+00:00')
    assert not store.continuation_reconciliation_required(rec.active_execution_id)


def test_v0160_02_threaded_conflict_then_success_late_reconcile_is_not_required(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T14:10:00+00:00')
    prepared_evt=threading.Event(); changed_evt=threading.Event(); original_prepare=cont._prepare_intent
    def pause_after_prepare(*args,**kwargs):
        iid=original_prepare(*args,**kwargs); prepared_evt.set(); assert changed_evt.wait(5); return iid
    monkeypatch.setattr(cont,'_prepare_intent',pause_after_prepare)
    errors=[]
    def worker():
        try:
            cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,
                observation=ExecutionObservation('conflict'),assessed_at='2026-10-02T14:10:01+00:00')
        except Exception as exc: errors.append(exc)
    th=threading.Thread(target=worker); th.start(); assert prepared_evt.wait(5)
    store2=trusted_store(tmp_path/'s.db'); obs2=ObservationService(store2)
    o=ExternalObservation('o-v160','src','reachability','net','sub','cfg','down',None,
        '2026-10-02T14:10:01+00:00','2026-10-02T14:10:01+00:00','2026-10-02T14:10:01+00:00',{})
    obs2.submit_observation(o); a=obs2.assess_observation(o,assessed_at='2026-10-02T14:10:01+00:00')
    obs2.commit_admission_change(o,a,committed_at='2026-10-02T14:10:01+00:00'); store2.close(); changed_evt.set(); th.join(5)
    assert errors and 'snapshot_conflict' in str(errors[0])
    monkeypatch.setattr(cont,'_prepare_intent',original_prepare)
    assert _latest_intent(store,rec.active_execution_id)['status']=='abandoned'
    fresh=cont.checkpoint(active_execution_id=rec.active_execution_id,observation=ExecutionObservation('fresh'),checkpoint_at='2026-10-02T14:10:02+00:00')
    assert fresh.canonical_step==1
    with pytest.raises(ValueError,match='continuation_reconciliation_not_required'):
        cont.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T14:10:03+00:00')


def test_v0160_03_raise_after_runtime_advance_marks_indeterminate_and_fences(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T14:20:00+00:00')
    before=bridge.episode_step(rec.episode_id); real=rt.advance_execution; observed=[]
    def advance_then_raise(*args,**kwargs):
        result=real(*args,**kwargs); observed.append(result.episode.step_count); raise RuntimeError('post-advance transport fault')
    monkeypatch.setattr(rt,'advance_execution',advance_then_raise)
    with pytest.raises(RuntimeError,match='post-advance transport fault'):
        cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,
            observation=ExecutionObservation('indeterminate'),assessed_at='2026-10-02T14:20:01+00:00')
    assert observed==[before+1]
    row=_latest_intent(store,rec.active_execution_id)
    assert row['status']=='reconciliation_required'
    assert bridge.episode_is_indeterminate(rec.episode_id)
    with pytest.raises(Exception,match='continuation_reconciliation_required'):
        cont.checkpoint(active_execution_id=rec.active_execution_id,observation=ExecutionObservation('blocked'),checkpoint_at='2026-10-02T14:20:02+00:00')
    with pytest.raises(Exception,match='indeterminate'):
        bridge.advance_execution(bridge.episode_state(rec.episode_id),ExecutionObservation('direct-blocked'))
    result=cont.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,
        authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T14:20:03+00:00')
    assert result['outcome']=='terminally_fenced'


def test_v0160_04_reopened_store_fails_closed_when_canonical_status_unavailable(tmp_path):
    rt,bridge,bindings,ep,auth,store=bridge_setup(tmp_path)
    handle=bridge.resolve_canonical_execution(auth,configuration_id='cfg-A')
    rec=bridge.register_active_execution(store,handle,execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id),registered_at='2026-10-02T14:30:00+00:00')
    rt.invoke_authorized_native(auth,bindings,configuration_id='cfg-A')
    assert rt.native_execution_authorization_status(auth.authorization_id)=='consumed'
    store2=trusted_store(tmp_path/'supervisor.db')
    eff=EffectService(store2,ObservationService(store2))
    with pytest.raises(ValueError,match='canonical authorization status unavailable|retry contract must be pre-execution'):
        eff.register_retry_contract(active_execution_id=rec.active_execution_id,idempotent=True,reconciliation_required=False,registered_at='2026-10-02T14:30:01+00:00')
    store2.close(); store.close()


def _register_runtime_on_store(store, label):
    rt,lic=new_runtime_and_license(); bridge=CanonicalRuntimeBridge(rt); action=lic.action_ids[0]
    bindings=ExecutionBindingRegistry(tuple(rt.registry.actions)); bindings.register(ExecutionBindingIdentity(f'b-{label}',action,'1'),lambda ctx:'ok')
    ep=bridge.instantiate_execution(f'ep-{label}',lic,entry_sufficient=True,max_steps=2).episode
    auth=bridge.issue_native_execution_authorization(ep,action,bindings,decision_cycle_id=f'cy-{label}',configuration_id='cfg')
    handle=bridge.resolve_canonical_execution(auth,configuration_id='cfg')
    rec=bridge.register_active_execution(store,handle,execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id),registered_at='2026-10-02T14:40:00+00:00')
    return rt,bridge,bindings,auth,rec


def test_v0160_05_two_runtime_bridge_bindings_are_per_execution_and_retry_fails_closed(tmp_path):
    store=trusted_store(tmp_path/'shared.db')
    rt1,b1,bindings1,auth1,rec1=_register_runtime_on_store(store,'one')
    rt2,b2,bindings2,auth2,rec2=_register_runtime_on_store(store,'two')
    rt1.invoke_authorized_native(auth1,bindings1,configuration_id='cfg')
    assert rt1.native_execution_authorization_status(auth1.authorization_id)=='consumed'
    assert store.canonical_authorization_status(rec1.active_execution_id)=='consumed'
    assert store.canonical_authorization_status(rec2.active_execution_id)=='issued'
    eff=EffectService(store,ObservationService(store))
    with pytest.raises(ValueError,match='retry contract must be pre-execution'):
        eff.register_retry_contract(active_execution_id=rec1.active_execution_id,idempotent=True,reconciliation_required=False,registered_at='2026-10-02T14:40:01+00:00')
    store.close()
