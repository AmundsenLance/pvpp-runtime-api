from dataclasses import replace
import pytest
from pvpp_runtime import *
from tests.test_v2_1_objective_interface_v0133 import runtime, state, objective, objectives


def base():
    rt=runtime()
    snap=rt.prepare_canonical_cycle_snapshot(state(), objectives(objective()))
    decision=rt.evaluate_canonical_decision_cycle(snap.represented_state, rt.registry.canonical_decision_request, perceived_decision_state=snap.perceived_decision_state, objectives=snap.objective_set) if hasattr(rt.registry,'canonical_decision_request') else None
    return rt,snap,decision


def minimal(rt,snap,decision=None):
    if decision is None:
        # Any real canonical assessment is acceptable replay evidence; stop-safe evidence need not execute.
        decision=CanonicalDecisionCycleAssessment('blocked','Graph/Seed',('Phi','H','G','R','Graph/Seed'))
    return rt.build_decision_replay_package(decision_episode_id='ep-1',snapshot=snap,decision=decision,stop_condition='blocked at Graph/Seed')


def test_replay_package_is_audit_carrier_not_live_state():
    rt,snap,_=base(); pkg=minimal(rt,snap)
    assert not isinstance(pkg, ActualPersistentStateEnvelope)
    assert pkg.actual_state is snap.actual_state
    assert rt.assess_replay_sufficiency(pkg).sufficient


def test_missing_actual_state_or_reference_is_insufficient():
    rt,snap,_=base(); pkg=minimal(rt,snap)
    a=rt.assess_replay_sufficiency(replace(pkg,actual_state=None,actual_state_reference=None))
    assert not a.sufficient and 'actual_state_or_reference' in a.missing_material


def test_missing_perceived_state_is_insufficient():
    rt,snap,_=base(); pkg=minimal(rt,snap)
    assert 'perceived_decision_state' in rt.assess_replay_sufficiency(replace(pkg,perceived_decision_state=None)).missing_material


def test_missing_pipeline_is_insufficient():
    rt,snap,_=base(); pkg=minimal(rt,snap)
    assert 'governing_decision_pipeline' in rt.assess_replay_sufficiency(replace(pkg,decision=None)).missing_material


def test_stop_condition_required_for_blocked_episode():
    rt,snap,_=base(); pkg=minimal(rt,snap)
    assert 'stop_condition' in rt.assess_replay_sufficiency(replace(pkg,stop_condition=None)).missing_material


def test_objective_context_preserved_by_identity_not_rewritten():
    rt,snap,_=base(); pkg=minimal(rt,snap)
    assert pkg.objective_set is snap.objective_set
    if pkg.objective_set:
        changed=replace(pkg.objective_set,version='later')
        assert changed.version != pkg.objective_set.version


def test_retrieval_disposition_survives_replay():
    rt,snap,_=base()
    gov=InformationGovernanceMetadata(disposition='rejected')
    q=RetrievalQualityMetadata(confidence=1.0)
    r=MemoryRetrievalPackage(snap.actual_state.actor_id,'r1','m1',snap.actual_state.time,{'claim':1},q,governance=gov)
    pkg=rt.build_decision_replay_package(decision_episode_id='ep',snapshot=snap,decision=CanonicalDecisionCycleAssessment('blocked','Graph/Seed',('Graph/Seed',)),retrieval=r,stop_condition='blocked')
    assert pkg.retrieval.governance.disposition=='rejected'
    assert rt.assess_replay_sufficiency(pkg).sufficient


def test_later_retrieval_is_temporal_integrity_violation():
    rt,snap,_=base(); q=RetrievalQualityMetadata(confidence=.5)
    r=MemoryRetrievalPackage(snap.actual_state.actor_id,'r1','m1',snap.actual_state.time+1,{},q)
    pkg=replace(minimal(rt,snap),retrieval=r)
    assert any('retrieval is later' in x for x in rt.assess_replay_sufficiency(pkg).violations)


def test_transfer_history_is_reference_evidence_not_substitute_for_state():
    rt,snap,_=base(); ref=TransferHistoryReference(snap.actual_state.actor_id,'h1',snap.actual_state.time)
    pkg=replace(minimal(rt,snap),transfer_history_references=(ref,),actual_state=None,actual_state_reference=None)
    assert 'actual_state_or_reference' in rt.assess_replay_sufficiency(pkg).missing_material


def test_later_transfer_history_reference_rejected():
    rt,snap,_=base(); ref=TransferHistoryReference(snap.actual_state.actor_id,'h1',snap.actual_state.time+1)
    assert any('transfer-history reference is later' in x for x in rt.assess_replay_sufficiency(replace(minimal(rt,snap),transfer_history_references=(ref,))).violations)


def test_actor_mismatch_detected():
    rt,snap,_=base(); ps=replace(snap.perceived_decision_state,actor_id='other')
    assert any('perceived state actor' in x for x in rt.assess_replay_sufficiency(replace(minimal(rt,snap),perceived_decision_state=ps)).violations)


def test_epsilon_requires_execution_license_in_replay():
    rt,snap,_=base(); ep=ExecutionEpisode('x',ExecutionLicenseEnvelope('p',(),(),(),True,True,True,True),1)
    eps=EpsilonStepResult(ep,'completed',True,False)
    assert any('execution license' in x for x in rt.assess_replay_sufficiency(replace(minimal(rt,snap),epsilon_result=eps)).violations)


def test_transition_requires_epsilon_evidence():
    rt,snap,_=base(); tr=Layer1TransitionResult('x','p',snap.actual_state.state_id,snap.actual_state,False)
    assert any('requires epsilon' in x for x in rt.assess_replay_sufficiency(replace(minimal(rt,snap),transition_result=tr)).violations)


def test_runtime_configuration_version_mismatch_detected():
    rt,snap,_=base(); cfg=RuntimeConfigurationProvenance('c','2.1','wrong',snap.actual_state.time)
    assert any('runtime version mismatch' in x for x in rt.assess_replay_sufficiency(replace(minimal(rt,snap),runtime_configuration=cfg)).violations)


def test_replay_assessment_does_not_mutate_current_state():
    rt,snap,_=base(); before=snap.actual_state
    rt.assess_replay_sufficiency(minimal(rt,snap))
    assert snap.actual_state is before


def test_source_and_rule_provenance_carried_without_authority_creation():
    rt,snap,_=base(); pkg=rt.build_decision_replay_package(decision_episode_id='ep',snapshot=snap,decision=CanonicalDecisionCycleAssessment('blocked','Graph/Seed',('Graph/Seed',)),source_snapshot_ids=('hash:a',),governing_rule_ids=('rule:v1',),stop_condition='blocked')
    assert pkg.source_snapshot_ids==('hash:a',) and pkg.governing_rule_ids==('rule:v1',)
    assert rt.assess_replay_sufficiency(pkg).sufficient


def test_temporal_provenance_preserved_without_universal_requirement():
    rt,snap,_=base(); tp=InformationTemporalProvenance(valid_time='t0',record_or_knowledge_time='t1')
    pkg=replace(minimal(rt,snap),temporal_provenance=tp)
    assert pkg.temporal_provenance is tp and rt.assess_replay_sufficiency(pkg).sufficient


def test_replay_type_validation():
    rt,snap,_=base()
    with pytest.raises(ValueError): rt.assess_replay_sufficiency(object())
