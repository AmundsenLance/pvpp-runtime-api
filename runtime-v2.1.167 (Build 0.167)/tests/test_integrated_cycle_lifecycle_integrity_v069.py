from dataclasses import replace
from pvpp_runtime.models import *
from test_cross_object_execution_identity_v068 import _chain


def test_complete_transition_chain_passes_lifecycle_audit():
    rt,i,_,_,_=_chain()
    a=rt.audit_integrated_cycle_lifecycle_integrity(i)
    assert a.valid, a.violations


def test_partial_execution_cannot_be_spliced_with_transition_handoff():
    rt,i,_,_,_=_chain()
    active_eps=replace(i.epsilon_result, terminal=False, status='active', return_upstream=False)
    bad=replace(i,status='integrated_cycle_execution_active',epsilon_result=active_eps)
    a=rt.audit_integrated_cycle_lifecycle_integrity(bad)
    assert not a.valid
    assert any('transition artifacts' in x for x in a.violations)


def test_transition_cannot_follow_nonterminal_epsilon():
    rt,i,_,_,_=_chain()
    bad=replace(i,epsilon_result=replace(i.epsilon_result,terminal=False,status='active'))
    a=rt.audit_integrated_cycle_lifecycle_integrity(bad)
    assert not a.valid
    assert any('terminal epsilon' in x for x in a.violations)


def test_final_state_splice_is_detected():
    rt,i,_,_,_=_chain()
    final=replace(i.final_actual_state,state_id='stale-next')
    a=rt.audit_integrated_cycle_lifecycle_integrity(replace(i,final_actual_state=final))
    assert not a.valid
    assert any('final actual state' in x for x in a.violations)


def test_prior_state_splice_is_detected():
    rt,i,_,_,_=_chain()
    badtr=replace(i.transition_result,prior_state_id='other-prior')
    a=rt.audit_integrated_cycle_lifecycle_integrity(replace(i,transition_result=badtr))
    assert not a.valid
    assert any('prior_state_id' in x for x in a.violations)


def test_selected_not_executed_cannot_carry_stale_license():
    rt,i,_,_,_=_chain()
    a=rt.audit_integrated_cycle_lifecycle_integrity(replace(i,status='integrated_cycle_selected_not_executed'))
    assert not a.valid


def test_blocked_execution_cannot_carry_stale_transition():
    rt,i,_,_,_=_chain()
    bad=replace(i,status='integrated_cycle_execution_blocked')
    a=rt.audit_integrated_cycle_lifecycle_integrity(bad)
    assert not a.valid


def test_lifecycle_audit_is_diagnostic_only():
    rt,i,_,_,_=_chain()
    before=i
    a=rt.audit_integrated_cycle_lifecycle_integrity(i)
    assert a.valid and i==before
