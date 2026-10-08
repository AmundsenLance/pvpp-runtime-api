import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_v2_regime_reentry_v095 import setup_case as setup_r


def setup_case():
    rt,w,ts,st,req,o,_,_,_,ri,gi,pi=setup_r()
    sig=GovernanceInvalidationSignal('g96','G','governing structural input changed','configuration')
    p=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    arts={'PPP':o.pressure_field,'Phi':o.pressure_field,'H':o.horizon_assessment}
    b=GovernanceReusableArtifactBundle('b96','c96','s96','cfg96',tuple((s,arts[s]) for s in p.reusable_upstream_stages))
    ba=validate_reusable_artifact_bundle(p,b,expected_cycle_id='c96',expected_initial_state_id='s96',expected_configuration_id='cfg96')
    ginput=GoverningReusableIdentificationInputs(rt.registry.governing_substrate_identity())
    return rt,w,ts,st,req,o,p,b,ba,ginput,ri,gi,pi


def test_v096_g_reentry_runs_downstream_and_matches_control():
    rt,w,ts,st,req,o,p,b,ba,ginput,ri,gi,pi=setup_case(); c=len(w.constraint_calls); q=len(w.q_calls)
    x=execute_governing_reentry(rt,p,b,ba,st,req,ginput,ri,gi,pi)
    assert x.valid and x.status=='reentry_pass_completed' and x.recomputed_stage_ids[:3]==('G','R','Graph/Seed')
    assert set(x.decision.governing_assessment.governing_domain_ids)==set(o.governing_assessment.governing_domain_ids)
    assert x.decision.selection.selected_policy_id==o.selection.selected_policy_id
    assert len(w.constraint_calls)>c and len(w.q_calls)>q and len(ts.handoffs)==0


def test_v096_g_does_not_reacquire_world_state():
    rt,w,ts,st,req,o,p,b,ba,ginput,ri,gi,pi=setup_case(); old=w.domain_value; calls={'n':0}
    def guard(*a,**k): calls['n']+=1; raise AssertionError('G reacquired world domain value')
    w.domain_value=guard
    try:
        x=execute_governing_reentry(rt,p,b,ba,st,req,ginput,ri,gi,pi)
        assert x.valid and calls['n']==0
    finally: w.domain_value=old


def test_v096_governing_substrate_identity_is_deterministic():
    rt,*_=setup_case(); assert rt.registry.governing_substrate_identity()==rt.registry.governing_substrate_identity()


def test_v096_changed_governing_substrate_fails_closed():
    rt,w,ts,st,req,o,p,b,ba,ginput,ri,gi,pi=setup_case()
    # Mutate the registered G configuration only to simulate a changed authorized substrate.
    rt.registry.governing_configuration=GoverningConfiguration(epsilon_h=(rt.registry.governing_configuration.epsilon_h if rt.registry.governing_configuration else 0.0)+0.25)
    x=execute_governing_reentry(rt,p,b,ba,st,req,ginput,ri,gi,pi)
    assert not x.valid and any('G substrate identity changed' in v for v in x.violations)


def test_v096_g_refreshes_downstream_governing_flags():
    rt,w,ts,st,req,o,p,b,ba,ginput,ri,gi,pi=setup_case()
    # Stale flags in the captured R payload are not authority at a G re-entry boundary.
    ds=tuple(DomainAssessment(x.domain_id,x.perceived_value,x.pressure,x.horizon,not x.governing,x.threshold) for x in ri.domain_assessments)
    stale=RegimeReusableClassificationInputs(ds,ri.contextual_interruption,ri.previous_regime,ri.regime_configuration_identity)
    x=execute_governing_reentry(rt,p,b,ba,st,req,ginput,stale,gi,pi)
    assert x.valid and set(x.decision.governing_assessment.governing_domain_ids)==set(o.governing_assessment.governing_domain_ids)


def test_v096_wrong_boundary_and_invalid_bundle_fail_closed():
    rt,w,ts,st,req,o,p,b,ba,ginput,ri,gi,pi=setup_case()
    bad=GovernanceReentryPlan(True,'R',p.reusable_upstream_stages,p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids)
    assert not execute_governing_reentry(rt,bad,b,ba,st,req,ginput,ri,gi,pi).valid
    badba=GovernanceReusableArtifactBundleAssessment(False,b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,p.reusable_upstream_stages,('bad',),())
    assert not execute_governing_reentry(rt,p,b,badba,st,req,ginput,ri,gi,pi).valid


def test_v096_no_epsilon_and_reusable_identity_preserved():
    rt,w,ts,st,req,o,p,b,ba,ginput,ri,gi,pi=setup_case(); x=execute_governing_reentry(rt,p,b,ba,st,req,ginput,ri,gi,pi)
    assert 'epsilon' not in x.recomputed_stage_ids and x.reused_stage_ids==p.reusable_upstream_stages and len(ts.handoffs)==0
