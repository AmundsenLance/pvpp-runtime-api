from dataclasses import replace
from pvpp_runtime.models import *
from pvpp_runtime.kernel import PVPPRuntime
from test_prediction_error_boundary_v052 import runtime
from test_post_execution_epistemic_update_v044 import prior_actual, memory, epsilon, transition


def _chain():
    rt=runtime()
    prior=prior_actual(); eps=epsilon(); tr=transition()
    hand=rt.build_layer1_transition_handoff(eps)
    tv=rt.validate_layer1_transition_result(prior,hand,tr)
    prov=rt.build_execution_transition_provenance(prior,hand,tr,tv)
    integrated=CanonicalIntegratedCycleResult(
        prior.state_id, decision=None, execution_license=eps.episode.license,
        epsilon_result=eps, handoff=hand, transition_result=tr,
        transition_validation=tv, final_actual_state=tr.next_state,
        status='executed', transition_provenance=prov)
    pe_req=rt.build_prediction_error_request(prior,eps,tr)
    pe=PredictionErrorAssessment(pe_req.actor_id,pe_req.episode_id,pe_req.selected_policy_id,(),False)
    mem=MemoryStateReference(prior.actor_id,'m0',prior.time,{})
    eu=rt.build_post_execution_epistemic_update_request(prior,eps,tr,mem,prediction_error=pe)
    return rt,integrated,pe_req,pe,eu


def test_clean_chain_passes():
    rt,i,pr,pa,eu=_chain()
    a=rt.audit_post_selection_identity_chain(i,pr,pa,eu)
    assert a.valid, a.violations


def test_spliced_license_policy_fails():
    rt,i,pr,pa,eu=_chain()
    badlic=replace(i.execution_license, selected_policy_id='other')
    a=rt.audit_post_selection_identity_chain(replace(i,execution_license=badlic),pr,pa,eu)
    assert not a.valid
    assert any('policy identity' in x for x in a.violations)


def test_spliced_action_authority_fails():
    rt,i,pr,pa,eu=_chain()
    badlic=replace(i.execution_license, action_ids=('other_action',))
    a=rt.audit_post_selection_identity_chain(replace(i,execution_license=badlic),pr,pa,eu)
    assert not a.valid
    assert any('action authority' in x for x in a.violations)


def test_spliced_transition_provenance_fails():
    rt,i,pr,pa,eu=_chain()
    badprov=replace(i.transition_provenance, episode_id='other-episode')
    a=rt.audit_post_selection_identity_chain(replace(i,transition_provenance=badprov),pr,pa,eu)
    assert not a.valid


def test_prediction_error_request_from_other_episode_fails():
    rt,i,pr,pa,eu=_chain()
    bad=replace(pr,episode_id='other-episode')
    a=rt.audit_post_selection_identity_chain(i,bad,pa,eu)
    assert not a.valid


def test_prediction_error_assessment_request_mismatch_fails():
    rt,i,pr,pa,eu=_chain()
    bad=replace(pa,selected_policy_id='other')
    a=rt.audit_post_selection_identity_chain(i,pr,bad,eu)
    assert not a.valid


def test_epistemic_update_requires_exact_audited_prediction_error_object():
    rt,i,pr,pa,eu=_chain()
    clone=replace(pa)
    eu2=replace(eu,prediction_error=clone)
    a=rt.audit_post_selection_identity_chain(i,pr,pa,eu2)
    assert not a.valid
    assert any('exact audited prediction-error assessment object' in x for x in a.violations)


def test_audit_is_diagnostic_only():
    rt,i,pr,pa,eu=_chain()
    before=(i.transition_provenance,eu.prediction_error)
    a=rt.audit_post_selection_identity_chain(i,pr,pa,eu)
    after=(i.transition_provenance,eu.prediction_error)
    assert a.valid and before==after
