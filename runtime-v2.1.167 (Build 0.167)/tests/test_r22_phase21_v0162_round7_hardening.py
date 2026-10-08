from __future__ import annotations

import threading
import time
from collections.abc import Mapping

import pytest

from pvpp_runtime import ExecutionObservation, ExecutionBindingIdentity
from pvpp_runtime.execution import ExecutionBindingRegistry
from pvpp_runtime.supervision import CanonicalRuntimeBridge
from pvpp_runtime.supervision.continuation import ContinuationService, ContinuationReconciliationRequired
from pvpp_runtime.supervision.dependency import DependencyService
from pvpp_runtime.supervision.observation import ObservationService, SourceRegistration, ExternalObservation
from pvpp_runtime.supervision.store import ConcurrencyConflict
from r22_real_cycle_fixture import new_runtime_and_license
from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
from test_r22_phase6_control import prepared


def _open_intents(store, aeid):
    return store._conn.execute(
        "SELECT status FROM continuation_intents WHERE active_execution_id=? AND status IN ('prepared','reconciliation_required','terminally_fenced') ORDER BY rowid",
        (aeid,),
    ).fetchall()


@pytest.mark.parametrize(
    "observation",
    [
        ExecutionObservation('bad-bundle-int', staged=True, realized_pv_bundle=5),
        ExecutionObservation('bad-info-int', staged=True, information=5),
        ExecutionObservation('bad-bundle-list', staged=True, realized_pv_bundle=[1, 2]),
        ExecutionObservation('bad-flag', staged=1),
    ],
)
def test_v0162_01_pre_mutation_observation_validation_does_not_fence(tmp_path, observation):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    before=bridge.episode_step(rec.episode_id)
    with pytest.raises((TypeError, ValueError)):
        cont.checkpoint(active_execution_id=rec.active_execution_id,observation=observation,checkpoint_at='2026-10-02T15:00:00+00:00')
    assert bridge.episode_step(rec.episode_id)==before
    assert not bridge.episode_is_indeterminate(rec.episode_id)
    assert _open_intents(store,rec.active_execution_id)==[]
    fresh=cont.checkpoint(active_execution_id=rec.active_execution_id,observation=ExecutionObservation('good-after-bad',staged=True),checkpoint_at='2026-10-02T15:00:01+00:00')
    assert fresh.canonical_step==before+1


def test_v0162_02_two_service_lost_update_cannot_reopen_closed_intent(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    store2=trusted_store(tmp_path/'s.db')
    dep2=DependencyService(store2)
    cont2=ContinuationService(store2,dep2,bridge)
    snap2=dep2.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T15:10:00+00:00')

    paused=threading.Event(); release=threading.Event()
    real_persist=cont._persist
    def pause_after_advance(a):
        paused.set()
        assert release.wait(5)
        return real_persist(a)
    monkeypatch.setattr(cont,'_persist',pause_after_advance)

    a_result=[]; a_error=[]; b_error=[]
    def run_a():
        try:
            a_result.append(cont.checkpoint(active_execution_id=rec.active_execution_id,
                observation=ExecutionObservation('A-step',staged=True),checkpoint_at='2026-10-02T15:10:01+00:00'))
        except Exception as exc:a_error.append(exc)
    def run_b():
        try:
            cont2.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap2,
                observation=ExecutionObservation('B-step',staged=True),assessed_at='2026-10-02T15:10:01+00:00')
        except Exception as exc:b_error.append(exc)

    ta=threading.Thread(target=run_a); ta.start(); assert paused.wait(5)
    tb=threading.Thread(target=run_b); tb.start()
    time.sleep(0.05)
    # The hardened path may fail-fast with a retryable concurrency conflict or wait
    # on the write boundary. Both are valid; neither may mutate A's intent.
    release.set(); ta.join(5); tb.join(5)
    assert not a_error and a_result and a_result[0].canonical_step==1
    assert b_error, 'concurrent stale checkpoint must be rejected/retried, not silently advance'
    assert any(k in str(b_error[0]) for k in ('snapshot_conflict','concurrency','retry'))
    row=store._conn.execute("SELECT status FROM continuation_intents WHERE active_execution_id=? ORDER BY rowid DESC LIMIT 1",(rec.active_execution_id,)).fetchone()
    assert row['status']=='closed'
    assert _open_intents(store,rec.active_execution_id)==[]
    fresh=cont.checkpoint(active_execution_id=rec.active_execution_id,observation=ExecutionObservation('after-race',staged=True),checkpoint_at='2026-10-02T15:10:02+00:00')
    assert fresh.canonical_step==2
    store2.close()


def _long_running_services(tmp_path):
    rt,lic=new_runtime_and_license(); bridge=CanonicalRuntimeBridge(rt)
    action_id=lic.action_ids[0]
    bindings=ExecutionBindingRegistry(tuple(rt.registry.actions))
    bindings.register(ExecutionBindingIdentity('b-long',action_id,'1'),lambda ctx:'ok')
    ep=bridge.instantiate_execution('ep-long',lic,entry_sufficient=True,max_steps=80).episode
    auth=bridge.issue_native_execution_authorization(ep,action_id,bindings,decision_cycle_id='cy-long',configuration_id='cfg')
    store=trusted_store(tmp_path/'stress.db'); handle=bridge.resolve_canonical_execution(auth,configuration_id='cfg')
    rec=bridge.register_active_execution(store,handle,execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id),registered_at='2026-10-02T15:20:00+00:00')
    obs=ObservationService(store); dep=DependencyService(store); cont=ContinuationService(store,dep,bridge)
    src=SourceRegistration('sr-long','src',('observation',),('reachability',),('sub',),('cfg',),('governance',),'att',None,None,'current','admin',1)
    register_test_source(obs,src)
    o=ExternalObservation('o-long','src','reachability','net','sub','cfg','up',None,'2026-10-02T15:20:00+00:00','2026-10-02T15:20:00+00:00','2026-10-02T15:20:00+00:00',{})
    obs.submit_observation(o); adm=obs.assess_observation(o,assessed_at='2026-10-02T15:20:00+00:00'); obs.commit_admission_change(o,adm,committed_at='2026-10-02T15:20:00+00:00')
    dep.register_dependency_binding(active_execution_id=rec.active_execution_id,configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T15:20:00+00:00')
    store2=trusted_store(tmp_path/'stress.db'); dep2=DependencyService(store2); cont2=ContinuationService(store2,dep2,bridge)
    return bridge,store,dep,cont,store2,dep2,cont2,rec


def test_v0162_03_two_connection_stress_has_no_false_fence_or_duplicate_steps(tmp_path):
    # >=20 repeated schedules; each has two services making 15 successful checkpoint attempts total.
    # A retryable concurrency conflict is acceptable; persistent reconciliation residue is not.
    for round_no in range(20):
        sub=tmp_path/f'r{round_no}'; sub.mkdir()
        bridge,store,dep,cont,store2,dep2,cont2,rec=_long_running_services(sub)
        successes=[]; failures=[]; lock=threading.Lock()
        target_per_worker=15
        def worker(label,svc):
            n=0; attempts=0
            while n<target_per_worker and attempts<300:
                attempts+=1
                try:
                    a=svc.checkpoint(active_execution_id=rec.active_execution_id,
                        observation=ExecutionObservation(f'{label}-{round_no}-{attempts}',staged=True),
                        checkpoint_at=f'2026-10-02T15:{30+round_no%20:02d}:{attempts%60:02d}+00:00')
                    with lock: successes.append(a.canonical_step)
                    n+=1
                except (ConcurrencyConflict,ContinuationReconciliationRequired) as exc:
                    with lock: failures.append(str(exc))
                    time.sleep(0.001)
        t1=threading.Thread(target=worker,args=('A',cont)); t2=threading.Thread(target=worker,args=('B',cont2))
        t1.start(); t2.start(); t1.join(15); t2.join(15)
        assert not t1.is_alive() and not t2.is_alive()
        assert len(successes)==30
        assert len(set(successes))==30
        assert sorted(successes)==list(range(1,31))
        residue=store._conn.execute("SELECT status FROM continuation_intents WHERE active_execution_id=? AND status IN ('reconciliation_required','terminally_fenced')",(rec.active_execution_id,)).fetchall()
        assert residue==[]
        store2.close(); store.close()
