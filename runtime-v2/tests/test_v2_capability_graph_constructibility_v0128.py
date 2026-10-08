from pvpp_runtime import *
from pvpp_runtime.models import DomainDefinition, ActionDefinition, GraphInstanceDefinition, GraphTransformationDefinition
from pvpp_runtime.registry import PVPPRegistry


def trajectory(snapshot="s2"):
    o=CapabilityChangeObservation("co:128","agent:1","cap:tool",10,"increased","s1",snapshot,"sensor","cp",.9,("ev",),("cfg",))
    return project_capability_trajectory("traj:128",(o,))


def setup():
    r=PVPPRegistry(); r.register_domain(DomainDefinition("D","d",0))
    r.register_action(ActionDefinition("steady","steady",("D",))); r.register_action(ActionDefinition("a","a",("D",)))
    r.register_graph_instance(GraphInstanceDefinition("i","thing",("D",),"ok")); r.register_graph_instance(GraphInstanceDefinition("j","thing",("D",),"ok"))
    return r


def dep(snapshot="s2", tid="t:new", **kw):
    tr=GraphTransformationDefinition(tid,"i","j","structural_reconfiguration",("D",),"reachable","a")
    d=dict(dependency_id="ccd:1",entity_id="agent:1",capability_id="cap:tool",capability_snapshot_id=snapshot,
           transformation=tr,configuration_version="cfg:128",source_id="host",provenance_id="prov:128",rationale="capability now supports declared path")
    d.update(kw); return CapabilityGraphConstructibilityDependency(**d)


def test_explicit_capability_dependency_can_admit_new_graph_path():
    r=setup(); a=construct_graph_from_capability_trajectory(r,trajectory(),dep(),admission_id="adm:128")
    assert a.valid and "t:new" in r.graph_transformations and a.governance_trigger.admission_assessment.status=="ADMITTED"

def test_constructibility_routes_to_graph_seed_reentry():
    r=setup(); a=construct_graph_from_capability_trajectory(r,trajectory(),dep(),admission_id="adm:128")
    assert a.governance_trigger.reentry_plan.recompute_from_stage=="Graph/Seed"

def test_dependency_must_bind_current_snapshot_without_mutation():
    r=setup(); before=r.graph_substrate_identity(); a=construct_graph_from_capability_trajectory(r,trajectory(),dep(snapshot="old"),admission_id="adm:128")
    assert not a.valid and r.graph_substrate_identity()==before

def test_entity_capability_mismatch_fails_closed():
    r=setup(); before=r.graph_substrate_identity(); a=construct_graph_from_capability_trajectory(r,trajectory(),dep(entity_id="other"),admission_id="adm:128")
    assert not a.valid and r.graph_substrate_identity()==before

def test_existing_transformation_cannot_be_re_admitted():
    r=setup(); r.register_graph_transformation(dep().transformation); before=r.graph_substrate_identity()
    a=construct_graph_from_capability_trajectory(r,trajectory(),dep(),admission_id="adm:128")
    assert not a.valid and r.graph_substrate_identity()==before

def test_unknown_action_is_rejected_by_existing_admission_boundary():
    r=setup(); tr=GraphTransformationDefinition("t:new","i","j","structural_reconfiguration",("D",),"reachable","not-registered")
    before=r.graph_substrate_identity(); a=construct_graph_from_capability_trajectory(r,trajectory(),dep(transformation=tr),admission_id="adm:128")
    assert not a.valid and r.graph_substrate_identity()==before

def test_provenance_and_rationale_are_mandatory():
    r=setup(); before=r.graph_substrate_identity(); a=construct_graph_from_capability_trajectory(r,trajectory(),dep(provenance_id="",rationale=""),admission_id="adm:128")
    assert not a.valid and r.graph_substrate_identity()==before

def test_constructibility_grants_no_selection_or_execution_authority():
    r=setup(); a=construct_graph_from_capability_trajectory(r,trajectory(),dep(),admission_id="adm:128")
    assert a.valid and not hasattr(a,"execution_result") and not hasattr(a,"sigma_result") and not hasattr(a,"epsilon")
