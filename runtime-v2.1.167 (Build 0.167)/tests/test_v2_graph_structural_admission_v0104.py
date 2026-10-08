from pvpp_runtime import *

def rt0():
    class X: pass
    rt=X(); rt.registry=PVPPRegistry()
    rt.registry.register_domain(DomainDefinition('D','d',0.0))
    rt.registry.register_action(ActionDefinition('a','a',('D',)))
    rt.registry.register_graph_instance(GraphInstanceDefinition('i','unit',('D',),'s'))
    return rt

def req(rt, tr=None, **kw):
    tr=tr or GraphTransformationDefinition('new','i','i','continuation',('D',),'unreachable','a')
    x=dict(admission_id='adm1',expected_graph_substrate_identity=rt.registry.graph_substrate_identity(),transformation=tr,configuration_version='cfg2',source_id='host',provenance_id='p1',rationale='approved represented mechanism',evidence={'ticket':'A'})
    x.update(kw); return GraphTransformationAdmissionRequest(**x)

def test_admits_explicit_new_transformation_and_changes_identity():
    rt=rt0(); before=rt.registry.graph_substrate_identity(); a=rt.registry.admit_graph_transformation(req(rt))
    assert a.status=='ADMITTED' and a.prior_graph_substrate_identity==before and a.resulting_graph_substrate_identity!=before
    assert 'new' in rt.registry.graph_transformations

def test_admission_metadata_is_versioned_and_provenance_bearing():
    rt=rt0(); rt.registry.admit_graph_transformation(req(rt)); m=rt.registry.graph_transformations['new'].metadata['structural_admission']
    assert m['configuration_version']=='cfg2' and m['provenance_id']=='p1' and m['evidence']['ticket']=='A'

def test_stale_substrate_fails_without_mutation():
    rt=rt0(); a=rt.registry.admit_graph_transformation(req(rt,expected_graph_substrate_identity='stale'))
    assert a.status=='REJECTED' and 'new' not in rt.registry.graph_transformations

def test_missing_provenance_version_or_rationale_fails_closed():
    for k in ('configuration_version','source_id','provenance_id','rationale'):
        rt=rt0(); a=rt.registry.admit_graph_transformation(req(rt,**{k:''}))
        assert a.status=='REJECTED' and not rt.registry.graph_transformations

def test_unregistered_action_fails_closed():
    rt=rt0(); tr=GraphTransformationDefinition('new','i','i','continuation',('D',),'unreachable','missing')
    assert rt.registry.admit_graph_transformation(req(rt,tr)).status=='REJECTED'
    assert 'new' not in rt.registry.graph_transformations

def test_unregistered_instance_fails_closed():
    rt=rt0(); tr=GraphTransformationDefinition('new','missing','i','continuation',('D',),'unreachable','a')
    assert rt.registry.admit_graph_transformation(req(rt,tr)).status=='REJECTED'

def test_duplicate_transformation_is_not_revision_path():
    rt=rt0(); assert rt.registry.admit_graph_transformation(req(rt)).status=='ADMITTED'
    r=req(rt, expected_graph_substrate_identity=rt.registry.graph_substrate_identity())
    assert rt.registry.admit_graph_transformation(r).status=='REJECTED'

def test_admission_does_not_create_execution_authority():
    rt=rt0(); a=rt.registry.admit_graph_transformation(req(rt))
    assert a.status=='ADMITTED'
    assert not hasattr(a,'execution_license') and not hasattr(a,'sigma_assessment')
