from pvpp_runtime import *

def rel(i,s,o,t="controls",active=True,at=1.0):
    return ControlProvenanceRelation(i,s,o,t,at,"host","prov",active,("e",))

def source(i="sensor"):
    return EvidenceSourceAuthorityState(i,"sp",1.0,"trusted","unknown")

def test_explicit_control_marks_source_governed():
    a=assess_control_provenance_topology((rel("r","agent","sensor"),),topology_id="t",as_of=2,governed_agent_ids=("agent",))
    assert a.valid and "sensor" in a.controlled_by_governed_agent
    assert qualify_evidence_source_from_control_topology(source(),a,governed_agent_ids=("agent",)).control_state=="governed_agent"

def test_descendant_chain_is_explicitly_closed():
    a=assess_control_provenance_topology((rel("r1","agent","child","descends_from"),rel("r2","child","sensor","descends_from")),topology_id="t",as_of=2,governed_agent_ids=("agent",))
    assert a.descendant_objects==("child","sensor")
    assert qualify_evidence_source_from_control_topology(source(),a).control_state=="descendant"

def test_inactive_edge_does_not_control():
    a=assess_control_provenance_topology((rel("r","agent","sensor",active=False),),topology_id="t",as_of=2,governed_agent_ids=("agent",))
    assert qualify_evidence_source_from_control_topology(source(),a).control_state=="independent"

def test_duplicate_relation_ids_fail():
    a=assess_control_provenance_topology((rel("r","a","b"),rel("r","a","c")),topology_id="t",as_of=2)
    assert not a.valid

def test_future_observation_fails():
    assert not assess_control_provenance_topology((rel("r","a","b",at=3),),topology_id="t",as_of=2).valid

def test_self_relation_fails():
    assert not assess_control_provenance_topology((rel("r","a","a"),),topology_id="t",as_of=2).valid

def test_invalid_topology_cannot_qualify_source():
    a=assess_control_provenance_topology((rel("r","a","a"),),topology_id="t",as_of=2)
    try: qualify_evidence_source_from_control_topology(source(),a)
    except ValueError: pass
    else: assert False

def test_qualified_control_flows_into_existing_evidence_authority_logic():
    a=assess_control_provenance_topology((rel("r","agent","sensor"),),topology_id="t",as_of=2,governed_agent_ids=("agent",))
    ss=qualify_evidence_source_from_control_topology(source(),a,governed_agent_ids=("agent",))
    dep=GovernanceEvidenceDependency("d","f","o","sensor","sp","primary")
    q=assess_evidence_dependency_authority(dep,ss,as_of=2)
    assert q.valid and not q.retains_epistemic_authority and q.loss_reason=="source_controlled_by_governed_agent"
