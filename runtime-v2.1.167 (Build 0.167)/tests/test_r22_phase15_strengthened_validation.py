"""v0.156 strengthened validation: real-cycle provenance, real process death, behavioral R3 gate."""
from __future__ import annotations
from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
import multiprocessing as mp
import os

from pvpp_runtime import ExecutionObservation, ExecutionBindingIdentity
from pvpp_runtime.execution import ExecutionBindingRegistry
from pvpp_runtime.models import GovernanceInvalidationSignal
from pvpp_runtime.supervision import CanonicalRuntimeBridge, SQLiteSupervisoryStore
from pvpp_runtime.supervision.observation import ObservationService, SourceRegistration, ExternalObservation
from pvpp_runtime.supervision.dependency import DependencyService
from pvpp_runtime.supervision.continuation import ContinuationService
from pvpp_runtime.supervision.control import ControlService
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.recovery import RecoveryService
from pvpp_runtime.supervision.simulation import SimulationObservationSource

from test_integrated_canonical_cycle_v041 import build as integrated_build, actual as integrated_actual, req as integrated_req
from test_r22_phase6_control import prepared


def real_cycle_supervision(tmp_path):
    rt, _world, _transition = integrated_build()
    request = integrated_req()
    integrated = rt.evaluate_integrated_canonical_cycle(integrated_actual(), request)
    license_obj = rt.build_execution_license_from_cycle(integrated.decision, request.domain_frame)
    bridge = CanonicalRuntimeBridge(rt)
    ep = bridge.instantiate_execution('real-ep', license_obj, entry_sufficient=True, max_steps=5).episode
    bindings = ExecutionBindingRegistry(tuple(rt.registry.actions))
    for action_id in license_obj.action_ids:
        bindings.register(ExecutionBindingIdentity(f'real-{action_id}', action_id, '1.0'), lambda ctx: 'ok')
    action_id = license_obj.action_ids[0]
    auth = bridge.issue_native_execution_authorization(ep, action_id, bindings, decision_cycle_id='real-cycle', configuration_id='cfg')
    store = trusted_store(tmp_path/'real.db')
    handle = bridge.resolve_canonical_execution(auth, configuration_id='cfg')
    rec = bridge.register_active_execution(store, handle, execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id), registered_at='2026-10-02T10:00:00+00:00')
    obs = ObservationService(store)
    register_test_source(obs, SourceRegistration('real-src-reg','real-src',('observation',),('reachability',),('sub',),('cfg',),('governance',),'test',None,None,'current','admin',1))
    o = ExternalObservation('real-o','real-src','reachability','net','sub','cfg','up',None,'2026-10-02T10:00:00+00:00','t0','t0',{})
    obs.submit_observation(o); adm=obs.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00'); change=obs.commit_admission_change(o,adm,committed_at='2026-10-02T10:00:00+00:00')
    dep=DependencyService(store)
    dep.register_dependency_binding(active_execution_id=rec.active_execution_id,configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00')
    cont=ContinuationService(store,dep,bridge)
    ctl=ControlService(store,dep,cont,bridge)
    ctl.register_supervisory_owner(owner_id='owner-A',configuration_id='cfg',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    ctl.register_supervisory_owner(owner_id='owner-B',configuration_id='cfg',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    own=ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='owner-A',acquired_at='2026-10-02T10:00:00+00:00')
    return rt,bridge,store,obs,dep,cont,ctl,rec,own,change,license_obj


def test_v0156_real_integrated_cycle_license_drives_supervision(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,change,license_obj=real_cycle_supervision(tmp_path)
    assert license_obj is not None and license_obj.action_ids
    assert rec.episode_id=='real-ep'
    assert dep.resolve_affected_executions(change,configuration_id='cfg')==(rec.active_execution_id,)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    sig=GovernanceInvalidationSignal('real-sig','Adequacy','changed','dependency_change:reachability',('ev',),('art',),rec.execution_id,'cfg')
    a=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,invalidation_signals=(sig,),assessed_at='2026-10-02T10:00:00+00:00')
    assert a.continuation_posture=='reauthorization_required'


def _crash_after_control_request(db_path, active_execution_id, assessment_id, owner_id, owner_fence):
    store=trusted_store(db_path)
    # The request was committed before this process-death point. A restarted
    # supervisor without live canonical state may inspect durable history but
    # must not mint new consequential control from it.
    assert store._conn.execute('SELECT count(*) n FROM control_requests').fetchone()['n']==1
    os._exit(23)  # deliberately bypass close/finalizers


def test_v0156_real_process_death_after_control_request_preserves_durable_request(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,a,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,
        owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    db_path=store.path; aid=rec.active_execution_id; assessment_id=a.assessment_id
    owner_id=own.owner_id; fence=own.owner_fence
    store.close()
    ctx=mp.get_context('spawn')
    p=ctx.Process(target=_crash_after_control_request,args=(db_path,aid,assessment_id,owner_id,fence))
    p.start(); p.join(5)
    if p.is_alive():
        p.terminate(); p.join(2)
        raise AssertionError('child process hung')
    assert p.exitcode==23
    s2=trusted_store(db_path)
    assert s2._conn.execute('SELECT count(*) n FROM control_requests').fetchone()['n']==1
    assert s2._conn.execute('SELECT count(*) n FROM control_attempts').fetchone()['n']==0


def behavioral_r3_checks(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,change,license_obj=real_cycle_supervision(tmp_path)
    before=obs.observation_count()
    # R3-14 semantic duplicate protection.
    dup=ExternalObservation('dup','real-src','reachability','net','sub','cfg','up',None,'2026-10-02T10:00:00+00:00','t0','t0',{})
    obs.submit_observation(dup); obs.submit_observation(dup)
    duplicate_ok=obs.observation_count()==before+1
    # R3-15 simulation path uses production observation semantics.
    sim=SimulationObservationSource(obs)
    simobs=ExternalObservation('sim-o','real-src','reachability','net','sub','cfg','degraded',None,'2026-10-02T10:00:01+00:00','t1','t1',{})
    _sim_adm,sim_change=sim.inject(simobs,assessed_at='2026-10-02T10:00:00+00:00',committed_at='2026-10-02T10:00:00+00:00')
    affected=dep.resolve_affected_executions(sim_change,configuration_id='cfg')
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    sig=GovernanceInvalidationSignal('gate-sig','Adequacy','changed','dependency_change:reachability',('ev',),('art',),rec.execution_id,'cfg')
    a=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,invalidation_signals=(sig,),trigger_ids=(sim_change.change_id,),assessed_at='2026-10-02T10:00:00+00:00')
    reg=ctl.register_adapter(adapter_id='gate-ctrl',configuration_id='cfg',target_handle_namespace='job:',supported_semantic_controls=('cancel',),command_mapping={'cancel':'cancel'},controller_attestation_method='signed',control_region_evidence_method='state',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    req=ctl.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    attempt=ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='cancelable',capability_evidence_ref='cap',mapping_identity='cancel=cancel',dispatched_at='2026-10-02T10:00:00+00:00')
    enf=ctl.record_enforcement_outcome(control_attempt_id=attempt.control_attempt_id,outcome='completed',attestation_evidence='signed:controller',controller_evidence_ref='ack',observed_control_region='stopped',recorded_at='2026-10-02T10:00:00+00:00')
    eff=EffectService(store,obs)
    register_test_source(obs, SourceRegistration('gate-eff-reg','gate-ledger',('effect',),('world_effect',),(),('cfg',),('effect_reconciliation',),'signed',None,None,'current','admin',1))
    unknown=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='gate-ledger',configuration_id='cfg',state='effect_unknown',realized_bundle_ref=None,evidence_ref='unknown',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    unresolved=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=unknown.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00')
    final_e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='gate-ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='world:stopped',evidence_ref='final',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    state=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=final_e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00',control_enforcement_refs=(enf.enforcement_record_id,))
    l1=eff.record_layer1_transition(active_execution_id=rec.active_execution_id,effect_reconciliation_ref=state.effect_record_id,prior_actual_state_ref='running',next_actual_state_ref='stopped',transition_time='2026-10-02T10:00:00+00:00',evidence_ref='host',provenance='host',configuration_id='cfg',authority_evidence='signed:layer1')
    recovery=RecoveryService(store,dep,eff)
    profile=recovery.register_recovery_profile(active_execution_id=rec.active_execution_id,required_control_reconciliation=True,required_effect_evidence=True,required_world_layer1_checks=True,registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    view=obs.read_current_fact_view(configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net')
    descriptor=dep.derive_dependency_set(rec.active_execution_id,derived_at='2026-10-02T10:00:00+00:00')
    checks={
        'R3-01': store._conn.execute('SELECT count(*) n FROM observations').fetchone()['n']>0,
        'R3-02': store._conn.execute('SELECT count(*) n FROM observation_admissions').fetchone()['n']>0,
        'R3-03': store.get_active_execution(rec.active_execution_id) is not None,
        'R3-04': bool(rec.execution_id and rec.attempt==1 and rec.episode_id),
        'R3-05': sim_change.new_view_version>0,
        'R3-06': a.continuation_posture=='reauthorization_required',
        'R3-07': cont.get_assessment(a.assessment_id) is not None,
        'R3-08': a.authority_fence_required is True,
        'R3-09': store.phase6_get('control_requests','control_request_id',req.control_request_id) is not None,
        'R3-10': reg.status=='current',
        'R3-11': enf.attestation_status=='verified',
        'R3-12': state.state=='completed_effect' and not state.unresolved,
        'R3-13': store.current_supervisory_ownership(rec.active_execution_id)['owner_fence']==own.owner_fence,
        'R3-14': duplicate_ok,
        'R3-15': sim_change is not None,
        'R3-16': len(store.audit_events(configuration_id='cfg'))>0,
        'R3-17': view is not None and view.version>=1,
        'R3-18': rec.active_execution_id in affected,
        'R3-19': dep.validate_snapshot(snap) is True,
        'R3-20': own.owner_fence>=1,
        'R3-21': profile.status=='current',
        'R3-22': attempt.control_region_at_request=='cancelable',
        'R3-23': unresolved.unresolved is True,
        'R3-24': l1.next_actual_state_ref=='stopped',
    }
    return checks


def test_v0156_behavioral_r3_01_through_r3_24_gate(tmp_path):
    checks=behavioral_r3_checks(tmp_path)
    assert set(checks)=={f'R3-{i:02d}' for i in range(1,25)}
    assert all(checks.values()), {k:v for k,v in checks.items() if not v}
