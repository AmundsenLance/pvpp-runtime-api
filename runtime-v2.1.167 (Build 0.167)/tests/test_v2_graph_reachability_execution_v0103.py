import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_v2_graph_reentry_v094 import setup_case


def observation(tid='t', status='reachable', provenance='prov-103'):
    return GraphReachabilityObservation(tid,status,2.0,'reachability-sensor',provenance,'',{'v':103})


def install_refreshable_transformation(rt):
    # Mature fixture already has registered graph material. Add one represented transformation
    # before authorizing reusable Graph inputs so its identity belongs to the pre-refresh substrate.
    did=next(iter(rt.registry.domains)); aid=next(a for a in rt.registry.actions if a!='steady')
    inst=next(iter(rt.registry.graph_instances))
    rt.registry.register_graph_transformation(GraphTransformationDefinition('t',inst,inst,'continuation',(did,),'unreachable',aid))
    rt.registry.register_sigma_order(SigmaOrderDefinition('graph:t',999))


def case():
    rt,w,ts,req,original,plan,b,ba,gi,pi=setup_case()
    # setup_case authorized before our extra represented structure, so construct a fresh ordinary cycle
    # and bundle after registration, exactly as a host would before later reachability changes.
    install_refreshable_transformation(rt)
    original=rt.evaluate_canonical_decision_cycle(__import__('test_concurrent_recovery_execution_binding_v055').state(),req)
    sig=GovernanceInvalidationSignal('placeholder103','Graph/Seed','later reachability','structure')
    p=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    arts={'PPP':original.pressure_field,'Phi':original.pressure_field,'H':original.horizon_assessment,'G':original.governing_assessment,'R':original.regime_assessment}
    b=GovernanceReusableArtifactBundle('b103','c103','s103','cfg103',tuple((s,arts[s]) for s in p.reusable_upstream_stages))
    ba=validate_reusable_artifact_bundle(p,b,expected_cycle_id='c103',expected_initial_state_id='s103',expected_configuration_id='cfg103')
    gi=GraphReusableConstructionInputs(req.preservation_object,req.required_graph_family_ids,req.required_graph_path_class_ids,req.graph_config,rt.registry.graph_substrate_identity())
    pi=PiReusableConstructionInputs(req.materially_required_policy_class_ids,req.pi_config)
    return rt,w,ts,req,b,ba,gi,pi


def run_case():
    rt,w,ts,req,b,ba,gi,pi=case(); rr=GraphReachabilityRefreshRequest(rt.registry.graph_substrate_identity(),(observation(),),'refresh-103')
    trigger=refresh_graph_reachability_and_plan_reentry(rt.registry,rr)
    st=__import__('test_concurrent_recovery_execution_binding_v055').state()
    return rt,w,ts,req,b,ba,gi,pi,trigger,st


def test_material_refresh_executes_existing_graph_downstream_path():
    rt,w,ts,req,b,ba,gi,pi,tr,st=run_case(); c=len(w.constraint_calls); q=len(w.q_calls)
    x=execute_graph_reachability_refresh_reentry(rt,tr,b,ba,st,req,gi,pi)
    assert x.valid and x.status=='reentry_pass_completed'
    assert x.recomputed_stage_ids[0:3]==('Graph/Seed','Pi','Pi Completeness')
    assert len(w.constraint_calls)>c and len(w.q_calls)>q and len(ts.handoffs)==0


def test_pre_refresh_graph_input_identity_is_required():
    rt,w,ts,req,b,ba,gi,pi,tr,st=run_case()
    bad=GraphReusableConstructionInputs(gi.preservation_object,gi.required_graph_family_ids,gi.required_graph_path_class_ids,gi.graph_config,'wrong')
    x=execute_graph_reachability_refresh_reentry(rt,tr,b,ba,st,req,bad,pi)
    assert not x.valid and any('pre-refresh' in v for v in x.violations)


def test_post_refresh_registry_mutation_fails_closed():
    rt,w,ts,req,b,ba,gi,pi,tr,st=run_case(); did=next(iter(rt.registry.domains))
    rt.registry.register_graph_instance(GraphInstanceDefinition('late103','thing',(did,),'available'))
    x=execute_graph_reachability_refresh_reentry(rt,tr,b,ba,st,req,gi,pi)
    assert not x.valid and any('no longer matches' in v for v in x.violations)


def test_noop_trigger_cannot_execute_reentry():
    rt,w,ts,req,b,ba,gi,pi=case(); rr=GraphReachabilityRefreshRequest(rt.registry.graph_substrate_identity(),(observation(status='unreachable'),),'noop-103')
    tr=refresh_graph_reachability_and_plan_reentry(rt.registry,rr); st=__import__('test_concurrent_recovery_execution_binding_v055').state()
    x=execute_graph_reachability_refresh_reentry(rt,tr,b,ba,st,req,gi,pi)
    assert not x.valid and any('material change' in v for v in x.violations)


def test_unknown_transformation_still_cannot_enter_execution_path():
    rt,w,ts,req,b,ba,gi,pi=case(); rr=GraphReachabilityRefreshRequest(rt.registry.graph_substrate_identity(),(observation(tid='novel'),),'novel-103')
    tr=refresh_graph_reachability_and_plan_reentry(rt.registry,rr); st=__import__('test_concurrent_recovery_execution_binding_v055').state()
    x=execute_graph_reachability_refresh_reentry(rt,tr,b,ba,st,req,gi,pi)
    assert not x.valid and 'novel' not in rt.registry.graph_transformations


def test_bridge_does_not_change_graph_declarations_or_pi_inputs():
    rt,w,ts,req,b,ba,gi,pi,tr,st=run_case(); before=(gi.preservation_object,gi.required_graph_family_ids,gi.required_graph_path_class_ids,gi.graph_config,pi)
    x=execute_graph_reachability_refresh_reentry(rt,tr,b,ba,st,req,gi,pi)
    assert x.valid and before==(gi.preservation_object,gi.required_graph_family_ids,gi.required_graph_path_class_ids,gi.graph_config,pi)


def test_refresh_provenance_remains_on_trigger_and_execution_stays_before_epsilon():
    rt,w,ts,req,b,ba,gi,pi,tr,st=run_case(); x=execute_graph_reachability_refresh_reentry(rt,tr,b,ba,st,req,gi,pi)
    assert tr.invalidation_signal.evidence_ids==('prov-103',)
    assert 'epsilon' not in x.recomputed_stage_ids and len(ts.handoffs)==0
