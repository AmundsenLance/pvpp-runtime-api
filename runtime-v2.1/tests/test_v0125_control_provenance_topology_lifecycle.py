from pvpp_runtime import *

def rel(i,s,o,t="controls",active=True,at=1.0,prov="p"):
    return ControlProvenanceRelation(i,s,o,t,at,"host",prov,active,("e",))

def prior():
    return assess_control_provenance_topology((rel("r1","agent","sensor"),),topology_id="top",as_of=2,governed_agent_ids=("agent",))

def req(p, relations, **kw):
    return ControlProvenanceTopologyUpdateRequest(kw.get("update_id","u"),kw.get("identity",control_provenance_topology_identity(p)),
        kw.get("topology_id","top"),kw.get("as_of",3),tuple(relations),kw.get("agents",("agent",)),
        kw.get("version","cfg2"),kw.get("source","host"),kw.get("prov","prov2"),kw.get("rationale","observed control change"))

def test_identity_is_order_independent_for_relations():
    a=assess_control_provenance_topology((rel("a","agent","x"),rel("b","agent","y")),topology_id="t",as_of=2,governed_agent_ids=("agent",))
    b=assess_control_provenance_topology((rel("b","agent","y"),rel("a","agent","x")),topology_id="t",as_of=2,governed_agent_ids=("agent",))
    assert control_provenance_topology_identity(a)==control_provenance_topology_identity(b)

def test_add_relation_delta_and_new_control():
    p=prior(); a=update_control_provenance_topology(p,req(p,(rel("r1","agent","sensor"),rel("r2","agent","tool",at=3))))
    assert a.valid and a.status=="UPDATED" and a.added_relation_ids==("r2",) and "tool" in a.topology_assessment.controlled_by_governed_agent

def test_remove_relation_delta():
    p=prior(); a=update_control_provenance_topology(p,req(p,()))
    assert a.valid and a.removed_relation_ids==("r1",)

def test_changed_relation_delta():
    p=prior(); a=update_control_provenance_topology(p,req(p,(rel("r1","agent","sensor",active=False,at=3),)))
    assert a.valid and a.changed_relation_ids==("r1",) and "sensor" not in a.topology_assessment.controlled_by_governed_agent

def test_stale_identity_rejected_without_result_snapshot():
    p=prior(); a=update_control_provenance_topology(p,req(p,p.relations,identity="stale"))
    assert not a.valid and a.topology_assessment is None

def test_time_cannot_move_backward():
    p=prior(); a=update_control_provenance_topology(p,req(p,p.relations,as_of=1))
    assert not a.valid

def test_missing_provenance_rejected():
    p=prior(); a=update_control_provenance_topology(p,req(p,p.relations,prov=""))
    assert not a.valid

def test_updated_snapshot_flows_to_existing_evidence_qualification():
    p=prior(); a=update_control_provenance_topology(p,req(p,()))
    ss=EvidenceSourceAuthorityState("sensor","sp",1.0,"trusted","unknown")
    q=qualify_evidence_source_from_control_topology(ss,a.topology_assessment,governed_agent_ids=("agent",))
    assert q.control_state=="independent"
