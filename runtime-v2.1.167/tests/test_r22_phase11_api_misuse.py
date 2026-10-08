from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
import pytest

from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision.models import CanonicalExecutionHandle
from pvpp_runtime.supervision.store import ConcurrencyConflict
from pvpp_runtime.supervision.observation import ObservationService, ExternalObservation, SourceRegistration
from pvpp_runtime.supervision.dependency import DependencyService
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.recovery import RecoveryService
from pvpp_runtime.supervision.control import ControlMappingWidened, TargetScopeViolation, StaleOwner
from pvpp_runtime.supervision.operational import OperationalObservationAdapter, OperationalEnforcementAdapter, OperationalEffectAdapter, HostLayer1Authority
from test_r22_phase6_control import setup as phase6_setup, prepared
from test_r22_phase7_effect import setup7, terminalize
from test_r22_phase8_recovery import prep


def test_identity_fabricated_and_cross_configuration_lineage_rejected(tmp_path):
    rt, bridge, store, obs, dep, cont, rec = phase6_setup(tmp_path)
    fake = CanonicalExecutionHandle('fake','no-episode',999,'p','a','cy','cfg',1,'b','1','no-auth','current','t')
    with pytest.raises(PermissionError, match="canonical_resolution_failed"):
        store.register_active_execution(fake, execution_id='forged', registered_at='2026-10-02T10:00:00+00:00')
    h = store.get_active_execution(rec.active_execution_id)
    with pytest.raises(ValueError):
        dep.register_dependency_binding(active_execution_id=h.active_execution_id, configuration_id='other', fact_kind='reachability', fact_id='net', registration_authority='model',authority_proof=proof('model'), registered_at='2026-10-02T10:00:00+00:00')


def test_source_authority_self_named_and_out_of_scope_remain_nonauthoritative(tmp_path):
    s=ObservationService(trusted_store(tmp_path/'src.db'))
    o=ExternalObservation('o','authoritative_sensor','reachability','route','net','cfg',True,1.0,'2026-10-02T10:00:00','x','x',{})
    s.submit_observation(o); a=s.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00')
    assert not a.authoritative and s.commit_admission_change(o,a,committed_at='2026-10-02T10:00:00+00:00') is None


def test_dependency_snapshot_cannot_omit_registered_material_fact(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=phase6_setup(tmp_path)
    dep.register_dependency_binding(active_execution_id=rec.active_execution_id,configuration_id='cfg',subject_id='sub',fact_kind='missing_material',fact_id='F2',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ValueError): dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')


def test_fact_identity_alias_is_canonicalized_not_laundered(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=phase6_setup(tmp_path)
    d=dep.derive_dependency_set(rec.active_execution_id,derived_at='2026-10-02T10:00:00+00:00')
    assert ('sub','reachability','net') in d.canonical_fact_identities and ('sub',' Reachability ','net') not in d.canonical_fact_identities


def test_snapshot_laundering_stale_descriptor_rejected(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=phase6_setup(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    dep.register_dependency_binding(active_execution_id=rec.active_execution_id,configuration_id='cfg',subject_id='sub',fact_kind='other',fact_id='z',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ConcurrencyConflict): dep.validate_snapshot(snap)


def test_control_mapping_cannot_widen_pause_to_terminate(tmp_path):
    *_,ctl,rec,own,assessment,reg=prepared(tmp_path)
    with pytest.raises(ControlMappingWidened):
        ctl.register_adapter(adapter_id='bad',configuration_id='cfg',target_handle_namespace='job:',supported_semantic_controls=('pause',),command_mapping={'pause':'terminate'},controller_attestation_method='signed',control_region_evidence_method='state',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')


def test_target_swap_outside_exact_request_is_rejected(tmp_path):
    *_,ctl,rec,own,assessment,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(TargetScopeViolation):
        ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:2',control_region_at_request='cancelable',capability_evidence_ref='cap',mapping_identity='m',dispatched_at='2026-10-02T10:00:00+00:00')


def test_unverified_enforcement_callback_cannot_become_world_effect(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path)
    # Existing enforcement status is not an effect source; no authoritative effect evidence means open.
    assert eff.current_effect_state(rec.active_execution_id).state=='open'


def test_unregistered_effect_source_cannot_close_effect(tmp_path):
    *_,rec,eff=setup7(tmp_path)
    with pytest.raises(ValueError,match='evidence_unverified'):
        eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='self-authorized',configuration_id='cfg',state='completed_effect',realized_bundle_ref='b',evidence_ref='return-value',provenance='caller',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    assert eff.current_effect_state(rec.active_execution_id).state=='open'


def test_retry_safety_cannot_be_declared_post_hoc_after_unknown_effect(tmp_path):
    *_,rec,eff=setup7(tmp_path)
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='effect_unknown',realized_bundle_ref=None,evidence_ref='timeout',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ValueError,match='effect_unresolved'): eff.assert_retry_safe(active_execution_id=rec.active_execution_id)


def test_finality_cannot_be_rewritten_and_late_effect_reconciles_forward(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path); term=terminalize(ctl,rec)
    f=eff.accept_canonical_finality(active_execution_id=rec.active_execution_id,continuation_assessment_id=term.assessment_id,terminalized_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ConcurrencyConflict,match='canonical_finality_conflict'):
        eff.accept_canonical_finality(active_execution_id=rec.active_execution_id,continuation_assessment_id=term.assessment_id,terminalized_at='2026-10-02T10:00:00+00:00')
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='b',evidence_ref='late',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    st=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00')
    assert st.canonical_finality_ref==f.canonical_finality_id and eff.get_canonical_finality(rec.active_execution_id)==f


def test_recovering_owner_cannot_weaken_profile_or_complete_from_replay(tmp_path):
    store,obs,dep,eff,svc,rec,p=prep(tmp_path,True)
    with pytest.raises(PermissionError):
        svc.register_recovery_profile(active_execution_id=rec.active_execution_id,required_control_reconciliation=False,required_effect_evidence=False,required_world_layer1_checks=False,registration_authority='recovering-owner',registered_at='2026-10-02T10:00:00+00:00')
    rr=svc.begin_recovery(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00',provenance='replay-package')
    with pytest.raises(ValueError,match='recovery_requirement_unsatisfied'):
        svc.assert_resumption_allowed(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence)


def test_split_brain_stale_owner_cannot_commit_control(tmp_path):
    *_,ctl,rec,own,assessment,reg=prepared(tmp_path)
    ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='owner-B',acquired_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(StaleOwner):
        ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')


def test_host_boundary_has_no_hidden_selector_and_layer1_requires_host_authority(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    eff=EffectService(store,obs)
    for adapter in (OperationalObservationAdapter(obs),OperationalEnforcementAdapter(ctl),OperationalEffectAdapter(eff)):
        assert not hasattr(adapter,'evaluate_continuation') and not hasattr(adapter,'choose_remedy')
    with pytest.raises(ValueError):
        HostLayer1Authority(eff).commit(active_execution_id=rec.active_execution_id,effect_reconciliation_ref='invented',prior_actual_state_ref='a',next_actual_state_ref='b',transition_time='2026-10-02T10:00:00+00:00',evidence_ref='h',provenance='host',configuration_id='cfg')
