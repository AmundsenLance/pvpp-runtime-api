import sys
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_projection_service_v036 import build, Service, req, state


def completed():
    rt,_=build(Service())
    out=rt.evaluate_canonical_decision_cycle(state(),req())
    return rt,out


def test_completed_cycle_has_valid_identity_integrity_audit():
    _,out=completed()
    a=out.cycle_artifact_integrity
    assert a is not None and a.valid
    assert a.state_id=='s0' and a.state_time==0.0
    assert a.candidate_policy_ids==('graph:cont','graph:adj')
    assert set(a.feasible_policy_ids)==set(a.projection_policy_ids)==set(a.adequacy_policy_ids)


def test_stale_q_state_identity_is_detected():
    rt,out=completed()
    badrec=replace(out.projection_records[0],state_id='older-state')
    bad=replace(out,projection_records=(badrec,)+out.projection_records[1:])
    a=rt.audit_cycle_artifact_integrity(bad,expected_state_id='s0',expected_state_time=0.0)
    assert not a.valid
    assert any('Q state_id' in x for x in a.violations)


def test_stale_q_state_time_is_detected():
    rt,out=completed()
    badrec=replace(out.projection_records[0],state_time=-1.0)
    bad=replace(out,projection_records=(badrec,)+out.projection_records[1:])
    a=rt.audit_cycle_artifact_integrity(bad,expected_state_id='s0',expected_state_time=0.0)
    assert not a.valid
    assert any('Q state_time' in x for x in a.violations)


def test_constraints_cannot_carry_prior_pi_candidate_set():
    rt,out=completed()
    bad_constraints=replace(out.constraints,candidate_results=out.constraints.candidate_results[:1])
    a=rt.audit_cycle_artifact_integrity(replace(out,constraints=bad_constraints),expected_state_id='s0',expected_state_time=0.0)
    assert not a.valid
    assert any('Constraints candidate identity' in x for x in a.violations)


def test_graph_pi_and_framing_must_share_current_governing_identity():
    rt,out=completed()
    bad_graph=replace(out.graph_assessment,governing_domain_ids=('OLD',))
    a=rt.audit_cycle_artifact_integrity(replace(out,graph_assessment=bad_graph),expected_state_id='s0',expected_state_time=0.0)
    assert not a.valid and any('Graph governing-domain' in x for x in a.violations)
    bad_frame=replace(out.domain_framing,governing_domain_ids=('OLD',))
    a=rt.audit_cycle_artifact_integrity(replace(out,domain_framing=bad_frame),expected_state_id='s0',expected_state_time=0.0)
    assert not a.valid and any('Domain Framing governing identity' in x for x in a.violations)


def test_projection_and_adequacy_policy_sets_cannot_be_spliced_from_other_cycle():
    rt,out=completed()
    bad=replace(out,projection_records=out.projection_records[:1])
    a=rt.audit_cycle_artifact_integrity(bad,expected_state_id='s0',expected_state_time=0.0)
    assert not a.valid and any('Q policy set' in x for x in a.violations)
    bad_adequacy=replace(out.adequacy,policy_results=out.adequacy.policy_results[:1])
    a=rt.audit_cycle_artifact_integrity(replace(out,adequacy=bad_adequacy),expected_state_id='s0',expected_state_time=0.0)
    assert not a.valid and any('Adequacy policy identity' in x for x in a.violations)


def test_execution_license_reaudits_instead_of_trusting_stored_valid_flag():
    rt,out=completed()
    assert out.cycle_artifact_integrity.valid
    bad_constraints=replace(out.constraints,candidate_results=out.constraints.candidate_results[:1])
    tampered=replace(out,constraints=bad_constraints)
    try:
        rt.build_execution_license_from_cycle(tampered,req().domain_frame)
        assert False
    except ValueError as e:
        assert 'stale or identity-inconsistent cycle artifacts' in str(e)


def test_audit_does_not_invent_semantic_freshness_timeout():
    rt,out=completed()
    # Time age by itself is not judged stale. The audit only verifies identity consistency
    # against the explicitly supplied expected decision-time identity.
    a=rt.audit_cycle_artifact_integrity(out,expected_state_id='s0',expected_state_time=0.0)
    assert a.valid
    assert 'no persistence, freshness timeout' in a.notes[0]
