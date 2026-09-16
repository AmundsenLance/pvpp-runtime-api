from pvpp_runtime import *

def rel(i,s,o,t="controls",active=True,at=1.0):
    return ControlProvenanceRelation(i,s,o,t,at,"host","rp",active,("e",))

def update(newrels):
    p=assess_control_provenance_topology((rel("r1","agent","sensor"),rel("r2","agent","tool","delegates")),topology_id="t",as_of=2,governed_agent_ids=("agent",))
    q=ControlProvenanceTopologyUpdateRequest("u",control_provenance_topology_identity(p),"t",3,tuple(newrels),("agent",),"cfg3","host","up","observed topology change")
    return update_control_provenance_topology(p,q)

def dep(i,artifact,stage,rids,types=()): return ControlProvenanceArtifactDependency(i,artifact,stage,tuple(rids),tuple(types),("dp",))

def test_changed_relation_invalidates_declared_non_evidence_artifact():
    u=update((rel("r1","agent","sensor",active=False,at=3),rel("r2","agent","tool","delegates")))
    a=derive_control_provenance_governance_invalidations(u,(dep("d","g-art","G",("r1",)),))
    assert a.valid and a.reentry.recompute_from_stage=="G" and a.plan.recompute_from_stage=="G"

def test_earliest_stage_selected_across_explicit_matches():
    u=update((rel("r1","agent","sensor",active=False,at=3),))
    a=derive_control_provenance_governance_invalidations(u,(dep("late","c","Constraints",("r1",)),dep("early","g","G",("r2",))))
    assert a.reentry.recompute_from_stage=="G" and set(a.matched_dependency_ids)=={"late","early"}

def test_unmatched_topology_change_creates_no_invalidation():
    u=update((rel("r1","agent","sensor"),rel("r2","agent","tool","delegates"),rel("r3","agent","x",at=3)))
    a=derive_control_provenance_governance_invalidations(u,(dep("d","g","G",("other",)),))
    assert a.valid and not a.invalidation_signals and not a.reentry.return_to_governance

def test_removed_relation_matches_by_explicit_identity():
    u=update((rel("r1","agent","sensor"),))
    a=derive_control_provenance_governance_invalidations(u,(dep("d","a","Adequacy",("r2",),("delegates",)),))
    assert a.reentry.recompute_from_stage=="Adequacy"

def test_relation_type_filter_blocks_wrong_current_type():
    u=update((rel("r1","agent","sensor",active=False,at=3),rel("r2","agent","tool","delegates")))
    a=derive_control_provenance_governance_invalidations(u,(dep("d","g","G",("r1",),("delegates",)),))
    assert not a.invalidation_signals

def test_rejected_update_cannot_invalidate():
    p=assess_control_provenance_topology((rel("r1","agent","sensor"),),topology_id="t",as_of=2,governed_agent_ids=("agent",))
    q=ControlProvenanceTopologyUpdateRequest("u","stale","t",3,p.relations,("agent",),"cfg","host","up","x")
    u=update_control_provenance_topology(p,q)
    a=derive_control_provenance_governance_invalidations(u,(dep("d","g","G",("r1",)),))
    assert not a.valid and not a.invalidation_signals

def test_duplicate_dependency_ids_fail_closed():
    u=update((rel("r1","agent","sensor",active=False,at=3),rel("r2","agent","tool","delegates")))
    d=dep("same","g","G",("r1",))
    a=derive_control_provenance_governance_invalidations(u,(d,d))
    assert not a.valid

def test_no_selection_or_execution_authority_is_created():
    u=update((rel("r1","agent","sensor",active=False,at=3),rel("r2","agent","tool","delegates")))
    a=derive_control_provenance_governance_invalidations(u,(dep("d","g","G",("r1",)),))
    assert a.reentry.return_to_governance and not hasattr(a,"sigma") and not hasattr(a,"execution_result")
