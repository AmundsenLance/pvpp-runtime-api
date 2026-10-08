import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_v2_horizon_reentry_v097 import setup_case as setup_h


def setup_case():
    rt,w,ts,st,req,o,_,_,_,hi,ginput,ri,gi,pi=setup_h()
    sig=GovernanceInvalidationSignal('phi98','Phi','pressure evidence changed','epistemic')
    p=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    b=GovernanceReusableArtifactBundle('b98','c98','s98','cfg98',tuple((s,o.pressure_field) for s in p.reusable_upstream_stages))
    ba=validate_reusable_artifact_bundle(p,b,expected_cycle_id='c98',expected_initial_state_id='s98',expected_configuration_id='cfg98')
    fi=PhiReusableEvaluationInputs(hi.perceived_state,hi.baseline_state,rt.registry.phi_substrate_identity())
    return rt,w,ts,st,req,o,p,b,ba,fi,hi,ginput,ri,gi,pi


def test_v098_phi_reentry_runs_downstream_and_matches_control():
    rt,w,ts,st,req,o,p,b,ba,fi,hi,ginput,ri,gi,pi=setup_case(); c=len(w.constraint_calls); q=len(w.q_calls)
    x=execute_phi_reentry(rt,p,b,ba,st,req,fi,hi,ginput,ri,gi,pi)
    assert x.valid and x.status=='reentry_pass_completed' and x.recomputed_stage_ids[:3]==('Phi','H','G')
    assert x.decision.selection.selected_policy_id==o.selection.selected_policy_id
    assert len(w.constraint_calls)>c and len(w.q_calls)>q and len(ts.handoffs)==0


def test_v098_phi_reruns_host_mapping_on_captured_state():
    rt,w,ts,st,req,o,p,b,ba,fi,hi,ginput,ri,gi,pi=setup_case(); calls=[]; old=w.pressure_factors
    def counted(state,did,drift): calls.append((state,did,drift)); return old(state,did,drift)
    w.pressure_factors=counted
    x=execute_phi_reentry(rt,p,b,ba,st,req,fi,hi,ginput,ri,gi,pi)
    assert x.valid and len(calls)==len(rt.registry.domains)
    assert all(state==fi.perceived_state for state,_,_ in calls)


def test_v098_phi_substrate_identity_is_deterministic():
    rt,*_=setup_case(); assert rt.registry.phi_substrate_identity()==rt.registry.phi_substrate_identity()


def test_v098_changed_domain_substrate_fails_closed():
    rt,w,ts,st,req,o,p,b,ba,fi,hi,ginput,ri,gi,pi=setup_case()
    did=next(iter(rt.registry.domains)); d=rt.registry.domains[did]
    from dataclasses import replace
    rt.registry.domains[did]=replace(d,threshold=d.threshold+0.001)
    x=execute_phi_reentry(rt,p,b,ba,st,req,fi,hi,ginput,ri,gi,pi)
    assert not x.valid and any('Phi domain substrate identity changed' in v for v in x.violations)


def test_v098_phi_h_state_boundary_mismatch_fails_closed():
    rt,w,ts,st,req,o,p,b,ba,fi,hi,ginput,ri,gi,pi=setup_case()
    from dataclasses import replace
    badhi=replace(hi,baseline_state=st)
    x=execute_phi_reentry(rt,p,b,ba,st,req,fi,badhi,ginput,ri,gi,pi)
    assert not x.valid and any('baseline-state payloads do not match' in v for v in x.violations)


def test_v098_wrong_boundary_and_invalid_bundle_fail_closed():
    rt,w,ts,st,req,o,p,b,ba,fi,hi,ginput,ri,gi,pi=setup_case()
    bad=GovernanceReentryPlan(True,'H',p.reusable_upstream_stages,p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids)
    assert not execute_phi_reentry(rt,bad,b,ba,st,req,fi,hi,ginput,ri,gi,pi).valid
    badba=GovernanceReusableArtifactBundleAssessment(False,b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,p.reusable_upstream_stages,('bad',),())
    assert not execute_phi_reentry(rt,p,b,badba,st,req,fi,hi,ginput,ri,gi,pi).valid


def test_v098_no_epsilon_and_reusable_identity_preserved():
    rt,w,ts,st,req,o,p,b,ba,fi,hi,ginput,ri,gi,pi=setup_case(); x=execute_phi_reentry(rt,p,b,ba,st,req,fi,hi,ginput,ri,gi,pi)
    assert 'epsilon' not in x.recomputed_stage_ids and x.reused_stage_ids==p.reusable_upstream_stages and len(ts.handoffs)==0
