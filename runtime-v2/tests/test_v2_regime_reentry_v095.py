import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_concurrent_recovery_execution_binding_v055 import build,state,request

def setup_case():
    rt,w,ts=build(); req=request(); st=state(); o=rt.evaluate_canonical_decision_cycle(st,req)
    sig=GovernanceInvalidationSignal('r95','R','regime input changed','configuration')
    p=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    # Capture the exact DomainAssessment payload once, as the original cycle did, but do not use world calls during re-entry.
    perceived=rt.world.perceive(st); pmap={x.domain_id:x.pressure for x in o.pressure_field.domain_results}
    ds=tuple(DomainAssessment(did,float(rt.world.domain_value(perceived,did)),pmap[did],o.horizon_assessment.horizons[did],did in set(o.governing_assessment.governing_domain_ids),d.threshold) for did,d in rt.registry.domains.items())
    arts={'PPP':o.pressure_field,'Phi':o.pressure_field,'H':o.horizon_assessment,'G':o.governing_assessment}
    b=GovernanceReusableArtifactBundle('b95','c95','s95','cfg95',tuple((s,arts[s]) for s in p.reusable_upstream_stages))
    ba=validate_reusable_artifact_bundle(p,b,expected_cycle_id='c95',expected_initial_state_id='s95',expected_configuration_id='cfg95')
    ri=RegimeReusableClassificationInputs(ds,req.contextual_interruption,req.previous_regime,rt.registry.regime_configuration_identity())
    gi=GraphReusableConstructionInputs(req.preservation_object,req.required_graph_family_ids,req.required_graph_path_class_ids,req.graph_config,rt.registry.graph_substrate_identity())
    pi=PiReusableConstructionInputs(req.materially_required_policy_class_ids,req.pi_config)
    return rt,w,ts,st,req,o,p,b,ba,ri,gi,pi

def test_v095_r_reentry_runs_downstream_and_matches_control():
    rt,w,ts,st,req,o,p,b,ba,ri,gi,pi=setup_case(); c=len(w.constraint_calls); q=len(w.q_calls)
    x=execute_regime_reentry(rt,p,b,ba,st,req,ri,gi,pi)
    assert x.valid and x.status=='reentry_pass_completed' and x.recomputed_stage_ids[:3]==('R','Graph/Seed','Pi')
    assert x.decision.regime_assessment.regime==o.regime_assessment.regime
    assert x.decision.selection.selected_policy_id==o.selection.selected_policy_id
    assert len(w.constraint_calls)>c and len(w.q_calls)>q and len(ts.handoffs)==0

def test_v095_r_does_not_reacquire_world_for_classification():
    rt,w,ts,st,req,o,p,b,ba,ri,gi,pi=setup_case()
    # If R tried to call domain_value again this would fail; downstream constraints/projectors remain available.
    old=w.domain_value
    calls={'n':0}
    def guard(*a,**k): calls['n']+=1; raise AssertionError('R reacquired world domain value')
    w.domain_value=guard
    try:
        # Graph/downstream does not need domain_value in this fixture.
        x=execute_regime_reentry(rt,p,b,ba,st,req,ri,gi,pi)
        assert x.valid and calls['n']==0
    finally: w.domain_value=old

def test_v095_regime_config_identity_is_stable():
    rt,*_=setup_case(); assert rt.registry.regime_configuration_identity()==rt.registry.regime_configuration_identity()

def test_v095_wrong_regime_config_identity_fails_closed():
    rt,w,ts,st,req,o,p,b,ba,ri,gi,pi=setup_case()
    bad=RegimeReusableClassificationInputs(ri.domain_assessments,ri.contextual_interruption,ri.previous_regime,'bad')
    x=execute_regime_reentry(rt,p,b,ba,st,req,bad,gi,pi); assert not x.valid and any('configuration identity changed' in v for v in x.violations)

def test_v095_phi_mismatch_fails_closed():
    rt,w,ts,st,req,o,p,b,ba,ri,gi,pi=setup_case(); ds=list(ri.domain_assessments); a=ds[0]
    ds[0]=DomainAssessment(a.domain_id,a.perceived_value,a.pressure+1,a.horizon,a.governing,a.threshold)
    bad=RegimeReusableClassificationInputs(tuple(ds),ri.contextual_interruption,ri.previous_regime,ri.regime_configuration_identity)
    x=execute_regime_reentry(rt,p,b,ba,st,req,bad,gi,pi); assert not x.valid and any('does not match Phi' in v for v in x.violations)

def test_v095_request_context_mismatch_fails_closed():
    rt,w,ts,st,req,o,p,b,ba,ri,gi,pi=setup_case(); bad=RegimeReusableClassificationInputs(ri.domain_assessments,not ri.contextual_interruption,ri.previous_regime,ri.regime_configuration_identity)
    x=execute_regime_reentry(rt,p,b,ba,st,req,bad,gi,pi); assert not x.valid and any('contextual-interruption' in v for v in x.violations)

def test_v095_wrong_boundary_and_no_epsilon():
    rt,w,ts,st,req,o,p,b,ba,ri,gi,pi=setup_case(); bad=GovernanceReentryPlan(True,'Graph/Seed',p.reusable_upstream_stages,p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids)
    x=execute_regime_reentry(rt,bad,b,ba,st,req,ri,gi,pi); assert not x.valid
    x=execute_regime_reentry(rt,p,b,ba,st,req,ri,gi,pi); assert 'epsilon' not in x.recomputed_stage_ids and x.reused_stage_ids==p.reusable_upstream_stages
