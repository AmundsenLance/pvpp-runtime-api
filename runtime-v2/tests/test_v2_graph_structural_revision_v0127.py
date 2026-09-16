from pvpp_runtime import *

def reg0():
    r=PVPPRegistry(); r.register_domain(DomainDefinition('D','d',0.0)); r.register_action(ActionDefinition('a','a',('D',))); r.register_graph_instance(GraphInstanceDefinition('i','unit',('D',),'s'))
    r.register_graph_transformation(GraphTransformationDefinition('t','i','i','continuation',('D',),'reachable','a'))
    return r

def req(r, operation='replace', replacement=None, **kw):
    if replacement is None and operation=='replace': replacement=GraphTransformationDefinition('t','i','i','corrective_repair',('D',),'unreachable','a')
    x=dict(revision_id='rev1',expected_graph_substrate_identity=r.graph_substrate_identity(),operation=operation,transformation_id='t',configuration_version='cfg3',source_id='host',provenance_id='p3',rationale='controlled lifecycle update',replacement=replacement,evidence={'ticket':'R'})
    x.update(kw); return GraphTransformationRevisionRequest(**x)

def test_replace_preserves_id_and_changes_identity_with_provenance():
    r=reg0(); before=r.graph_substrate_identity(); a=r.revise_graph_transformation(req(r)); assert a.status=='REVISED' and a.resulting_graph_substrate_identity!=before
    assert r.graph_transformations['t'].family=='corrective_repair' and r.graph_transformations['t'].metadata['structural_revision']['provenance_id']=='p3'

def test_remove_is_atomic_and_changes_identity():
    r=reg0(); before=r.graph_substrate_identity(); a=r.revise_graph_transformation(req(r,'remove')); assert a.status=='REVISED' and 't' not in r.graph_transformations and a.resulting_graph_substrate_identity!=before

def test_stale_identity_rejected_without_mutation():
    r=reg0(); before=r.graph_substrate_identity(); a=r.revise_graph_transformation(req(r,expected_graph_substrate_identity='stale')); assert a.status=='REJECTED' and r.graph_substrate_identity()==before and 't' in r.graph_transformations

def test_replacement_cannot_change_structural_identity():
    r=reg0(); bad=GraphTransformationDefinition('other','i','i','continuation',('D',),'reachable','a'); assert r.revise_graph_transformation(req(r,replacement=bad)).status=='REJECTED'

def test_remove_cannot_smuggle_replacement():
    r=reg0(); repl=GraphTransformationDefinition('t','i','i','continuation',('D',),'reachable','a'); assert r.revise_graph_transformation(req(r,'remove',repl)).status=='REJECTED' and 't' in r.graph_transformations

def test_missing_provenance_fails_closed():
    r=reg0(); before=r.graph_substrate_identity(); assert r.revise_graph_transformation(req(r,provenance_id='')).status=='REJECTED' and r.graph_substrate_identity()==before

def test_successful_revision_plans_graph_reentry():
    r=reg0(); trig=revise_graph_transformation_and_plan_reentry(r,req(r)); assert trig.valid and trig.reentry_plan.recompute_from_stage=='Graph/Seed' and trig.invalidation_signal.invalidated_stage=='Graph/Seed'

def test_rejected_revision_has_no_reentry_or_execution_authority():
    r=reg0(); trig=revise_graph_transformation_and_plan_reentry(r,req(r,expected_graph_substrate_identity='bad')); assert not trig.valid and trig.invalidation_signal is None and trig.reentry_plan is None
    assert not hasattr(trig,'execution_license') and not hasattr(trig,'sigma_assessment')
