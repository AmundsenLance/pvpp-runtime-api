import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_v2_phi_reentry_v098 import setup_case as setup_phi


def setup_case():
    rt,w,ts,st,req,o,_,_,_,fi,hi,ginput,ri,gi,pi=setup_phi()
    # The fixture's represented WorldState uses s0; create the authoritative opaque
    # actual-state envelope whose host mapping produces that same decision state.
    actual=ActualPersistentStateEnvelope('actor','s98',st.time,{'pp':'opaque'},{'spv':'opaque'},{'avs':'opaque'},{'x':'opaque'})
    # Existing fixture adapter has no actual->P_i mapper. Add the ordinary typed boundary.
    calls=[]
    def mapper(a):
        calls.append(a.state_id)
        return PerceivedDecisionState(a.actor_id,a.state_id,a.time,st,ppp={'fresh':len(calls)},metadata={'source':'v099-test'})
    w.perceived_decision_state_from_actual=mapper
    sig=GovernanceInvalidationSignal('ppp99','PPP','perception evidence invalidated','epistemic')
    p=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    b=GovernanceReusableArtifactBundle('b99','c99','s98','cfg99',())
    ba=validate_reusable_artifact_bundle(p,b,expected_cycle_id='c99',expected_initial_state_id='s98',expected_configuration_id='cfg99')
    return rt,w,ts,st,actual,req,o,p,b,ba,PPPReentryInputs(actual),hi,ginput,ri,gi,pi,calls


def test_v099_ppp_reentry_reacquires_perception_and_runs_downstream():
    rt,w,ts,st,a,req,o,p,b,ba,pppi,hi,g,ri,gi,pi,calls=setup_case()
    x=execute_ppp_reentry(rt,p,b,ba,req,pppi,hi,g,ri,gi,pi)
    assert x.valid and x.status=='reentry_pass_completed'
    assert x.recomputed_stage_ids[:3]==('PPP','Phi','H')
    assert calls==['s98'] and x.decision.selection.selected_policy_id==o.selection.selected_policy_id
    assert len(ts.handoffs)==0


def test_v099_old_represented_state_is_not_used_as_perception_authority():
    rt,w,ts,st,a,req,o,p,b,ba,pppi,hi,g,ri,gi,pi,calls=setup_case()
    old=hi.perceived_state
    def mapper(actual):
        calls.append(actual.state_id)
        # fresh object, same values; metadata proves fresh host mapping occurred
        fresh=WorldState(old.time,dict(old.powers),{**dict(old.metadata),'fresh_ppp':True})
        return PerceivedDecisionState(actual.actor_id,actual.state_id,actual.time,fresh,ppp={'fresh':True})
    w.perceived_decision_state_from_actual=mapper
    seen=[]; old_pf=w.pressure_factors
    def pf(state,did,drift):
        seen.append(state.metadata.get('fresh_ppp')); return old_pf(state,did,drift)
    w.pressure_factors=pf
    x=execute_ppp_reentry(rt,p,b,ba,req,pppi,hi,g,ri,gi,pi)
    assert x.valid and calls==['s98'] and seen and all(v is True for v in seen)


def test_v099_actual_state_identity_mismatch_fails_before_perception():
    rt,w,ts,st,a,req,o,p,b,ba,pppi,hi,g,ri,gi,pi,calls=setup_case()
    bad=ActualPersistentStateEnvelope(a.actor_id,'wrong',a.time,a.pp,a.spv,a.avs,a.context)
    x=execute_ppp_reentry(rt,p,b,ba,req,PPPReentryInputs(bad),hi,g,ri,gi,pi)
    assert not x.valid and calls==[] and any('actual-state identity' in v for v in x.violations)


def test_v099_invalid_host_perception_fails_closed():
    rt,w,ts,st,a,req,o,p,b,ba,pppi,hi,g,ri,gi,pi,calls=setup_case()
    def bad(actual):
        calls.append(actual.state_id)
        return PerceivedDecisionState(actual.actor_id,'wrong',actual.time,st,ppp={'x':1})
    w.perceived_decision_state_from_actual=bad
    x=execute_ppp_reentry(rt,p,b,ba,req,pppi,hi,g,ri,gi,pi)
    assert not x.valid and x.status=='ppp_reentry_not_executable' and calls==['s98']


def test_v099_wrong_boundary_and_invalid_bundle_fail_before_perception():
    rt,w,ts,st,a,req,o,p,b,ba,pppi,hi,g,ri,gi,pi,calls=setup_case()
    badp=GovernanceReentryPlan(True,'Phi',(),p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids)
    assert not execute_ppp_reentry(rt,badp,b,ba,req,pppi,hi,g,ri,gi,pi).valid
    badba=GovernanceReusableArtifactBundleAssessment(False,b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,(),('bad',),())
    assert not execute_ppp_reentry(rt,p,b,badba,req,pppi,hi,g,ri,gi,pi).valid
    assert calls==[]


def test_v099_ppp_plan_may_not_claim_upstream_reuse():
    rt,w,ts,st,a,req,o,p,b,ba,pppi,hi,g,ri,gi,pi,calls=setup_case()
    badp=GovernanceReentryPlan(True,'PPP',('PPP',),p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids)
    badba=GovernanceReusableArtifactBundleAssessment(True,b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,('PPP',),(),())
    x=execute_ppp_reentry(rt,badp,b,badba,req,pppi,hi,g,ri,gi,pi)
    assert not x.valid and calls==[] and any('may not claim reusable' in v for v in x.violations)


def test_v099_no_epsilon_or_layer1_transition():
    rt,w,ts,st,a,req,o,p,b,ba,pppi,hi,g,ri,gi,pi,calls=setup_case()
    x=execute_ppp_reentry(rt,p,b,ba,req,pppi,hi,g,ri,gi,pi)
    assert x.valid and 'epsilon' not in x.recomputed_stage_ids and x.reused_stage_ids==() and len(ts.handoffs)==0
