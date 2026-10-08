from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
import pytest
from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision.operational import OperationalObservationAdapter,OperationalEnforcementAdapter,OperationalEffectAdapter,HostLayer1Authority
from pvpp_runtime.supervision.observation import ExternalObservation,SourceRegistration
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.control import ControlMappingWidened
from test_r22_phase6_control import prepared

def pilot(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,old_assessment,reg=prepared(tmp_path)
    eff=EffectService(store,obs)
    register_test_source(obs, SourceRegistration('effect-reg','world-ledger',('effect','Layer-1-support'),(),('sub',),('cfg',),('effect_reconciliation',),'signed',None,None,'current','admin',1))
    return rt,bridge,store,obs,dep,cont,ctl,rec,own,reg,eff

def changed_observation():
    return ExternalObservation('op-change','src','reachability','net','sub','cfg','down',None,'2026-10-02T15:00:00','2026-10-02T15:00:00','2026-10-02T15:00:01',{'transport':'pilot'})

def test_operational_pilot_full_chain_without_semantic_bypass(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,reg,eff=pilot(tmp_path)
    oa=OperationalObservationAdapter(obs); admission,change=oa.admit(changed_observation(),assessed_at='2026-10-02T10:00:00+00:00',committed_at='2026-10-02T10:00:00+00:00')
    assert admission.authoritative and rec.active_execution_id in dep.resolve_affected_executions(change,configuration_id='cfg')
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    assessment=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('op-eval',continuation_sufficient=False),assessed_at='2026-10-02T10:00:00+00:00')
    req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    ca=OperationalEnforcementAdapter(ctl); attempt=ca.dispatch_exact(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='cancelable',capability_evidence_ref='controller-state',mapping_identity='cancel=cancel',dispatched_at='2026-10-02T10:00:00+00:00')
    enforcement=ca.report_outcome(control_attempt_id=attempt.control_attempt_id,outcome='completed',attestation_evidence='signed:controller',controller_evidence_ref='signed-ack',observed_control_region='stopped',recorded_at='2026-10-02T10:00:00+00:00')
    ea=OperationalEffectAdapter(eff); evidence,state=ea.admit_and_reconcile(active_execution_id=rec.active_execution_id,source_id='world-ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='world:stopped',evidence_ref='ledger:1',provenance='signed-ledger',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00',updated_at='2026-10-02T10:00:00+00:00',control_enforcement_refs=(enforcement.enforcement_record_id,))
    l1=HostLayer1Authority(eff).commit(authority_evidence='signed:layer1',active_execution_id=rec.active_execution_id,effect_reconciliation_ref=state.effect_record_id,prior_actual_state_ref='world:running',next_actual_state_ref='world:stopped',transition_time='2026-10-02T10:00:00+00:00',evidence_ref='host-state:2',provenance='host-authoritative',configuration_id='cfg')
    assert change and assessment and req and enforcement.outcome=='completed' and state.state=='completed_effect' and l1.next_actual_state_ref=='world:stopped'

def test_observation_adapter_does_not_issue_control(tmp_path):
    *_,obs,dep,cont,ctl,rec,own,reg,eff=pilot(tmp_path)
    oa=OperationalObservationAdapter(obs); _,change=oa.admit(changed_observation(),assessed_at='2026-10-02T10:00:00+00:00',committed_at='2026-10-02T10:00:00+00:00')
    assert change is not None and store_count(ctl.store,'control_requests')==0

def store_count(store,table): return store._conn.execute(f'SELECT count(*) n FROM {table}').fetchone()['n']

def test_operational_control_adapter_cannot_widen_mapping(tmp_path):
    *_,ctl,rec,own,reg,eff=pilot(tmp_path)[5:]
    with pytest.raises(ControlMappingWidened): ctl.register_adapter(adapter_id='bad-op',configuration_id='cfg',target_handle_namespace='job:',supported_semantic_controls=('pause',),command_mapping={'pause':'terminate'},controller_attestation_method='signed',control_region_evidence_method='state',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')

def test_controller_completion_does_not_create_effect_state(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,reg,eff=pilot(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00'); a=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('e',continuation_sufficient=False),assessed_at='2026-10-02T10:00:00+00:00')
    req=ctl.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    ca=OperationalEnforcementAdapter(ctl); at=ca.dispatch_exact(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='cancelable',capability_evidence_ref='c',mapping_identity='m',dispatched_at='2026-10-02T10:00:00+00:00'); ca.report_outcome(control_attempt_id=at.control_attempt_id,outcome='completed',attestation_evidence='signed:controller',controller_evidence_ref='ack',observed_control_region='stopped',recorded_at='2026-10-02T10:00:00+00:00')
    assert eff.current_effect_state(rec.active_execution_id).state=='open'

def test_layer1_requires_explicit_host_authority(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,reg,eff=pilot(tmp_path); ea=OperationalEffectAdapter(eff)
    _,st=ea.admit_and_reconcile(active_execution_id=rec.active_execution_id,source_id='world-ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='b',evidence_ref='e',provenance='p',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00',updated_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ValueError): eff.record_layer1_transition(active_execution_id=rec.active_execution_id,effect_reconciliation_ref=st.effect_record_id,prior_actual_state_ref='a',next_actual_state_ref='b',transition_time='2026-10-02T10:00:00+00:00',evidence_ref='h',provenance='p',configuration_id='cfg',authority_evidence='bad')

def test_effect_adapter_requires_registered_effect_authority(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,reg,eff=pilot(tmp_path); ea=OperationalEffectAdapter(eff)
    with pytest.raises(ValueError): ea.admit_and_reconcile(active_execution_id=rec.active_execution_id,source_id='src',configuration_id='cfg',state='completed_effect',realized_bundle_ref='b',evidence_ref='e',provenance='p',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00',updated_at='2026-10-02T10:00:00+00:00')

def test_operational_adapters_expose_no_governance_choice_method(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,reg,eff=pilot(tmp_path)
    for adapter in (OperationalObservationAdapter(obs),OperationalEnforcementAdapter(ctl),OperationalEffectAdapter(eff)):
        assert not hasattr(adapter,'evaluate_continuation') and not hasattr(adapter,'choose_remedy')

def test_layer1_transition_uses_current_effect_reconciliation(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,reg,eff=pilot(tmp_path); ea=OperationalEffectAdapter(eff)
    _,st=ea.admit_and_reconcile(active_execution_id=rec.active_execution_id,source_id='world-ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='b',evidence_ref='e',provenance='p',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00',updated_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ValueError): HostLayer1Authority(eff).commit(authority_evidence='signed:layer1',active_execution_id=rec.active_execution_id,effect_reconciliation_ref='stale',prior_actual_state_ref='a',next_actual_state_ref='b',transition_time='2026-10-02T10:00:00+00:00',evidence_ref='h',provenance='p',configuration_id='cfg')

def test_operational_pilot_uses_production_durable_tables(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,reg,eff=pilot(tmp_path); before=store_count(store,'observations')
    OperationalObservationAdapter(obs).admit(changed_observation(),assessed_at='2026-10-02T10:00:00+00:00',committed_at='2026-10-02T10:00:00+00:00')
    assert store_count(store,'observations')==before+1

def test_host_layer1_authority_cannot_invent_effect_reconciliation(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,reg,eff=pilot(tmp_path)
    with pytest.raises(ValueError): HostLayer1Authority(eff).commit(authority_evidence='signed:layer1',active_execution_id=rec.active_execution_id,effect_reconciliation_ref='invented',prior_actual_state_ref='a',next_actual_state_ref='b',transition_time='2026-10-02T10:00:00+00:00',evidence_ref='h',provenance='p',configuration_id='cfg')
