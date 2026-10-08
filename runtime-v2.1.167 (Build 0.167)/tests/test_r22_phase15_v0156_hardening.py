from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
import threading
import time
import pytest

from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision.store import SQLiteSupervisoryStore, ConcurrencyConflict
from pvpp_runtime.supervision.dependency import DependencyService
from pvpp_runtime.supervision.continuation import ContinuationService
from pvpp_runtime.supervision.control import ControlService, ControlMappingWidened, TargetScopeViolation
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.observation import ObservationService, ExternalObservation
from pvpp_runtime.supervision.recovery import RecoveryService

from test_r22_phase6_control import prepared, setup
from test_r22_phase7_effect import setup7
from test_r22_phase8_recovery import prep


def _fresh_abort_assessment(tmp_path):
    rt, bridge, store, obs, dep, cont, rec = setup(tmp_path)
    ctl = ControlService(store, dep, cont, bridge)
    ctl.register_supervisory_owner(owner_id='owner-A', configuration_id='cfg', registration_authority='admin',authority_proof=proof('admin'), registered_at='2026-10-02T10:00:00+00:00')
    own = ctl.acquire_ownership(active_execution_id=rec.active_execution_id, owner_id='owner-A', acquired_at='2026-10-02T10:00:00+00:00')
    snap = dep.capture_governance_snapshot(rec.active_execution_id, created_at='2026-10-02T10:00:01+00:00')
    a = cont.evaluate_continuation(
        active_execution_id=rec.active_execution_id,
        snapshot=snap,
        observation=ExecutionObservation('stop', continuation_sufficient=False),
        assessed_at='2026-10-02T10:00:02+00:00',
    )
    return rt, bridge, store, obs, dep, cont, ctl, rec, own, a


def test_v0156_01_snapshots_and_assessments_survive_store_reopen(tmp_path):
    rt, bridge, store, obs, dep, cont, ctl, rec, own, a = _fresh_abort_assessment(tmp_path)
    snap_id = a.committed_snapshot_id
    assessment_id = a.assessment_id
    db_path = store.path
    store.close()

    s2 = trusted_store(db_path)
    d2 = DependencyService(s2)
    c2 = ContinuationService(s2, d2, bridge)
    assert d2.get_snapshot(snap_id) is not None
    assert c2.get_assessment(assessment_id) is not None


def test_v0156_02_control_request_cannot_contradict_continue_or_use_unknown_control(tmp_path):
    rt, bridge, store, obs, dep, cont, rec = setup(tmp_path)
    ctl=ControlService(store,dep,cont,bridge)
    own=ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='owner-A',acquired_at='2026-10-02T10:00:00+00:00')
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:01+00:00')
    assessment=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('continue'),assessed_at='2026-10-02T10:00:02+00:00')
    assert assessment.continuation_posture == 'continue'
    with pytest.raises(ValueError, match='control.*posture|continuation.*control'):
        ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='terminate',target_handle='job:1',created_at='2026-10-02T10:00:03+00:00')
    with pytest.raises(ValueError, match='unsupported.*control|semantic control'):
        ctl.issue_control_request(assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='anything_at_all',target_handle='job:1',created_at='2026-10-02T10:00:03+00:00')


def test_v0156_03_adapter_rejects_unknown_command_mapping_and_ambiguous_namespace(tmp_path):
    *_, ctl, _rec, _own, _assessment, _reg = prepared(tmp_path)
    with pytest.raises((ValueError, ControlMappingWidened)):
        ctl.register_adapter(
            adapter_id='bad-map', configuration_id='cfg', target_handle_namespace='job:',
            supported_semantic_controls=('pause',), command_mapping={'pause':'kill -9 && wipe_disk'},
            controller_attestation_method='signed', control_region_evidence_method='state',
            registration_authority='admin',authority_proof=proof('admin'), registered_at='2026-10-02T10:00:00+00:00')
    with pytest.raises((ValueError, TargetScopeViolation)):
        ctl.register_adapter(
            adapter_id='bad-ns', configuration_id='cfg', target_handle_namespace='j',
            supported_semantic_controls=('pause',), command_mapping={'pause':'pause'},
            controller_attestation_method='signed', control_region_evidence_method='state',
            registration_authority='admin',authority_proof=proof('admin'), registered_at='2026-10-02T10:00:00+00:00')


def test_v0156_04_canonical_finality_cannot_be_asserted_while_episode_active(tmp_path):
    rt, store, obs, ctl, rec, eff = setup7(tmp_path)
    with pytest.raises(ValueError, match='canonical.*terminal|finality.*active|terminal'):
        eff.accept_canonical_finality(
            active_execution_id=rec.active_execution_id,
            epsilon_terminal_status='completed',
            terminalized_at='2026-10-02T10:00:00+00:00',
        )


def test_v0156_05_retry_contract_cannot_be_registered_after_effect_evidence(tmp_path):
    *_, rec, eff = setup7(tmp_path)
    e = eff.submit_effect_evidence(
        active_execution_id=rec.active_execution_id, source_id='ledger', configuration_id='cfg',
        state='effect_unknown', realized_bundle_ref=None, evidence_ref='unknown', provenance='signed',
        observed_at='2026-10-02T10:00:00+00:00', effective_at='2026-10-02T10:00:00+00:00', received_at='2026-10-02T10:00:00+00:00')
    eff.reconcile_effect(active_execution_id=rec.active_execution_id, effect_evidence_id=e.effect_evidence_id, updated_at='2026-10-02T10:00:00+00:00')
    with pytest.raises((ValueError, ConcurrencyConflict), match='pre.*exist|retry[_ ]contract|effect.*already'):
        eff.register_retry_contract(
            active_execution_id=rec.active_execution_id,
            idempotent=True,
            reconciliation_required=True,
            registered_at='2026-10-02T10:00:00+00:00')


def test_v0156_06_recovery_claim_strings_cannot_substitute_for_control_and_layer1_evidence(tmp_path):
    store, obs, dep, eff, svc, rec, p = prep(tmp_path, True)
    rr = svc.begin_recovery(active_execution_id=rec.active_execution_id, new_owner_id='B', started_at='2026-10-02T10:00:00+00:00')
    x = svc.reconcile_recovery(
        active_execution_id=rec.active_execution_id,
        owner_id='B', owner_fence=rr.owner_fence,
        external_control_status='reconciled',
        effect_status='no_material_effect_evidenced',
        layer1_world_state_status='reconciled')
    result = dict(x.requirement_results)
    assert result['control'] is False
    assert result['layer1'] is False
    assert x.recovery_state == 'unresolved'


def test_v0156_07_dependency_lookup_is_exact_and_subject_scoped(tmp_path):
    rt, bridge, store, obs, dep, cont, rec = setup(tmp_path)
    # Current view contains reachability/net for subject 'sub'.  A different fact id must not wildcard-match it.
    dep.register_dependency_binding(
        active_execution_id=rec.active_execution_id,
        configuration_id='cfg', subject_id='sub', fact_kind='reachability', fact_id='n_t',
        registration_authority='model',authority_proof=proof('model'), registered_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ValueError, match='missing current governed fact'):
        dep.capture_governance_snapshot(rec.active_execution_id, created_at='2026-10-02T10:00:00+00:00')


def test_v0156_08_ownership_requires_registered_authority_and_expiry_is_enforced(tmp_path):
    rt, bridge, store, obs, dep, cont, rec = setup(tmp_path)
    ctl = ControlService(store, dep, cont, bridge)
    with pytest.raises(PermissionError, match='owner|supervisor|authority'):
        ctl.acquire_ownership(
            active_execution_id=rec.active_execution_id,
            owner_id='unregistered-owner',
            acquired_at='2026-10-02T10:00:00+00:00')
    ctl.register_supervisory_owner(owner_id='expired-owner',configuration_id='cfg',registration_authority='admin',authority_proof=proof('admin'),registered_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ValueError, match='expired'):
        ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='expired-owner',
            acquired_at='2026-10-02T10:00:00+00:00',expires_at='2000-01-01T00:00:00+00:00')
    ctl.register_owner_authority(owner_id='expired-owner',configuration_id='cfg',registration_authority='admin',authority_proof=proof('admin'),registered_at='1999-01-01T00:00:00+00:00')
    with pytest.raises(ValueError,match='expired'):
        ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='expired-owner',acquired_at='1999-01-01T00:00:00+00:00',expires_at='2000-01-01T00:00:00+00:00')


def test_v0156_09_material_change_cannot_land_between_validation_and_canonical_advance(tmp_path):
    rt, bridge, store, obs, dep, cont, rec = setup(tmp_path)
    snap = dep.capture_governance_snapshot(rec.active_execution_id, created_at='2026-10-02T10:00:00+00:00')
    before = bridge.current_episode(rec.episode_id).step_count

    entered = threading.Event()
    original_advance = bridge.advance_execution

    def slow_advance(episode, observation):
        entered.set()
        time.sleep(0.15)
        return original_advance(episode, observation)

    bridge.advance_execution = slow_advance
    writer_error = []

    def writer():
        if not entered.wait(1):
            writer_error.append(RuntimeError('continuation never entered advance'))
            return
        # Separate connection models a concurrent supervisor/source process.
        s2 = trusted_store(store.path)
        o2 = ObservationService(s2)
        try:
            late = ExternalObservation(
                'race-change','src','reachability','net','sub','cfg','down',None,
                '2026-10-02T10:00:01+00:00','2026-10-02T10:00:01+00:00','2026-10-02T10:00:01+00:00',{})
            o2.submit_observation(late)
            adm = o2.assess_observation(late, assessed_at='2026-10-02T10:00:01+00:00')
            o2.commit_admission_change(late, adm, committed_at='2026-10-02T10:00:01+00:00')
        except Exception as exc:
            writer_error.append(exc)
        finally:
            s2.close()

    th = threading.Thread(target=writer, daemon=True)
    th.start()
    outcome = None
    try:
        outcome = cont.evaluate_continuation(
            active_execution_id=rec.active_execution_id,
            snapshot=snap,
            observation=ExecutionObservation('race', staged=True),
            assessed_at='2026-10-02T10:00:02+00:00')
    except ConcurrencyConflict:
        outcome = 'stale'
    th.join(2)
    assert not th.is_alive(), 'writer thread hung'
    assert not writer_error, writer_error
    after = bridge.current_episode(rec.episode_id).step_count
    # Correct behavior is serializable: either the continuation commits before the change, or it rejects before mutation.
    if outcome == 'stale':
        assert after == before
    else:
        assert outcome is not None and after == before + 1
