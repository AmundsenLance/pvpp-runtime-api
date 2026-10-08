from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
"""Runtime 2.2 v0.153 Phase 12 — required race-matrix hardening."""
import pytest
from pvpp_runtime import ExecutionBindingIdentity, ExecutionObservation
from pvpp_runtime.execution import ExecutionBindingRegistry
from pvpp_runtime.supervision import CanonicalRuntimeBridge, SQLiteSupervisoryStore
from pvpp_runtime.supervision.observation import ObservationService, SourceRegistration, ExternalObservation
from pvpp_runtime.supervision.dependency import DependencyService
from pvpp_runtime.supervision.continuation import ContinuationService
from pvpp_runtime.supervision.control import ControlService, StaleOwner
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.store import ConcurrencyConflict
from test_r22_phase6_control import setup, prepared
from test_r22_phase7_effect import setup7, terminalize
from r22_real_cycle_fixture import new_runtime_and_license


def change(obs, oid, value, effective):
    o=ExternalObservation(oid,'src','reachability','net','sub','cfg',value,None,effective,effective,effective,{})
    obs.submit_observation(o); a=obs.assess_observation(o,assessed_at=effective)
    return obs.commit_admission_change(o,a,committed_at=effective)


def native(tmp_path):
    rt,lic=new_runtime_and_license(); bridge=CanonicalRuntimeBridge(rt)
    action_id=lic.action_ids[0]
    reg=ExecutionBindingRegistry(tuple(rt.registry.actions)); reg.register(ExecutionBindingIdentity('b',action_id,'1'),lambda ctx:'ok')
    ep=bridge.instantiate_execution('ep',lic,entry_sufficient=True,max_steps=5).episode
    auth=bridge.issue_native_execution_authorization(ep,action_id,reg,decision_cycle_id='cy',configuration_id='cfg')
    store=trusted_store(tmp_path/'native.db'); store.register_supervisory_owner_authority(owner_id='A',configuration_id='cfg',registration_authority='test-admin',authority_proof=proof('test-admin'),registered_at='2026-10-02T10:00:00+00:00'); h=bridge.resolve_canonical_execution(auth,configuration_id='cfg')
    rec=bridge.register_active_execution(store,h,execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id),registered_at='2026-10-02T10:00:00+00:00')
    return rt,bridge,store,reg,auth,rec


def test_race01_observation_before_consumption_fences_future_entry(tmp_path):
    rt,bridge,store,reg,auth,rec=native(tmp_path); dep=DependencyService(store); cont=ContinuationService(store,dep,bridge); ctl=ControlService(store,dep,cont,bridge)
    own=ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='A',acquired_at='2026-10-02T10:00:00+00:00')
    ctl.fence_execution_authority(active_execution_id=rec.active_execution_id,owner_id='A',owner_fence=own.owner_fence,reason='admitted material change')
    assert rt.native_execution_authorization_status(auth.authorization_id)=='invalidated'
    with pytest.raises(RuntimeError,match='invalidated'): bridge.invoke_registered_native(store,rec.active_execution_id,auth,reg)


def test_race02_observation_after_consumption_never_retroactively_unconsumes(tmp_path):
    rt,bridge,store,reg,auth,rec=native(tmp_path)
    assert bridge.invoke_registered_native(store,rec.active_execution_id,auth,reg,configuration_id='cfg').status=='succeeded'
    assert rt.native_execution_authorization_status(auth.authorization_id)=='consumed'
    dep=DependencyService(store); cont=ContinuationService(store,dep,bridge); ctl=ControlService(store,dep,cont,bridge)
    own=ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='A',acquired_at='2026-10-02T10:00:00+00:00')
    assert ctl.fence_execution_authority(active_execution_id=rec.active_execution_id,owner_id='A',owner_fence=own.owner_fence,reason='late change')==()
    assert rt.native_execution_authorization_status(auth.authorization_id)=='consumed'


def test_race03_material_change_during_checkpoint_invalidates_old_snapshot(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path); snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    change(obs,'r3','down','2026-10-02T11:00:00')
    with pytest.raises(ConcurrencyConflict): cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('r3-e'),assessed_at='2026-10-02T10:00:00+00:00')


def test_race04_observation_after_assessment_does_not_rewrite_committed_assessment(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,a,reg=prepared(tmp_path); posture=a.continuation_posture
    change(obs,'r4','changed','2026-10-02T11:00:00')
    assert a.continuation_posture==posture
    with pytest.raises(ConcurrencyConflict): ctl.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')


def test_race05_observation_after_control_request_preserves_request_history(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,a,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    change(obs,'r5','changed','2026-10-02T11:00:00')
    assert req.requested_control=='cancel' and req.target_handle=='job:1'


def test_race06_enforcement_ack_before_effect_does_not_close_world_effect(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path); own=store.current_supervisory_ownership(rec.active_execution_id); a=next(iter(ctl.continuation._assessments.values()))
    regid=store._conn.execute('SELECT adapter_registration_id FROM adapter_registrations ORDER BY rowid DESC LIMIT 1').fetchone()['adapter_registration_id']
    req=ctl.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own['owner_id'],owner_fence=own['owner_fence'],requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    at=ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=regid,owner_id=own['owner_id'],owner_fence=own['owner_fence'],target_handle='job:1',control_region_at_request='cancelable',capability_evidence_ref='cap',mapping_identity='m',dispatched_at='2026-10-02T10:00:00+00:00')
    ctl.record_enforcement_outcome(control_attempt_id=at.control_attempt_id,outcome='completed',attestation_evidence='signed:controller',controller_evidence_ref='ack',observed_control_region='stopped',recorded_at='2026-10-02T10:00:00+00:00')
    assert eff.current_effect_state(rec.active_execution_id).state=='open'


def test_race07_effect_before_enforcement_ack_is_independently_reconciled(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path)
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='b',evidence_ref='world-first',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    s=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00')
    assert s.state=='completed_effect' and not s.unresolved


def test_race08_late_effect_after_canonical_finality_reconciles_forward(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path); term=terminalize(ctl,rec); f=eff.accept_canonical_finality(active_execution_id=rec.active_execution_id,continuation_assessment_id=term.assessment_id,terminalized_at='2026-10-02T10:00:00+00:00')
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='b',evidence_ref='late',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    s=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00')
    assert s.canonical_finality_ref==f.canonical_finality_id and eff.get_canonical_finality(rec.active_execution_id)==f


def test_race09_layer1_waits_for_host_authoritative_transition(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path)
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='b',evidence_ref='e',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    s=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ValueError,match='host-authoritative'): eff.record_layer1_transition(active_execution_id=rec.active_execution_id,effect_reconciliation_ref=s.effect_record_id,prior_actual_state_ref='a',next_actual_state_ref='b',transition_time='2026-10-02T10:00:00+00:00',evidence_ref='h',provenance='host',configuration_id='cfg',authority_evidence='bad')


def test_race10_duplicate_observation_is_idempotent(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path); before=obs.observation_count()
    o=ExternalObservation('dup','src','reachability','net','sub','cfg','up2',None,'2026-10-02T11:00:00','x2','x2',{})
    obs.submit_observation(o); obs.submit_observation(o)
    assert obs.observation_count()==before+1


def test_race11_out_of_order_observation_does_not_displace_newer_view(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path); change(obs,'new','new','2026-10-02T12:00:00'); change(obs,'old','old','2026-10-02T11:00:00')
    v=obs.read_current_fact_view(configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net')
    assert v.value=='new'


def test_race12_stale_owner_cannot_commit_control_after_fence_advance(tmp_path):
    *_,ctl,rec,own,a,reg=prepared(tmp_path); ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='B',acquired_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(StaleOwner): ctl.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
