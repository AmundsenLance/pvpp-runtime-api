from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
import pytest
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.observation import SourceRegistration
from pvpp_runtime.supervision.store import ConcurrencyConflict
from test_r22_phase6_control import prepared
from pvpp_runtime import ExecutionObservation

def setup7(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    eff=EffectService(store,obs)
    register_test_source(obs, SourceRegistration('sr-eff','ledger',('effect',),('world_effect',),(),('cfg',),('effect_reconciliation',),'signed',None,None,'current','admin',1))
    return rt,store,obs,ctl,rec,eff

def terminalize(ctl,rec,at='2026-10-02T10:30:00+00:00'):
    dep=ctl.dependencies; cont=ctl.continuation
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at=at)
    return cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('terminal',continuation_sufficient=False),assessed_at=at)

def test_unregistered_effect_source_cannot_establish_effect(tmp_path):
    *_,rec,eff=setup7(tmp_path)
    with pytest.raises(ValueError,match='evidence_unverified'):
        eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='self-declared',configuration_id='cfg',state='completed_effect',realized_bundle_ref='b',evidence_ref='e',provenance='p',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')

def test_authoritative_effect_evidence_reconciles(tmp_path):
    *_,rec,eff=setup7(tmp_path)
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='bundle',evidence_ref='ledger:1',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    s=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00')
    assert s.state=='completed_effect' and not s.unresolved and s.authoritative_source_refs==('ledger',)

def test_unknown_effect_remains_unresolved(tmp_path):
    *_,rec,eff=setup7(tmp_path)
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='effect_unknown',realized_bundle_ref=None,evidence_ref='ledger:unknown',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    assert eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00').unresolved

def test_canonical_finality_accept_once(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path); term=terminalize(ctl,rec)
    f=eff.accept_canonical_finality(active_execution_id=rec.active_execution_id,continuation_assessment_id=term.assessment_id,terminalized_at='2026-10-02T10:00:00+00:00')
    assert f.immutable
    with pytest.raises(ConcurrencyConflict,match='canonical_finality_conflict'):
        eff.accept_canonical_finality(active_execution_id=rec.active_execution_id,continuation_assessment_id=term.assessment_id,terminalized_at='2026-10-02T10:00:00+00:00')

def test_late_effect_does_not_rewrite_finality(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path); term=terminalize(ctl,rec)
    f=eff.accept_canonical_finality(active_execution_id=rec.active_execution_id,continuation_assessment_id=term.assessment_id,terminalized_at='2026-10-02T10:00:00+00:00')
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='bundle',evidence_ref='late',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    s=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00')
    assert s.canonical_finality_ref==f.canonical_finality_id
    assert eff.get_canonical_finality(rec.active_execution_id)==f

def test_enforcement_completed_is_not_effect_evidence(tmp_path):
    rt,store,obs,ctl,rec,eff=setup7(tmp_path)
    assert eff.current_effect_state(rec.active_execution_id).state=='open'

def test_retry_blocked_while_effect_unresolved_without_preexisting_contract(tmp_path):
    *_,rec,eff=setup7(tmp_path)
    with pytest.raises(ValueError,match='effect_unresolved'): eff.assert_retry_safe(active_execution_id=rec.active_execution_id)

def test_preexisting_idempotency_contract_can_establish_retry_safety(tmp_path):
    *_,rec,eff=setup7(tmp_path)
    eff.register_retry_contract(active_execution_id=rec.active_execution_id,idempotent=True,reconciliation_required=True,registered_at='2026-10-02T10:00:00+00:00')
    assert eff.assert_retry_safe(active_execution_id=rec.active_execution_id)

def test_layer1_requires_host_authority_and_current_effect_state(tmp_path):
    *_,rec,eff=setup7(tmp_path)
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='bundle',evidence_ref='e',provenance='p',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    s=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ValueError,match='host-authoritative'): eff.record_layer1_transition(active_execution_id=rec.active_execution_id,effect_reconciliation_ref=s.effect_record_id,prior_actual_state_ref='a',next_actual_state_ref='b',transition_time='2026-10-02T10:00:00+00:00',evidence_ref='h',provenance='host',configuration_id='cfg',authority_evidence='bad')
    t=eff.record_layer1_transition(active_execution_id=rec.active_execution_id,effect_reconciliation_ref=s.effect_record_id,prior_actual_state_ref='a',next_actual_state_ref='b',transition_time='2026-10-02T10:00:00+00:00',evidence_ref='h',provenance='host',configuration_id='cfg',authority_evidence='signed:layer1')
    assert t.next_actual_state_ref=='b'

def test_compensation_reference_does_not_erase_original_effect(tmp_path):
    *_,rec,eff=setup7(tmp_path)
    e=eff.submit_effect_evidence(active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',state='partial_effect',realized_bundle_ref='original',evidence_ref='e',provenance='p',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
    s=eff.reconcile_effect(active_execution_id=rec.active_execution_id,effect_evidence_id=e.effect_evidence_id,updated_at='2026-10-02T10:00:00+00:00',compensation_refs=('separate-action-C',))
    assert s.realized_bundle_ref=='original' and s.compensation_refs==('separate-action-C',)
