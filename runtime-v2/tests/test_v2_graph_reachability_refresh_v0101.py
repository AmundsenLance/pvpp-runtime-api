from pvpp_runtime import *
from pvpp_runtime.models import DomainDefinition, ActionDefinition, GraphInstanceDefinition, GraphTransformationDefinition, PreliminaryPreservationObject
from pvpp_runtime.registry import PVPPRegistry
from pvpp_runtime.kernel import PVPPRuntime

def setup():
    r=PVPPRegistry(); r.register_domain(DomainDefinition('D','d',0))
    r.register_action(ActionDefinition('steady','steady',('D',))); r.register_action(ActionDefinition('a','a',('D',)))
    r.register_graph_instance(GraphInstanceDefinition('i','thing',('D',),'ok'))
    r.register_graph_transformation(GraphTransformationDefinition('t','i','i','continuation',('D',),'unreachable','a'))
    return r

def obs(status='reachable', tid='t', note=''):
    return GraphReachabilityObservation(tid,status,1.0,'sensor','prov-1',note,{'sample':1})

def test_refresh_changes_existing_reachability_and_identity():
    r=setup(); before=r.graph_substrate_identity()
    a=r.refresh_graph_reachability(GraphReachabilityRefreshRequest(before,(obs(),),'refresh-1'))
    assert a.status=='APPLIED' and a.changed_transformation_ids==('t',)
    assert a.resulting_graph_substrate_identity != before
    assert r.graph_transformations['t'].reachability_status=='reachable'
    assert r.graph_transformations['t'].metadata['reachability_refresh']['provenance_id']=='prov-1'

def test_refresh_changes_graph_construction_without_structural_admission():
    r=setup(); rt=PVPPRuntime(r,None); po=PreliminaryPreservationObject('p','preserve')
    assert rt.construct_graph(po,'Mission',('D',),required_family_ids=('continuation',)).status=='FAIL'
    before=set(r.graph_transformations)
    a=r.refresh_graph_reachability(GraphReachabilityRefreshRequest(r.graph_substrate_identity(),(obs(),),'refresh-2'))
    assert a.status=='APPLIED' and set(r.graph_transformations)==before
    assert rt.construct_graph(po,'Mission',('D',),required_family_ids=('continuation',)).status=='PASS'

def test_unknown_transformation_fails_closed_atomically():
    r=setup(); before=r.graph_substrate_identity(); old=r.graph_transformations['t']
    req=GraphReachabilityRefreshRequest(before,(obs(),obs(tid='novel')),'refresh-3')
    a=r.refresh_graph_reachability(req)
    assert a.status=='REJECTED' and r.graph_transformations['t']==old and r.graph_substrate_identity()==before
    assert any('unrepresented' in x for x in a.violations)

def test_stale_substrate_identity_rejected():
    r=setup(); a=r.refresh_graph_reachability(GraphReachabilityRefreshRequest('stale',(obs(),),'refresh-4'))
    assert a.status=='REJECTED' and r.graph_transformations['t'].reachability_status=='unreachable'

def test_uncertain_requires_note_and_valid_refresh_records_uncertainty():
    r=setup(); before=r.graph_substrate_identity()
    bad=r.refresh_graph_reachability(GraphReachabilityRefreshRequest(before,(obs('uncertain'),),'r-bad'))
    assert bad.status=='REJECTED'
    good=r.refresh_graph_reachability(GraphReachabilityRefreshRequest(before,(obs('uncertain',note='route not confirmed'),),'r-good'))
    assert good.status=='APPLIED' and r.graph_transformations['t'].uncertainty_note=='route not confirmed'

def test_duplicate_observation_rejected_atomically():
    r=setup(); before=r.graph_substrate_identity()
    a=r.refresh_graph_reachability(GraphReachabilityRefreshRequest(before,(obs(),obs('unreachable')),'refresh-6'))
    assert a.status=='REJECTED' and r.graph_substrate_identity()==before

def test_provenance_and_source_are_required():
    r=setup(); before=r.graph_substrate_identity()
    x=GraphReachabilityObservation('t','reachable',1.0,'','')
    a=r.refresh_graph_reachability(GraphReachabilityRefreshRequest(before,(x,),'refresh-7'))
    assert a.status=='REJECTED'

def test_noop_refresh_is_explicit_and_identity_stable():
    r=setup(); before=r.graph_substrate_identity()
    x=obs('unreachable')
    a=r.refresh_graph_reachability(GraphReachabilityRefreshRequest(before,(x,),'refresh-8'))
    assert a.status=='APPLIED' and a.unchanged_transformation_ids==('t',) and a.resulting_graph_substrate_identity==before
