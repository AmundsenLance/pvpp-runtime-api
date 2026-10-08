from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
"""Runtime 2.2 v0.154 Phase 13 — crash injection at Section-31 durable boundaries."""
import pytest
from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision import SQLiteSupervisoryStore
from pvpp_runtime.supervision.observation import ObservationService, ExternalObservation
from pvpp_runtime.supervision.dependency import DependencyService
from pvpp_runtime.supervision.continuation import ContinuationService
from pvpp_runtime.supervision.control import ControlService, StaleOwner
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.recovery import RecoveryService
from pvpp_runtime.supervision.store import ConcurrencyConflict
from test_r22_phase6_control import setup, prepared
from test_r22_phase7_effect import setup7, terminalize, terminalize
from test_r22_phase8_recovery import prep


def _obs(oid='crash-o', value='down', effective='2026-10-02T13:00:00'):
    return ExternalObservation(oid,'src','reachability','net','sub','cfg',value,None,effective,effective,effective,{})


def test_crash01_before_admission_commit_has_no_phantom_current_view_change(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path)
    before=obs.read_current_fact_view(configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net')
    o=_obs(); obs.submit_observation(o); obs.assess_observation(o,assessed_at=o.received_at)
    path=store.path; store.close()  # crash before commit_admission_change
    s2=trusted_store(path); o2=ObservationService(s2)
    after=o2.read_current_fact_view(configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net')
    assert after==before


def test_crash02_after_admission_commit_preserves_change_for_fanout_recovery(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path)
    o=_obs(); obs.submit_observation(o); a=obs.assess_observation(o,assessed_at=o.received_at); ch=obs.commit_admission_change(o,a,committed_at='2026-10-02T10:00:00+00:00')
    cid=ch.change_id; path=store.path; store.close()  # crash before fan-out
    s2=trusted_store(path); ObservationService(s2); d2=DependencyService(s2)
    row=s2._conn.execute('SELECT payload FROM admitted_fact_changes WHERE change_id=?',(cid,)).fetchone()
    assert row is not None and rec.active_execution_id in d2.resolve_affected_executions(ch,configuration_id='cfg')


def test_crash03_during_continuation_assessment_cannot_commit_stale_snapshot(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path); snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    o=_obs(); obs.submit_observation(o); a=obs.assess_observation(o,assessed_at=o.received_at); obs.commit_admission_change(o,a,committed_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ConcurrencyConflict):
        cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('crash3'),assessed_at='2026-10-02T10:00:00+00:00')


def test_crash04_control_request_survives_restart_before_dispatch(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,a,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    path=store.path; store.close()  # crash before dispatch
    s2=trusted_store(path); d2=DependencyService(s2); c2=ContinuationService(s2,d2,bridge); ctl2=ControlService(s2,d2,c2,bridge)
    raw=s2.phase6_get('control_requests','control_request_id',req.control_request_id)
    assert raw is not None and s2._conn.execute('SELECT count(*) n FROM control_attempts').fetchone()['n']==0


def test_crash05_after_dispatch_before_ack_remains_effect_unresolved(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path); own=store.current_supervisory_ownership(rec.active_execution_id); a=next(iter(ctl.continuation._assessments.values()))
    regid=store._conn.execute('SELECT adapter_registration_id FROM adapter_registrations ORDER BY rowid DESC LIMIT 1').fetchone()['adapter_registration_id']
    req=ctl.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own['owner_id'],owner_fence=own['owner_fence'],requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=regid,owner_id=own['owner_id'],owner_fence=own['owner_fence'],target_handle='job:1',control_region_at_request='cancelable',capability_evidence_ref='cap',mapping_identity='m',dispatched_at='2026-10-02T10:00:00+00:00')
    path=store.path; store.close()
    s2=trusted_store(path); o2=ObservationService(s2); e2=EffectService(s2,o2)
    st=e2.current_effect_state(rec.active_execution_id)
    assert st.state=='open' and st.unresolved
    with pytest.raises(ValueError,match='effect_unresolved'): e2.assert_retry_safe(active_execution_id=rec.active_execution_id)


def test_crash06_after_ack_before_effect_does_not_infer_effect(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path); own=store.current_supervisory_ownership(rec.active_execution_id); a=next(iter(ctl.continuation._assessments.values()))
    regid=store._conn.execute('SELECT adapter_registration_id FROM adapter_registrations ORDER BY rowid DESC LIMIT 1').fetchone()['adapter_registration_id']
    req=ctl.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own['owner_id'],owner_fence=own['owner_fence'],requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    at=ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=regid,owner_id=own['owner_id'],owner_fence=own['owner_fence'],target_handle='job:1',control_region_at_request='cancelable',capability_evidence_ref='cap',mapping_identity='m',dispatched_at='2026-10-02T10:00:00+00:00')
    ctl.record_enforcement_outcome(control_attempt_id=at.control_attempt_id,outcome='completed',attestation_evidence='signed:controller',controller_evidence_ref='ack',observed_control_region='stopped',recorded_at='2026-10-02T10:00:00+00:00')
    path=store.path; store.close()
    s2=trusted_store(path); o2=ObservationService(s2); e2=EffectService(s2,o2)
    assert e2.current_effect_state(rec.active_execution_id).state=='open'


def test_crash07_after_effect_reconciliation_preserves_effect_evidence(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path)
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='bundle',evidence_ref='world',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    st=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00')
    path=store.path; store.close()
    s2=trusted_store(path); o2=ObservationService(s2); e2=EffectService(s2,o2); recovered=e2.current_effect_state(rec.active_execution_id)
    assert recovered.state=='completed_effect' and recovered.version==st.version and not recovered.unresolved


def test_crash08_after_finality_before_layer1_preserves_finality_and_requires_host_transition(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path)
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='bundle',evidence_ref='world',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00'); st=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00')
    term=terminalize(ctl,rec,at='2026-10-02T10:35:00+00:00'); fin=eff.accept_canonical_finality(active_execution_id=rec.active_execution_id,continuation_assessment_id=term.assessment_id,terminalized_at='2026-10-02T10:00:00+00:00')
    path=store.path; store.close()
    s2=trusted_store(path); o2=ObservationService(s2); e2=EffectService(s2,o2)
    assert e2.get_canonical_finality(rec.active_execution_id)==fin
    assert s2._conn.execute('SELECT count(*) n FROM layer1_transitions').fetchone()['n']==0
    with pytest.raises(ValueError,match='host-authoritative'):
        e2.record_layer1_transition(active_execution_id=rec.active_execution_id,effect_reconciliation_ref=st.effect_record_id,prior_actual_state_ref='a',next_actual_state_ref='b',transition_time='2026-10-02T10:00:00+00:00',evidence_ref='h',provenance='recovery',configuration_id='cfg',authority_evidence='bad')


def test_crash09_during_recovery_remains_fenced_until_requirements_and_fresh_snapshot(tmp_path):
    store,obs,dep,eff,svc,rec,p=prep(tmp_path,True); rr=svc.begin_recovery(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00')
    path=store.path; store.close()
    s2=trusted_store(path); o2=ObservationService(s2); d2=DependencyService(s2); e2=EffectService(s2,o2); svc2=RecoveryService(s2,d2,e2)
    with pytest.raises(ValueError,match='recovery_requirement_unsatisfied'):
        svc2.assert_resumption_allowed(active_execution_id=rec.active_execution_id,owner_id='B',owner_fence=rr.owner_fence)


def test_crash10_old_owner_return_may_not_commit_control(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,a,reg=prepared(tmp_path)
    ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='B',acquired_at='2026-10-02T10:00:00+00:00')
    path=store.path; store.close()
    s2=trusted_store(path); d2=DependencyService(s2); c2=ContinuationService(s2,d2,bridge); ctl2=ControlService(s2,d2,c2,bridge)
    with pytest.raises(StaleOwner):
        ctl2.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
