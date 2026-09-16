from dataclasses import replace
from test_prediction_error_boundary_v052 import runtime, PESvc, projection
from test_post_execution_epistemic_update_v044 import prior_actual, memory, expectation, epsilon, transition
from pvpp_runtime import *


def test_prediction_error_request_carries_exact_execution_transition_provenance():
    rt=runtime(PESvc())
    req,_,val=rt.apply_prediction_error(prior_actual(),epsilon('failed',True,True),transition(),expectation(),projection())
    p=req.execution_transition_provenance
    assert val.valid and p is not None
    assert (p.actor_id,p.episode_id,p.selected_policy_id)==(req.actor_id,req.episode_id,req.selected_policy_id)
    assert (p.prior_state_id,p.next_state_id)==(req.prior_actual_state_id,req.next_actual_state_id)
    assert p.execution_status==req.execution_status and p.execution_path==req.execution_path


def test_prediction_error_rejects_spliced_provenance():
    rt=runtime(PESvc())
    req=rt.build_prediction_error_request(prior_actual(),epsilon(),transition(),expectation(),projection())
    bad=replace(req,execution_transition_provenance=replace(req.execution_transition_provenance,episode_id='other'))
    res=PredictionErrorAssessment(req.actor_id,req.episode_id,req.selected_policy_id,(),False)
    val=rt.validate_prediction_error_assessment(bad,res)
    assert not val.valid and any('provenance attribution' in x for x in val.violations)


def test_epistemic_update_request_carries_same_transition_provenance_basis():
    rt=runtime()
    req=rt.build_post_execution_epistemic_update_request(prior_actual(),epsilon(),transition(),memory(),expectation())
    p=req.execution_transition_provenance
    assert p is not None and p.episode_id==req.episode_id and p.selected_policy_id==req.selected_policy_id
    assert p.next_state_id==req.next_actual_state_id


def test_epistemic_update_rejects_spliced_execution_provenance():
    rt=runtime()
    req=rt.build_post_execution_epistemic_update_request(prior_actual(),epsilon(),transition(),memory(),expectation())
    req=replace(req,execution_transition_provenance=replace(req.execution_transition_provenance,next_state_id='stale'))
    res=PostExecutionEpistemicUpdateResult(req.actor_id,req.episode_id,req.prior_memory_state,req.prior_expectation_state,False,False)
    val=rt.validate_post_execution_epistemic_update_result(req,res)
    assert not val.valid and any('state identity' in x for x in val.violations)


def test_realized_pv_and_execution_information_remain_exact_epsilon_evidence():
    rt=runtime()
    ep=epsilon()
    req=rt.build_post_execution_epistemic_update_request(prior_actual(),ep,transition(),memory(),expectation())
    assert req.realized_pv_bundles==tuple(dict(x) for x in ep.realized_pv_bundles)
    assert req.execution_information==tuple(dict(x) for x in ep.information_events)


def test_provenance_does_not_create_learning_rule_or_scalar_error():
    rt=runtime(PESvc())
    req,res,val=rt.apply_prediction_error(prior_actual(),epsilon(),transition(),expectation(),projection())
    assert val.valid and not hasattr(req.execution_transition_provenance,'learning_rate')
    assert not hasattr(req.execution_transition_provenance,'error_score') and not hasattr(res,'score')


def test_prediction_error_attribution_must_match_epistemic_update_provenance():
    rt=runtime()
    pe=PredictionErrorAssessment('actor','wrong-episode','policy',(),False)
    req=rt.build_post_execution_epistemic_update_request(prior_actual(),epsilon(),transition(),memory(),expectation(),prediction_error=pe)
    res=PostExecutionEpistemicUpdateResult(req.actor_id,req.episode_id,req.prior_memory_state,req.prior_expectation_state,False,False)
    val=rt.validate_post_execution_epistemic_update_result(req,res)
    assert not val.valid and any('prediction error attribution' in x for x in val.violations)


def test_absent_provenance_fails_closed_on_direct_validation():
    rt=runtime(PESvc())
    req=rt.build_prediction_error_request(prior_actual(),epsilon(),transition(),expectation(),projection())
    req=replace(req,execution_transition_provenance=None)
    res=PredictionErrorAssessment(req.actor_id,req.episode_id,req.selected_policy_id,(),False)
    val=rt.validate_prediction_error_assessment(req,res)
    assert not val.valid and any('requires execution-transition provenance' in x for x in val.violations)
