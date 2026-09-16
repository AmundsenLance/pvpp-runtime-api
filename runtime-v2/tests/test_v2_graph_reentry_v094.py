import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_concurrent_recovery_execution_binding_v055 import build,state,request


def setup_case():
    rt,w,ts=build(); req=request(); original=rt.evaluate_canonical_decision_cycle(state(),req)
    sig=GovernanceInvalidationSignal('graph94','Graph/Seed','registered graph input changed','structure')
    plan=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    arts={'PPP':original.pressure_field,'Phi':original.pressure_field,'H':original.horizon_assessment,'G':original.governing_assessment,'R':original.regime_assessment}
    b=GovernanceReusableArtifactBundle('b94','c94','s94','cfg94',tuple((s,arts[s]) for s in plan.reusable_upstream_stages))
    ba=validate_reusable_artifact_bundle(plan,b,expected_cycle_id='c94',expected_initial_state_id='s94',expected_configuration_id='cfg94')
    gi=GraphReusableConstructionInputs(req.preservation_object,req.required_graph_family_ids,req.required_graph_path_class_ids,req.graph_config,rt.registry.graph_substrate_identity())
    pi=PiReusableConstructionInputs(req.materially_required_policy_class_ids,req.pi_config)
    return rt,w,ts,req,original,plan,b,ba,gi,pi

def test_v094_graph_reentry_reconstructs_graph_then_downstream():
    rt,w,ts,req,o,p,b,ba,gi,pi=setup_case(); c=len(w.constraint_calls); q=len(w.q_calls)
    x=execute_graph_reentry(rt,p,b,ba,state(),req,gi,pi)
    assert x.valid and x.status=='reentry_pass_completed'
    assert x.recomputed_stage_ids[0:3]==('Graph/Seed','Pi','Pi Completeness')
    assert x.decision.graph_assessment.seed_ids==o.graph_assessment.seed_ids
    assert len(w.constraint_calls)>c and len(w.q_calls)>q and len(ts.handoffs)==0

def test_v094_registry_identity_is_stable_without_mutation():
    rt,*_=setup_case(); assert rt.registry.graph_substrate_identity()==rt.registry.graph_substrate_identity()

def test_v094_changed_graph_registry_fails_closed():
    rt,w,ts,req,o,p,b,ba,gi,pi=setup_case()
    # Adding an otherwise valid graph instance changes the registered substrate.
    did=next(iter(rt.registry.domains))
    rt.registry.register_graph_instance(GraphInstanceDefinition('late94','state',(did,),'available'))
    c=len(w.constraint_calls); q=len(w.q_calls)
    x=execute_graph_reentry(rt,p,b,ba,state(),req,gi,pi)
    assert not x.valid and any('substrate identity changed' in v for v in x.violations)
    assert (len(w.constraint_calls),len(w.q_calls))==(c,q)

def test_v094_graph_declarations_must_match_request():
    rt,w,ts,req,o,p,b,ba,gi,pi=setup_case()
    bad=GraphReusableConstructionInputs(req.preservation_object,('continuation',),req.required_graph_path_class_ids,req.graph_config,gi.graph_substrate_identity)
    x=execute_graph_reentry(rt,p,b,ba,state(),req,bad,pi)
    assert not x.valid and any('required-family' in v for v in x.violations)

def test_v094_graph_config_must_match_request():
    rt,w,ts,req,o,p,b,ba,gi,pi=setup_case()
    bad=GraphReusableConstructionInputs(req.preservation_object,req.required_graph_family_ids,req.required_graph_path_class_ids,GraphConstructionConfig(7),gi.graph_substrate_identity)
    x=execute_graph_reentry(rt,p,b,ba,state(),req,bad,pi)
    assert not x.valid and any('configuration' in v for v in x.violations)

def test_v094_wrong_boundary_fails_before_downstream_work():
    rt,w,ts,req,o,p,b,ba,gi,pi=setup_case(); bad=GovernanceReentryPlan(True,'Pi',p.reusable_upstream_stages,p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids)
    c=len(w.constraint_calls); q=len(w.q_calls); x=execute_graph_reentry(rt,bad,b,ba,state(),req,gi,pi)
    assert not x.valid and (len(w.constraint_calls),len(w.q_calls))==(c,q)

def test_v094_stops_before_epsilon_and_preserves_reuse_identity():
    rt,w,ts,req,o,p,b,ba,gi,pi=setup_case(); x=execute_graph_reentry(rt,p,b,ba,state(),req,gi,pi)
    assert 'epsilon' not in x.recomputed_stage_ids and len(ts.handoffs)==0 and x.reused_stage_ids==p.reusable_upstream_stages
