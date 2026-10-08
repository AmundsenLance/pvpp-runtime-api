import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_v2_governing_reentry_v096 import setup_case as setup_g


def setup_case():
    rt,w,ts,st,req,o,_,_,_,ginput,ri,gi,pi=setup_g()
    sig=GovernanceInvalidationSignal('h97','H','expected deterioration evidence changed','epistemic')
    p=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    arts={'PPP':o.pressure_field,'Phi':o.pressure_field}
    b=GovernanceReusableArtifactBundle('b97','c97','s97','cfg97',tuple((s,arts[s]) for s in p.reusable_upstream_stages))
    ba=validate_reusable_artifact_bundle(p,b,expected_cycle_id='c97',expected_initial_state_id='s97',expected_configuration_id='cfg97')
    perceived=w.perceive(st); baseline=rt._baseline_continuation(perceived)
    hi=HorizonReusableEvaluationInputs(perceived,baseline,rt.registry.horizon_configuration_identity())
    return rt,w,ts,st,req,o,p,b,ba,hi,ginput,ri,gi,pi


def test_v097_h_reentry_runs_downstream_and_matches_control():
    rt,w,ts,st,req,o,p,b,ba,hi,ginput,ri,gi,pi=setup_case(); c=len(w.constraint_calls); q=len(w.q_calls)
    x=execute_horizon_reentry(rt,p,b,ba,st,req,hi,ginput,ri,gi,pi)
    assert x.valid and x.status=='reentry_pass_completed' and x.recomputed_stage_ids[:3]==('H','G','R')
    assert x.decision.selection.selected_policy_id==o.selection.selected_policy_id
    assert len(w.constraint_calls)>c and len(w.q_calls)>q and len(ts.handoffs)==0


def test_v097_h_reuses_captured_phi_drift_and_calls_expected_deterioration():
    rt,w,ts,st,req,o,p,b,ba,hi,ginput,ri,gi,pi=setup_case()
    old=w.expected_deterioration; calls=[]
    def counted(state,did,drift,pressure,factors):
        calls.append((state,did,drift,pressure,factors))
        return old(state,did,drift,pressure,factors)
    w.expected_deterioration=counted
    x=execute_horizon_reentry(rt,p,b,ba,st,req,hi,ginput,ri,gi,pi)
    assert x.valid and len(calls)==len(rt.registry.domains)
    pby={r.domain_id:r for r in o.pressure_field.domain_results}
    assert all(drift==pby[did].factors.local_trajectory for _,did,drift,_,_ in calls)


def test_v097_horizon_configuration_identity_is_deterministic():
    rt,*_=setup_case(); assert rt.registry.horizon_configuration_identity()==rt.registry.horizon_configuration_identity()


def test_v097_changed_h_configuration_fails_closed():
    rt,w,ts,st,req,o,p,b,ba,hi,ginput,ri,gi,pi=setup_case()
    rt.registry.horizon_configuration=HorizonConfiguration(epsilon_deterioration=1e-6)
    x=execute_horizon_reentry(rt,p,b,ba,st,req,hi,ginput,ri,gi,pi)
    assert not x.valid and any('H configuration identity changed' in v for v in x.violations)


def test_v097_fresh_horizon_replaces_stale_downstream_horizon_field():
    rt,w,ts,st,req,o,p,b,ba,hi,ginput,ri,gi,pi=setup_case()
    ds=tuple(DomainAssessment(x.domain_id,x.perceived_value,x.pressure,x.horizon+999,x.governing,x.threshold) for x in ri.domain_assessments)
    stale=RegimeReusableClassificationInputs(ds,ri.contextual_interruption,ri.previous_regime,ri.regime_configuration_identity)
    x=execute_horizon_reentry(rt,p,b,ba,st,req,hi,ginput,stale,gi,pi)
    assert x.valid and x.recomputed_stage_ids[:3]==('H','G','R')
    assert x.decision.selection.selected_policy_id==o.selection.selected_policy_id


def test_v097_wrong_boundary_and_invalid_bundle_fail_closed():
    rt,w,ts,st,req,o,p,b,ba,hi,ginput,ri,gi,pi=setup_case()
    bad=GovernanceReentryPlan(True,'G',p.reusable_upstream_stages,p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids)
    assert not execute_horizon_reentry(rt,bad,b,ba,st,req,hi,ginput,ri,gi,pi).valid
    badba=GovernanceReusableArtifactBundleAssessment(False,b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,p.reusable_upstream_stages,('bad',),())
    assert not execute_horizon_reentry(rt,p,b,badba,st,req,hi,ginput,ri,gi,pi).valid


def test_v097_no_epsilon_and_reusable_identity_preserved():
    rt,w,ts,st,req,o,p,b,ba,hi,ginput,ri,gi,pi=setup_case(); x=execute_horizon_reentry(rt,p,b,ba,st,req,hi,ginput,ri,gi,pi)
    assert 'epsilon' not in x.recomputed_stage_ids and x.reused_stage_ids==p.reusable_upstream_stages and len(ts.handoffs)==0
