from pvpp_runtime import *
from pvpp_runtime.models import DomainDefinition, ActionDefinition, GraphInstanceDefinition, GraphTransformationDefinition


def setup():
    r=PVPPRegistry(); r.register_domain(DomainDefinition('D','D',0.0))
    r.register_action(ActionDefinition('steady','steady',('D',)))
    r.register_graph_instance(GraphInstanceDefinition('s','unit',('D',),'s'))
    r.register_graph_instance(GraphInstanceDefinition('t','unit',('D',),'t'))
    return r

def req(r, **kw):
    a=ActionDefinition('novel','host-defined novel consequential function',('D',))
    tr=GraphTransformationDefinition('novel:t','s','t','structural_reconfiguration',('D',),'reachable','novel')
    x=dict(admission_id='nf121',expected_action_registry_identity=r.action_registry_identity(),expected_graph_substrate_identity=r.graph_substrate_identity(),action=a,transformation=tr,configuration_version='cfg121',source_id='host-authority',provenance_id='prov121',rationale='explicit reviewed extension',evidence={'ticket':'121'})
    x.update(kw); return NovelFunctionAdmissionRequest(**x)

def test_atomic_admission_adds_action_and_transformation_with_provenance():
    r=setup(); a=r.admit_novel_function(req(r)); assert a.status=='ADMITTED'
    assert 'novel' in r.actions and 'novel:t' in r.graph_transformations
    assert r.actions['novel'].metadata['novel_function_admission']['provenance_id']=='prov121'

def test_rejected_unknown_domain_is_atomic():
    r=setup(); q=req(r,action=ActionDefinition('novel','x',('UNKNOWN',)))
    a=r.admit_novel_function(q); assert a.status=='REJECTED'; assert 'novel' not in r.actions and 'novel:t' not in r.graph_transformations

def test_transformation_must_reference_same_new_action():
    r=setup(); tr=GraphTransformationDefinition('x','s','t','structural_reconfiguration',('D',),'reachable','steady')
    a=r.admit_novel_function(req(r,transformation=tr)); assert a.status=='REJECTED'; assert 'novel' not in r.actions

def test_stale_action_identity_fails_closed():
    r=setup(); q=req(r,expected_action_registry_identity='stale'); a=r.admit_novel_function(q)
    assert a.status=='REJECTED' and 'novel' not in r.actions

def test_stale_graph_identity_fails_closed():
    r=setup(); q=req(r,expected_graph_substrate_identity='stale'); a=r.admit_novel_function(q)
    assert a.status=='REJECTED' and 'novel' not in r.actions

def test_success_plans_graph_seed_reentry():
    r=setup(); t=admit_novel_function_and_plan_reentry(r,req(r)); assert t.valid
    assert t.reentry_plan.recompute_from_stage=='Graph/Seed'
    assert t.invalidation_signal.source_kind=='novel_function_structural_admission'

def test_rejection_creates_no_reentry_authority():
    r=setup(); t=admit_novel_function_and_plan_reentry(r,req(r,expected_graph_substrate_identity='stale'))
    assert not t.valid and t.invalidation_signal is None and t.reentry_plan is None

def test_admission_creates_no_selection_or_execution_authority():
    r=setup(); t=admit_novel_function_and_plan_reentry(r,req(r)); assert t.valid
    assert not hasattr(t,'decision') and not hasattr(t,'epsilon') and not hasattr(t,'execution_result')
