from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
import pytest
from test_r22_phase7_effect import setup7
from pvpp_runtime.supervision.recovery import RecoveryService
from pvpp_runtime.supervision.dependency import DependencyService
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.observation import ObservationService
from pvpp_runtime.supervision.store import SQLiteSupervisoryStore, ConcurrencyConflict

def prep(tmp_path,effect=False,live=False):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path); dep=DependencyService(store); svc=RecoveryService(store,dep,eff)
    store.register_supervisory_owner_authority(owner_id='B',configuration_id='cfg',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    store.register_supervisory_owner_authority(owner_id='C',configuration_id='cfg',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    p=svc.register_recovery_profile(active_execution_id=rec.active_execution_id,required_control_reconciliation=True,required_effect_evidence=True,required_world_layer1_checks=True,registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    state=None
    if live:
        own=store.current_supervisory_ownership(rec.active_execution_id)
        assessment=next(iter(ctl.continuation._assessments.values()))
        regid=store._conn.execute('SELECT adapter_registration_id FROM adapter_registrations ORDER BY rowid DESC LIMIT 1').fetchone()['adapter_registration_id']
        req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own['owner_id'],owner_fence=own['owner_fence'],requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
        attempt=ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=regid,owner_id=own['owner_id'],owner_fence=own['owner_fence'],target_handle='job:1',control_region_at_request='cancelable',capability_evidence_ref='cap',mapping_identity='cancel=cancel',dispatched_at='2026-10-02T10:00:00+00:00')
        ctl.record_enforcement_outcome(control_attempt_id=attempt.control_attempt_id,outcome='completed',attestation_evidence='signed:controller',controller_evidence_ref='controller',observed_control_region='stopped',recorded_at='2026-10-02T10:00:00+00:00')
    if effect or live:
        e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='no_material_effect_evidenced',realized_bundle_ref=None,evidence_ref='ledger',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
        state=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00')
    if live:
        eff.record_layer1_transition(active_execution_id=rec.active_execution_id,effect_reconciliation_ref=state.effect_record_id,prior_actual_state_ref='before',next_actual_state_ref='after',transition_time='2026-10-02T10:00:00+00:00',evidence_ref='world',provenance='host',configuration_id='cfg',authority_evidence='signed:layer1')
    return store,obs,dep,eff,svc,rec,p

def test_recovery_profile_required(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path); svc=RecoveryService(store,DependencyService(store),eff)
    with pytest.raises(ValueError,match='recovery_profile_missing'): svc.begin_recovery(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00')

def test_profile_cannot_be_weakened_after_registration(tmp_path):
    *_,svc,rec,p=prep(tmp_path)
    with pytest.raises(PermissionError): svc.register_recovery_profile(active_execution_id=rec.active_execution_id,required_control_reconciliation=False,required_effect_evidence=False,required_world_layer1_checks=False,registration_authority='recovering-owner',registered_at='2026-10-02T10:00:00+00:00')

def test_begin_recovery_advances_fence_and_starts_fenced(tmp_path):
    store,obs,dep,eff,svc,rec,p=prep(tmp_path); before=store.current_supervisory_ownership(rec.active_execution_id)
    rr=svc.begin_recovery(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00')
    assert rr.owner_fence>before['owner_fence'] and rr.recovery_state=='recovering' and not rr.control_resumption_allowed

def test_claimed_effect_cannot_replace_authoritative_effect_evidence(tmp_path):
    store,obs,dep,eff,svc,rec,p=prep(tmp_path); rr=svc.begin_recovery(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00')
    x=svc.reconcile_recovery(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence,external_control_status='reconciled',effect_status='no_material_effect_evidenced',layer1_world_state_status='reconciled')
    assert x.recovery_state=='unresolved' and dict(x.requirement_results)['effect'] is False

def test_live_reconciliation_can_satisfy_profile(tmp_path):
    store,obs,dep,eff,svc,rec,p=prep(tmp_path,live=True); rr=svc.begin_recovery(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00')
    x=svc.reconcile_recovery(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence,external_control_status='reconciled',effect_status='no_material_effect_evidenced',layer1_world_state_status='reconciled',evidence_refs=('controller','ledger','world'))
    assert x.recovery_state=='reconciled' and not x.control_resumption_allowed

def test_fresh_snapshot_required_before_completion(tmp_path):
    store,obs,dep,eff,svc,rec,p=prep(tmp_path,live=True); rr=svc.begin_recovery(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00'); svc.reconcile_recovery(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence,external_control_status='reconciled',effect_status='no_material_effect_evidenced',layer1_world_state_status='reconciled')
    with pytest.raises(ValueError,match='fresh snapshot'): svc.complete_recovery(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence,completed_at='2026-10-02T10:00:00+00:00')

def test_fresh_snapshot_allows_completion(tmp_path):
    store,obs,dep,eff,svc,rec,p=prep(tmp_path,live=True); rr=svc.begin_recovery(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00'); svc.reconcile_recovery(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence,external_control_status='reconciled',effect_status='no_material_effect_evidenced',layer1_world_state_status='reconciled'); svc.capture_recovery_snapshot(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence,created_at='2026-10-02T10:00:00+00:00')
    done=svc.complete_recovery(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence,completed_at='2026-10-02T10:00:00+00:00'); assert done.control_resumption_allowed

def test_snapshot_staleness_blocks_completion(tmp_path):
    store,obs,dep,eff,svc,rec,p=prep(tmp_path,live=True); rr=svc.begin_recovery(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00'); svc.reconcile_recovery(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence,external_control_status='reconciled',effect_status='no_material_effect_evidenced',layer1_world_state_status='reconciled'); svc.capture_recovery_snapshot(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence,created_at='2026-10-02T10:00:00+00:00'); dep.register_dependency_binding(active_execution_id=rec.active_execution_id,configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='extra',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ConcurrencyConflict): svc.complete_recovery(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence,completed_at='2026-10-02T10:00:00+00:00')

def test_stale_owner_cannot_reconcile_or_resume(tmp_path):
    store,obs,dep,eff,svc,rec,p=prep(tmp_path,True); rr=svc.begin_recovery(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00'); store.register_supervisory_owner_authority(owner_id='C',configuration_id='cfg',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00'); store.acquire_supervisory_ownership(active_execution_id=rec.active_execution_id,owner_id='C',acquired_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(PermissionError,match='stale_owner'): svc.reconcile_recovery(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence,external_control_status='reconciled',effect_status='no_material_effect_evidenced',layer1_world_state_status='reconciled')

def test_replay_or_history_alone_never_authorizes_resumption(tmp_path):
    store,obs,dep,eff,svc,rec,p=prep(tmp_path,True); rr=svc.begin_recovery(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00',provenance='replay-package')
    with pytest.raises(ValueError,match='recovery_requirement_unsatisfied'): svc.assert_resumption_allowed(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence)
