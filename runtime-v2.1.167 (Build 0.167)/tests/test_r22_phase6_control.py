from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
import pytest
from pvpp_runtime import ExecutionObservation
from pvpp_runtime.models import GovernanceInvalidationSignal
from pvpp_runtime.supervision.control import ControlService, StaleOwner, ControlMappingWidened, TargetScopeViolation
from pvpp_runtime.supervision.store import ConcurrencyConflict
from pvpp_runtime import ExecutionBindingIdentity
from pvpp_runtime.execution import ExecutionBindingRegistry
from pvpp_runtime.supervision import CanonicalRuntimeBridge, SQLiteSupervisoryStore
from pvpp_runtime.supervision.observation import ObservationService, SourceRegistration, ExternalObservation
from pvpp_runtime.supervision.dependency import DependencyService
from pvpp_runtime.supervision.continuation import ContinuationService
from r22_real_cycle_fixture import new_runtime_and_license

def setup(tmp_path):
    rt,lic=new_runtime_and_license(); bridge=CanonicalRuntimeBridge(rt)
    action_id=lic.action_ids[0]
    reg=ExecutionBindingRegistry(tuple(rt.registry.actions)); reg.register(ExecutionBindingIdentity('b',action_id,'1'),lambda ctx:'ok')
    ep=bridge.instantiate_execution('ep',lic,entry_sufficient=True,max_steps=5).episode
    auth=bridge.issue_native_execution_authorization(ep,action_id,reg,decision_cycle_id='cy',configuration_id='cfg')
    store=trusted_store(tmp_path/'s.db'); handle=bridge.resolve_canonical_execution(auth,configuration_id='cfg')
    for owner in ('owner-A','owner-B','A','B','C'):
        store.register_supervisory_owner_authority(owner_id=owner,configuration_id='cfg',registration_authority='test-admin',authority_proof=proof('test-admin'),registered_at='2026-10-02T10:00:00+00:00')
    rec=bridge.register_active_execution(store,handle,execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id),registered_at='2026-10-02T10:00:00+00:00')
    obs=ObservationService(store); dep=DependencyService(store); cont=ContinuationService(store,dep,bridge)
    src=SourceRegistration('sr','src',('observation',),('reachability',),('sub',),('cfg',),('governance',),'att',None,None,'current','admin',1); register_test_source(obs, src)
    o=ExternalObservation('o1','src','reachability','net','sub','cfg','up',None,'2026-10-02T10:00:00','x','x',{}); obs.submit_observation(o); a=obs.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00'); obs.commit_admission_change(o,a,committed_at='2026-10-02T10:00:00+00:00')
    dep.register_dependency_binding(active_execution_id=rec.active_execution_id,configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00')
    return rt,bridge,store,obs,dep,cont,rec


def prepared(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path)
    ctl=ControlService(store,dep,cont,bridge)
    ctl.register_supervisory_owner(owner_id='owner-A',configuration_id='cfg',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    ctl.register_supervisory_owner(owner_id='owner-B',configuration_id='cfg',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    own=ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='owner-A',acquired_at='2026-10-02T10:00:00+00:00')
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    sig=GovernanceInvalidationSignal('ctl-sig','Adequacy','changed','dependency_change:reachability',('ev',),('art',),rec.execution_id,'cfg')
    assessment=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,invalidation_signals=(sig,),assessed_at='2026-10-02T10:00:00+00:00')
    reg=ctl.register_adapter(adapter_id='ctrl',configuration_id='cfg',target_handle_namespace='job:',supported_semantic_controls=('pause','cancel','terminate'),command_mapping={'pause':'pause','cancel':'cancel','terminate':'terminate'},controller_attestation_method='signed',control_region_evidence_method='controller-state',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    return rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg

def test_ownership_fence_advances_and_stale_owner_rejected(tmp_path):
    *_,ctl,rec,own,assessment,reg=prepared(tmp_path)
    newer=ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='owner-B',acquired_at='2026-10-02T10:00:00+00:00')
    assert newer.owner_fence==own.owner_fence+1
    with pytest.raises(StaleOwner): ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id='owner-A',owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')

def test_control_requires_committed_assessment(tmp_path):
    *_,ctl,rec,own,assessment,reg=prepared(tmp_path)
    with pytest.raises(ValueError): ctl.issue_control_request(assessment_id='fabricated',active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')

def test_control_request_rejects_stale_material_snapshot(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    from pvpp_runtime.supervision.observation import ExternalObservation
    o=ExternalObservation('late','src','reachability','net','sub','cfg','changed',None,'2026-10-02T12:00:00','z','z',{}); obs.submit_observation(o); a=obs.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00'); obs.commit_admission_change(o,a,committed_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ConcurrencyConflict): ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')

def test_adapter_registration_rejects_widened_mapping(tmp_path):
    *_,ctl,rec,own,assessment,reg=prepared(tmp_path)
    with pytest.raises(ControlMappingWidened): ctl.register_adapter(adapter_id='bad',configuration_id='cfg',target_handle_namespace='job:',supported_semantic_controls=('pause',),command_mapping={'pause':'terminate'},controller_attestation_method='signed',control_region_evidence_method='state',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')

def test_dispatch_rejects_target_swap(tmp_path):
    *_,ctl,rec,own,assessment,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(TargetScopeViolation): ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:2',control_region_at_request='cancelable',capability_evidence_ref='cap1',mapping_identity='m1',dispatched_at='2026-10-02T10:00:00+00:00')

def test_dispatch_records_time_local_control_region(tmp_path):
    *_,ctl,rec,own,assessment,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    at=ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='commit-pending',capability_evidence_ref='cap1',mapping_identity='m1',dispatched_at='2026-10-02T10:00:00+00:00')
    assert at.control_region_at_request=='commit-pending' and at.mapped_command=='cancel'

def test_enforcement_outcomes_remain_distinct_and_unverified_stays_unverified(tmp_path):
    *_,ctl,rec,own,assessment,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    at=ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='cancelable',capability_evidence_ref='cap1',mapping_identity='m1',dispatched_at='2026-10-02T10:00:00+00:00')
    e=ctl.record_enforcement_outcome(control_attempt_id=at.control_attempt_id,outcome='accepted',attestation_evidence='bad',controller_evidence_ref='ack',observed_control_region='cancelable',recorded_at='2026-10-02T10:00:00+00:00')
    assert e.outcome=='accepted' and e.attestation_status=='unverified'

def test_completed_enforcement_is_not_world_effect_record(tmp_path):
    *_,ctl,rec,own,assessment,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    at=ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='cancelable',capability_evidence_ref='cap1',mapping_identity='m1',dispatched_at='2026-10-02T10:00:00+00:00')
    e=ctl.record_enforcement_outcome(control_attempt_id=at.control_attempt_id,outcome='completed',attestation_evidence='signed:controller',controller_evidence_ref='ack',observed_control_region='stopped',recorded_at='2026-10-02T10:00:00+00:00')
    assert e.outcome=='completed' and not hasattr(e,'world_effect_state')

def test_fence_invalidates_still_issued_native_authority(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    changed=ctl.fence_execution_authority(active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,reason='continuation invalid')
    assert rec.authorization_id in changed and rt.native_execution_authorization_status(rec.authorization_id)=='invalidated'

def test_stale_owner_cannot_fence_authority(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='owner-B',acquired_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(StaleOwner): ctl.fence_execution_authority(active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,reason='stale')
    assert rt.native_execution_authorization_status(rec.authorization_id)=='issued'
