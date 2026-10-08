from r22_trust_fixture import proof
import pytest
from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision.control import ControlService, TargetScopeViolation
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.continuation import ContinuationReconciliationRequired
from test_r22_phase6_control import prepared, setup
from test_r3_phase2_canonical_bridge import setup as bridge_setup


def _induce_divergence(cont, dep, bridge, rec, monkeypatch):
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:10:00+00:00')
    before=bridge.current_episode(rec.episode_id).step_count
    original=cont._persist
    def fail(a):
        raise OSError('disk full')
    monkeypatch.setattr(cont,'_persist',fail)
    with pytest.raises(OSError, match='disk full'):
        cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,
            observation=ExecutionObservation('advance'),assessed_at='2026-10-02T10:10:01+00:00')
    monkeypatch.setattr(cont,'_persist',original)
    assert bridge.current_episode(rec.episode_id).step_count == before + 1
    return snap


def test_v0158_01_direct_bridge_native_invoke_cannot_bypass_retry_cutoff(tmp_path):
    rt,bridge,bindings,ep,auth,store=bridge_setup(tmp_path)
    handle=bridge.resolve_canonical_execution(auth,configuration_id='cfg-A')
    rec=bridge.register_active_execution(store,handle,execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id),registered_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(Exception, match='registered|supervised|invoke_registered'):
        bridge.invoke_authorized_native(auth,bindings,configuration_id='cfg-A')
    assert rt.native_execution_authorization_status(auth.authorization_id)=='issued'
    assert not store.has_supervised_native_invocation(rec.active_execution_id)


def test_v0158_02_dispatch_blocks_request_created_before_divergence(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,
        owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    _induce_divergence(cont,dep,bridge,rec,monkeypatch)
    with pytest.raises(Exception, match='reconciliation|divergence|fence'):
        ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,
            owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='cancelable',
            capability_evidence_ref='cap',mapping_identity='m1',dispatched_at='2026-10-02T10:10:02+00:00')


def test_v0158_03_explicit_reconciliation_terminally_fences_unreconstructable_divergence(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    _induce_divergence(cont,dep,bridge,rec,monkeypatch)
    result=cont.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,
        authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T10:11:00+00:00')
    assert result['outcome']=='terminally_fenced'
    assert store.continuation_reconciliation_required(rec.active_execution_id)
    events=[e for e in store.audit_events() if e.event_kind=='continuation_divergence_reconciled']
    assert events and events[-1].payload['outcome']=='terminally_fenced'


def test_v0158_04_assessment_bound_to_canonical_step_and_stale_after_direct_advance(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    assert assessment.canonical_step == bridge.current_episode(rec.episode_id).step_count
    episode=bridge.current_episode(rec.episode_id)
    with pytest.raises(Exception, match='supervised|intent|registered'):
        bridge.advance_execution(episode,ExecutionObservation('direct'))


def test_v0158_05_issue_rejects_malformed_target_before_persistence(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    with pytest.raises(TargetScopeViolation):
        ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,
            owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:*',created_at='2026-10-02T10:00:00+00:00')
    rows=store._conn.execute('SELECT COUNT(*) AS n FROM control_requests').fetchone()['n']
    assert rows==0


def test_v0158_06_consequential_records_include_trusted_clock_time(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,
        owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2020-01-01T00:00:00+00:00')
    assert req.created_at=='2020-01-01T00:00:00+00:00'
    assert req.trusted_created_at.startswith('2026-10-02T12:00:00')
    at=ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,
        owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='cancelable',
        capability_evidence_ref='cap',mapping_identity='m1',dispatched_at='2020-01-01T00:00:01+00:00')
    assert at.dispatched_at=='2020-01-01T00:00:01+00:00'
    assert at.trusted_dispatched_at.startswith('2026-10-02T12:00:00')

def test_v0158_07_reconciliation_can_close_consistent_prepared_intent(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:20:00+00:00')
    episode=bridge.current_episode(rec.episode_id)
    intent_id=cont._prepare_intent(rec.active_execution_id,episode,snap,'2026-10-02T10:20:01+00:00')
    assert store.continuation_reconciliation_required(rec.active_execution_id)
    result=cont.reconcile_continuation_divergence(active_execution_id=rec.active_execution_id,
        authority_id='admin',authority_proof=proof('admin'),reconciled_at='2026-10-02T10:20:02+00:00')
    assert result['outcome']=='reconciled_closed'
    assert not store.continuation_reconciliation_required(rec.active_execution_id)


def test_v0158_08_old_assessment_and_request_stale_after_successful_new_canonical_step(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,old_assessment,reg=prepared(tmp_path)
    req=ctl.issue_control_request(assessment_id=old_assessment.assessment_id,active_execution_id=rec.active_execution_id,
        owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:21:00+00:00')
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:21:01+00:00')
    new_assessment=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,
        observation=ExecutionObservation('next-step'),assessed_at='2026-10-02T10:21:02+00:00')
    assert new_assessment.canonical_step != old_assessment.canonical_step
    assert not store.continuation_reconciliation_required(rec.active_execution_id)
    with pytest.raises(Exception, match='stale_continuation_assessment'):
        ctl.issue_control_request(assessment_id=old_assessment.assessment_id,active_execution_id=rec.active_execution_id,
            owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:21:03+00:00')
    with pytest.raises(Exception, match='stale_continuation_assessment'):
        ctl.dispatch_control_request(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,
            owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='cancelable',
            capability_evidence_ref='cap',mapping_identity='m1',dispatched_at='2026-10-02T10:21:04+00:00')
