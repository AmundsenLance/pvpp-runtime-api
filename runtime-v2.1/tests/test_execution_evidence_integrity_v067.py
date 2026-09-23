from dataclasses import replace
from test_prediction_error_boundary_v052 import runtime, PESvc, projection
from test_post_execution_epistemic_update_v044 import prior_actual, memory, expectation, epsilon, transition
from pvpp_runtime import PredictionErrorAssessment, PostExecutionEpistemicUpdateResult


def test_prediction_error_rejects_spliced_realized_pv_evidence():
    rt=runtime(PESvc())
    req=rt.build_prediction_error_request(prior_actual(),epsilon(),transition(),expectation(),projection())
    bad=replace(req,realized_pv_bundles=({"pv":"tampered"},))
    assessment=PredictionErrorAssessment(req.actor_id,req.episode_id,req.selected_policy_id,(),False)
    validation=rt.validate_prediction_error_assessment(bad,assessment)
    assert not validation.valid
    assert any("realized-PV evidence" in x for x in validation.violations)


def test_prediction_error_rejects_spliced_execution_information():
    rt=runtime(PESvc())
    req=rt.build_prediction_error_request(prior_actual(),epsilon(),transition(),expectation(),projection())
    bad=replace(req,execution_information=({"info":"tampered"},))
    assessment=PredictionErrorAssessment(req.actor_id,req.episode_id,req.selected_policy_id,(),False)
    validation=rt.validate_prediction_error_assessment(bad,assessment)
    assert not validation.valid
    assert any("execution-information evidence" in x for x in validation.violations)


def test_epistemic_update_rejects_spliced_execution_information():
    rt=runtime()
    req=rt.build_post_execution_epistemic_update_request(prior_actual(),epsilon(),transition(),memory(),expectation())
    bad=replace(req,execution_information=({"info":"tampered"},))
    result=PostExecutionEpistemicUpdateResult(req.actor_id,req.episode_id,req.prior_memory_state,req.prior_expectation_state,False,False)
    validation=rt.validate_post_execution_epistemic_update_result(bad,result)
    assert not validation.valid
    assert any("execution-information evidence" in x for x in validation.violations)


def test_epistemic_update_rejects_spliced_realized_pv_evidence():
    rt=runtime()
    req=rt.build_post_execution_epistemic_update_request(prior_actual(),epsilon(),transition(),memory(),expectation())
    bad=replace(req,realized_pv_bundles=({"pv":"tampered"},))
    result=PostExecutionEpistemicUpdateResult(req.actor_id,req.episode_id,req.prior_memory_state,req.prior_expectation_state,False,False)
    validation=rt.validate_post_execution_epistemic_update_result(bad,result)
    assert not validation.valid
    assert any("realized-PV evidence" in x for x in validation.violations)


def test_execution_provenance_carries_evidence_signatures_and_return_posture():
    rt=runtime(PESvc())
    req=rt.build_prediction_error_request(prior_actual(),epsilon(),transition(),expectation(),projection())
    prov=req.execution_transition_provenance
    assert prov.realized_pv_evidence_signature == rt._execution_evidence_signature(tuple(req.realized_pv_bundles))
    assert prov.execution_information_signature == rt._execution_evidence_signature(tuple(req.execution_information))
    assert prov.return_upstream == req.return_upstream


def test_prediction_error_rejects_spliced_return_upstream_posture():
    rt=runtime(PESvc())
    req=rt.build_prediction_error_request(prior_actual(),epsilon(),transition(),expectation(),projection())
    bad=replace(req,return_upstream=not req.return_upstream)
    assessment=PredictionErrorAssessment(req.actor_id,req.episode_id,req.selected_policy_id,(),False)
    validation=rt.validate_prediction_error_assessment(bad,assessment)
    assert not validation.valid
    assert any("return-upstream posture" in x for x in validation.violations)


def test_nested_evidence_mutation_after_request_build_is_detected():
    rt=runtime(PESvc())
    req=rt.build_prediction_error_request(prior_actual(),epsilon(),transition(),expectation(),projection())
    if req.realized_pv_bundles:
        req.realized_pv_bundles[0]["post_build_mutation"]="changed"
        assessment=PredictionErrorAssessment(req.actor_id,req.episode_id,req.selected_policy_id,(),False)
        validation=rt.validate_prediction_error_assessment(req,assessment)
        assert not validation.valid
        assert any("realized-PV evidence" in x for x in validation.violations)
