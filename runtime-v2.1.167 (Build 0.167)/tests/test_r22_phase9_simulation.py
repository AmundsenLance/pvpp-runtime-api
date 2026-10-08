from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
import pytest
from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision.simulation import DeterministicScheduler,SimulationObservationSource,SimulationEnforcementAdapter,SimulationEffectSource,CrashFailoverInjector,SimulationAuditOracle
from pvpp_runtime.supervision.observation import ExternalObservation,SourceRegistration
from pvpp_runtime.supervision.dependency import DependencyService
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.recovery import RecoveryService
from pvpp_runtime.supervision.control import StaleOwner
from test_r22_phase6_control import setup,prepared
from test_r22_phase7_effect import setup7
from test_r22_phase8_recovery import prep
from r22_real_cycle_fixture import license_from_real_cycle

def inject(obs,source,oid,value,effective,received,fact_kind='reachability',fact_id='net'):
    o=ExternalObservation(oid,'src',fact_kind,fact_id,'sub','cfg',value,None,effective,effective,received,{})
    return source.inject(o,assessed_at=received,committed_at=received)

def test_trace1_reachability_change_flows_observation_to_dependency(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path); sim=SimulationObservationSource(obs)
    a,ch=inject(obs,sim,'route-new','new-route','2026-10-02T11:00:00','r')
    assert a.authoritative and rec.active_execution_id in dep.resolve_affected_executions(ch,configuration_id='cfg')

def test_trace2_authority_revocation_fences_future_not_consumed_history(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    changed=ctl.fence_execution_authority(active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,reason='revoked')
    assert rec.authorization_id in changed and rt.native_execution_authorization_status(rec.authorization_id)=='invalidated'

def test_trace3_resource_loss_requires_explicit_dependency_not_automatic_inference(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path)
    register_test_source(obs, SourceRegistration('sr2','resource-sensor',('observation',),('resource',),('sub',),('cfg',),('governance',),'att',None,None,'current','admin',1))
    sim=SimulationObservationSource(obs); o=ExternalObservation('res-loss','resource-sensor','resource','gpu','sub','cfg','lost',None,'2','2','2',{})
    a,ch=sim.inject(o,assessed_at='2026-10-02T10:00:00+00:00',committed_at='2026-10-02T10:00:00+00:00'); assert ch is not None
    assert rec.active_execution_id not in dep.resolve_affected_executions(ch,configuration_id='cfg')
    dep.register_dependency_binding(active_execution_id=rec.active_execution_id,configuration_id='cfg',fact_kind='resource',fact_id='gpu',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00')
    assert rec.active_execution_id in dep.resolve_affected_executions(ch,configuration_id='cfg')

def test_trace4_out_of_order_and_contradictory_observations_preserve_governed_view(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path); sim=SimulationObservationSource(obs); sch=DeterministicScheduler()
    sch.schedule(1,'newer',lambda: inject(obs,sim,'o-new','up','2026-10-02T12:00:00','r1'))
    sch.schedule(2,'older',lambda: inject(obs,sim,'o-old','down','2026-10-02T11:00:00','r2'))
    sch.run(); v=obs.read_current_fact_view(configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net'); assert v.value=='up'
    _,ch=inject(obs,sim,'o-conflict','down','2026-10-02T12:00:00','r3'); v=obs.read_current_fact_view(configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net'); assert ch and v.state=='unresolved'

def test_trace5_shared_dependency_fanout_is_one_to_many_not_broadcast_decision(tmp_path):
    from pvpp_runtime.execution import ExecutionBindingRegistry
    rt,bridge,store,obs,dep,cont,rec1=setup(tmp_path); sim=SimulationObservationSource(obs)
    lic2=license_from_real_cycle(rt); action_id=lic2.action_ids[0]
    reg2=ExecutionBindingRegistry(tuple(rt.registry.actions)); reg2.register(__import__('pvpp_runtime').ExecutionBindingIdentity('b2',action_id,'1'),lambda ctx:'ok')
    ep2=bridge.instantiate_execution('ep2',lic2,entry_sufficient=True,max_steps=5).episode
    auth2=bridge.issue_native_execution_authorization(ep2,action_id,reg2,decision_cycle_id='cy2',configuration_id='cfg')
    h2=bridge.resolve_canonical_execution(auth2,configuration_id='cfg'); rec2=bridge.register_active_execution(store,h2,execution_id=rt.native_execution_authorization_execution_id(auth2.authorization_id),registered_at='2026-10-02T10:00:00+00:00')
    dep.register_dependency_binding(active_execution_id=rec2.active_execution_id,configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00')
    _,ch=inject(obs,sim,'shared-change','changed','2026-10-02T13:00:00','r')
    affected=dep.resolve_affected_executions(ch,configuration_id='cfg')
    assert set(affected)=={rec1.active_execution_id,rec2.active_execution_id} and not hasattr(ch,'continuation_posture')

def test_trace6_raced_noninterruptible_effect_preserves_too_late_and_late_effect(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path); dep=DependencyService(store)
    own=store.current_supervisory_ownership(rec.active_execution_id)
    # retrieve committed assessment and adapter from production tables/services via setup fixture recreation is unnecessary; use control records created here from existing fixture state
    cont=ctl.continuation; assessment=next(iter(cont._assessments.values())); regrow=store._conn.execute("SELECT adapter_registration_id FROM adapter_registrations ORDER BY rowid DESC LIMIT 1").fetchone()
    regid=regrow['adapter_registration_id']
    req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own['owner_id'],owner_fence=own['owner_fence'],requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    simctl=SimulationEnforcementAdapter(ctl); at=simctl.dispatch(control_request_id=req.control_request_id,adapter_registration_id=regid,owner_id=own['owner_id'],owner_fence=own['owner_fence'],target_handle='job:1',control_region_at_request='commit-pending',capability_evidence_ref='cap',mapping_identity='m',dispatched_at='2026-10-02T10:00:00+00:00')
    en=simctl.outcome(control_attempt_id=at.control_attempt_id,outcome='too_late',attestation_evidence='signed:controller',controller_evidence_ref='ack',observed_control_region='irreversible',recorded_at='2026-10-02T10:00:00+00:00')
    simeff=SimulationEffectSource(eff); e,st=simeff.inject_and_reconcile(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='bundle',evidence_ref='late',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00',updated_at='2026-10-02T10:00:00+00:00',control_enforcement_refs=(en.enforcement_record_id,))
    assert en.outcome=='too_late' and st.state=='completed_effect' and not st.unresolved

def test_trace7_restart_new_fence_blocks_stale_owner_and_replay_is_not_authority(tmp_path):
    store,obs,dep,eff,svc,rec,p=prep(tmp_path,True); old=store.current_supervisory_ownership(rec.active_execution_id); crash=CrashFailoverInjector(svc); rr=crash.failover(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00')
    assert rr.owner_fence>old['owner_fence'] and not rr.control_resumption_allowed
    with pytest.raises(ValueError): svc.assert_resumption_allowed(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence)

def test_scheduler_is_deterministic_for_same_time(tmp_path):
    s=DeterministicScheduler(); seen=[]; s.schedule(1,'a',lambda:seen.append('a')); s.schedule(1,'b',lambda:seen.append('b')); s.run(); assert seen==['a','b']

def test_audit_oracle_is_read_only_surface(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path); q=SimulationAuditOracle(store); before=obs.observation_count(); assert q.table_count('observations')==before and obs.observation_count()==before

def test_simulation_observation_adapter_uses_production_tables(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path); q=SimulationAuditOracle(store); sim=SimulationObservationSource(obs); before=q.table_count('observations'); inject(obs,sim,'sim-prod','up2','2026-10-02T14:00:00','r'); assert q.table_count('observations')==before+1
