from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
import pytest
from datetime import datetime, timezone

from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision.control import ControlService, TargetScopeViolation
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.observation import ObservationService
from test_r22_phase6_control import prepared, setup


def test_v0157_01_lease_expiry_uses_trusted_clock_not_caller_timestamp(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    ctl.register_supervisory_owner(owner_id='lease-owner',configuration_id='cfg',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-09-01T00:00:00+00:00')
    # Acquire while the host clock says the lease is still live, then advance only the trusted clock.
    store.trust._clock=lambda: datetime(2026,9,1,12,0,0,tzinfo=timezone.utc)
    lease=ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='lease-owner',acquired_at='2026-09-01T00:00:00+00:00',expires_at='2026-09-02T00:00:00+00:00')
    store.trust._clock=lambda: datetime(2026,10,2,12,0,0,tzinfo=timezone.utc)
    # Backdating a request must not revive an already-expired lease.
    with pytest.raises(Exception, match='expired|stale_owner'):
        ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,
            owner_id=lease.owner_id,owner_fence=lease.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-09-01T12:00:00+00:00')
    # Unparseable audit time must fail rather than disable expiry checks.
    with pytest.raises((ValueError, Exception), match='time|timestamp|expired|stale_owner'):
        ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,
            owner_id=lease.owner_id,owner_fence=lease.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')


def test_v0157_02_retry_contract_cannot_be_added_after_dispatch(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,
        owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,
        owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='cancelable',
        capability_evidence_ref='cap',mapping_identity='m1',dispatched_at='2026-10-02T10:00:01+00:00')
    eff=EffectService(store,obs)
    with pytest.raises(Exception, match='pre.*execution|pre.*dispatch|retry.*contract|already.*dispatch|uncertain'):
        eff.register_retry_contract(active_execution_id=rec.active_execution_id,idempotent=True,reconciliation_required=True,registered_at='2026-10-02T10:00:02+00:00')


def test_v0157_03_registration_authority_cannot_self_bootstrap(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path)
    ctl=ControlService(store,dep,cont,bridge)
    with pytest.raises(PermissionError, match='root|authority|trusted'):
        ctl.register_supervisory_owner(owner_id='mallory',configuration_id='cfg',registration_authority='mallory',registered_at='2026-10-02T10:00:00+00:00')


def test_v0157_04_persist_failure_marks_continuation_reconciliation_required(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    before=bridge.current_episode(rec.episode_id).step_count
    original=cont._persist
    calls={'n':0}
    def fail_once(a):
        calls['n']+=1
        if calls['n']==1:
            raise OSError('disk full')
        return original(a)
    monkeypatch.setattr(cont,'_persist',fail_once)
    with pytest.raises(OSError, match='disk full'):
        cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,
            observation=ExecutionObservation('go'),assessed_at='2026-10-02T10:00:01+00:00')
    assert bridge.current_episode(rec.episode_id).step_count==before+1
    with pytest.raises(Exception, match='reconciliation|divergence|intent'):
        cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,
            observation=ExecutionObservation('go-again'),assessed_at='2026-10-02T10:00:02+00:00')


def test_v0157_05_target_suffix_rejects_wildcards_and_path_syntax(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    with pytest.raises(TargetScopeViolation):
        ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,
            owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:*',created_at='2026-10-02T10:00:00+00:00')


def test_v0157_06_vendor_command_binding_records_real_command_without_widening(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,_=prepared(tmp_path)
    reg=ctl.register_adapter(adapter_id='posix',configuration_id='cfg',target_handle_namespace='job:',
        supported_semantic_controls=('pause',),command_mapping={'pause':'pause'},vendor_command_mapping={'pause':'SIGSTOP'},
        controller_attestation_method='signed',control_region_evidence_method='state',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    # Need a pause-compatible assessment; reauthorization_required permits pause.
    req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,
        owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='pause',target_handle='job:1',created_at='2026-10-02T10:00:01+00:00')
    at=ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,
        owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='pauseable',
        capability_evidence_ref='cap',mapping_identity='posix-v1',dispatched_at='2026-10-02T10:00:02+00:00')
    assert at.mapped_command=='SIGSTOP'


def test_v0157_07_continue_posture_remains_non_authorizing_for_control(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path)
    ctl=ControlService(store,dep,cont,bridge)
    ctl.register_supervisory_owner(owner_id='owner-A',configuration_id='cfg',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    own=ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='owner-A',acquired_at='2026-10-02T10:00:00+00:00')
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:01+00:00')
    a=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('continue'),assessed_at='2026-10-02T10:00:02+00:00')
    assert a.continuation_posture=='continue'
    with pytest.raises(ValueError, match='posture'):
        ctl.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,
            owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='pause',target_handle='job:1',created_at='2026-10-02T10:00:03+00:00')


def test_v0157_08_caller_boolean_cannot_verify_controller_attestation(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,
        owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    at=ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,
        owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='cancelable',
        capability_evidence_ref='cap',mapping_identity='m1',dispatched_at='2026-10-02T10:00:01+00:00')
    e=ctl.record_enforcement_outcome(control_attempt_id=at.control_attempt_id,outcome='completed',attestation_verified=True,
        controller_evidence_ref='ack',observed_control_region='stopped',recorded_at='2026-10-02T10:00:02+00:00')
    assert e.attestation_status=='unverified'
    v=ctl.record_enforcement_outcome(control_attempt_id=at.control_attempt_id,outcome='completed',attestation_evidence='signed:controller',
        controller_evidence_ref='ack2',observed_control_region='stopped',recorded_at='2026-10-02T10:00:03+00:00')
    assert v.attestation_status=='verified'


def test_v0157_09_caller_boolean_cannot_create_layer1_authority(tmp_path):
    from test_r22_phase7_effect import setup7
    *_,rec,eff=setup7(tmp_path)
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',
        state='completed_effect',realized_bundle_ref='bundle',evidence_ref='e',provenance='p',observed_at='2026-10-02T10:00:00+00:00',
        effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    st=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:01+00:00')
    with pytest.raises(ValueError, match='verified host-authoritative'):
        eff.record_layer1_transition(active_execution_id=rec.active_execution_id,effect_reconciliation_ref=st.effect_record_id,
            prior_actual_state_ref='a',next_actual_state_ref='b',transition_time='2026-10-02T10:00:02+00:00',evidence_ref='h',provenance='host',
            configuration_id='cfg',host_authoritative=True)
    x=eff.record_layer1_transition(active_execution_id=rec.active_execution_id,effect_reconciliation_ref=st.effect_record_id,
        prior_actual_state_ref='a',next_actual_state_ref='b',transition_time='2026-10-02T10:00:03+00:00',evidence_ref='h2',provenance='host',
        configuration_id='cfg',authority_evidence='signed:layer1')
    assert x.next_actual_state_ref=='b'


def test_v0157_10_source_registration_requires_host_root_proof(tmp_path):
    from pvpp_runtime.supervision.observation import SourceRegistration
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path)
    bad=SourceRegistration('mallory-src-reg','mallory-src',('observation',),('reachability',),('sub',),('cfg',),('governance',),'self',None,None,'current','mallory',1)
    with pytest.raises(PermissionError, match='trusted registration authority'):
        obs.register_source(bad, authority_proof='mallory')


def test_v0157_11_retry_contract_cannot_be_added_after_supervised_native_invocation(tmp_path):
    from test_r3_phase2_canonical_bridge import setup as bridge_setup
    rt,bridge,bindings,ep,auth,store=bridge_setup(tmp_path)
    handle=bridge.resolve_canonical_execution(auth,configuration_id='cfg-A')
    rec=bridge.register_active_execution(store,handle,execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id),registered_at='2026-10-02T10:00:00+00:00')
    bridge.invoke_registered_native(store,rec.active_execution_id,auth,bindings,configuration_id='cfg-A')
    obs=ObservationService(store); eff=EffectService(store,obs)
    with pytest.raises(ValueError, match='pre-execution|pre-dispatch|uncertain'):
        eff.register_retry_contract(active_execution_id=rec.active_execution_id,idempotent=True,reconciliation_required=True,registered_at='2026-10-02T10:00:01+00:00')


def test_v0157_12_recovery_profile_requires_host_root_proof(tmp_path):
    from pvpp_runtime.supervision.recovery import RecoveryService
    from test_r22_phase7_effect import setup7
    rt,store,obs,ctl,rec,eff=setup7(tmp_path)
    svc=RecoveryService(store,ctl.dependencies,eff)
    with pytest.raises(PermissionError, match='trusted registration authority'):
        svc.register_recovery_profile(active_execution_id=rec.active_execution_id,required_control_reconciliation=True,
            required_effect_evidence=True,required_world_layer1_checks=True,registration_authority='mallory',registered_at='2026-10-02T10:00:00+00:00',authority_proof='mallory')
