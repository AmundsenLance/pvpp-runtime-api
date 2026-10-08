from pvpp_runtime import *
from pvpp_runtime.models import DomainDefinition, ActionDefinition, GraphInstanceDefinition, GraphTransformationDefinition
from pvpp_runtime.registry import PVPPRegistry


def trajectory(snapshot="s2"):
    o=CapabilityChangeObservation("co:1","agent:1","cap:tool",10,"increased","s1",snapshot,"sensor","cp",.9,("ev",),("cfg",))
    return project_capability_trajectory("traj:1",(o,))


def setup():
    r=PVPPRegistry(); r.register_domain(DomainDefinition("D","d",0))
    r.register_action(ActionDefinition("steady","steady",("D",))); r.register_action(ActionDefinition("a","a",("D",)))
    r.register_graph_instance(GraphInstanceDefinition("i","thing",("D",),"ok"))
    r.register_graph_transformation(GraphTransformationDefinition("t","i","i","continuation",("D",),"unreachable","a"))
    return r,"t","reachable"


def dep(tid,status,snapshot="s2",**kw):
    d=dict(dependency_id="cd:1",entity_id="agent:1",capability_id="cap:tool",transformation_id=tid,
           capability_snapshot_id=snapshot,reachability_status=status,source_id="cap-model",provenance_id="prov:cap")
    d.update(kw); return CapabilityGraphReachabilityDependency(**d)


def test_capability_trajectory_can_refresh_explicit_existing_reachability():
    rt,tid,target=setup(); a=refresh_graph_from_capability_trajectory(rt,trajectory(),(dep(tid,target),),refresh_id="cr:1")
    assert a.valid and a.governance_trigger.refresh_assessment.status=="APPLIED"
    assert tid in a.governance_trigger.refresh_assessment.changed_transformation_ids


def test_material_refresh_routes_to_graph_seed_reentry_plan():
    rt,tid,target=setup(); a=refresh_graph_from_capability_trajectory(rt,trajectory(),(dep(tid,target),),refresh_id="cr:1")
    assert a.governance_trigger.reentry_plan.recompute_from_stage=="Graph/Seed"
    assert "Pi" in a.governance_trigger.reentry_plan.nonreusable_stages


def test_dependency_must_match_current_capability_snapshot():
    rt,tid,target=setup(); before=rt.graph_substrate_identity()
    a=refresh_graph_from_capability_trajectory(rt,trajectory(),(dep(tid,target,"OLD"),),refresh_id="cr:1")
    assert not a.valid and rt.graph_substrate_identity()==before


def test_entity_or_capability_mismatch_fails_without_mutation():
    rt,tid,target=setup(); before=rt.graph_substrate_identity()
    a=refresh_graph_from_capability_trajectory(rt,trajectory(),(dep(tid,target,entity_id="other"),),refresh_id="cr:1")
    assert not a.valid and rt.graph_substrate_identity()==before


def test_unknown_transformation_cannot_be_invented_by_capability_gain():
    rt,tid,target=setup(); before=rt.graph_substrate_identity()
    a=refresh_graph_from_capability_trajectory(rt,trajectory(),(dep("novel:transformation",target),),refresh_id="cr:1")
    assert not a.valid and a.governance_trigger.refresh_assessment.status=="REJECTED"
    assert rt.graph_substrate_identity()==before


def test_uncertain_reachability_requires_explicit_note():
    rt,tid,_=setup(); a=refresh_graph_from_capability_trajectory(rt,trajectory(),(dep(tid,"uncertain"),),refresh_id="cr:1")
    assert not a.valid


def test_invalid_trajectory_cannot_drive_graph_refresh():
    rt,tid,target=setup(); before=rt.graph_substrate_identity()
    bad=CapabilityTrajectoryProjectionAssessment(False,None,("bad",))
    a=refresh_graph_from_capability_trajectory(rt,bad,(dep(tid,target),),refresh_id="cr:1")
    assert not a.valid and rt.graph_substrate_identity()==before


def test_refresh_creates_no_structural_admission_or_execution_authority():
    rt,tid,target=setup(); count=len(rt.graph_transformations)
    a=refresh_graph_from_capability_trajectory(rt,trajectory(),(dep(tid,target),),refresh_id="cr:1")
    assert a.valid and len(rt.graph_transformations)==count
    assert not hasattr(a,"execution_result") and not hasattr(a,"admission_request")
