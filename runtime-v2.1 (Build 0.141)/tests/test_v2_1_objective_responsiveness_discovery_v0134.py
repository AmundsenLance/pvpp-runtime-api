from dataclasses import replace
import pytest

from pvpp_runtime import (
    ActualPersistentStateEnvelope, WorldState, ActionDefinition, DomainDefinition, PVPPRegistry, PVPPRuntime,
    QualifiedObjectiveRecord, ObjectiveSet, ObjectiveResponsivenessRecord,
    ObjectiveResponsivenessAssessment, ObjectiveDiscoveryHint, CandidatePolicySet,
    CandidatePolicySpace, GraphInstanceDefinition, GraphTransformationDefinition,
    PreliminaryPreservationObject,
)


class World:
    def represented_state_from_actual(self, actual):
        return WorldState(time=actual.time, powers={}, metadata={"state_id":actual.state_id})


def state():
    return ActualPersistentStateEnvelope("actor","s1",10.0,{},{},{},{})


def objective(oid="o1"):
    return QualifiedObjectiveRecord(oid,"restore service","self-adopted","task",authority={"basis":"self"},version="v1")


def objectives(*objs):
    return ObjectiveSet("actor",10.0,tuple(objs),"os1","v1")


def space():
    return CandidatePolicySpace((
        CandidatePolicySet("direct",("a",),policy_class_ids=("continuation",)),
        CandidatePolicySet("prereq",("b",),policy_class_ids=("repair",)),
    ),("continuation","repair"))


def runtime(with_graph=False):
    r=PVPPRegistry()
    r.register_domain(DomainDefinition("D","D",0.0))
    r.register_action(ActionDefinition("steady","steady",()))
    r.register_action(ActionDefinition("a","a",()))
    r.register_action(ActionDefinition("b","b",()))
    if with_graph:
        r.register_graph_instance(GraphInstanceDefinition("i","state",("D",),"current"))
        r.register_graph_transformation(GraphTransformationDefinition("t","i","i","continuation",("D",),"reachable","a"))
    return PVPPRuntime(r,World())


class RespAdapter:
    def objective_responsiveness(self, st, policy_id, action_ids, obj):
        relation={"direct":"supports","prereq":"neutral"}[policy_id]
        return ObjectiveResponsivenessRecord(policy_id,obj.id,relation,evidence={"native":True},provenance="app-v1")


def test_resp_emits_every_candidate_objective_pair_without_pruning():
    rt=runtime(); sp=space(); os=objectives(objective(),objective("o2"))
    a=rt.evaluate_objective_responsiveness(WorldState(10.0,{}),sp,os,RespAdapter())
    assert a.valid
    assert len(a.records)==4
    assert {r.policy_id for r in a.records}=={"direct","prereq"}
    assert {r.objective_id for r in a.records}=={"o1","o2"}
    assert tuple(c.id for c in sp.candidates)==("direct","prereq")


def test_resp_labels_are_closed_and_application_supplied():
    class Bad:
        def objective_responsiveness(self, st,pid,aids,obj):
            return ObjectiveResponsivenessRecord(pid,obj.id,"preferred")
    a=runtime().evaluate_objective_responsiveness(WorldState(10.0,{}),space(),objectives(objective()),Bad())
    assert not a.valid
    assert "invalid relation" in a.violations[0]


def test_resp_identity_mismatch_is_rejected():
    class Bad:
        def objective_responsiveness(self, st,pid,aids,obj):
            return ObjectiveResponsivenessRecord("other",obj.id,"supports")
    a=runtime().evaluate_objective_responsiveness(WorldState(10.0,{}),space(),objectives(objective()),Bad())
    assert not a.valid
    assert any("identity mismatch" in x for x in a.violations)


def test_no_adapter_leaves_relation_unresolved_by_runtime_not_fabricated():
    a=runtime().evaluate_objective_responsiveness(WorldState(10.0,{}),space(),objectives(objective()),None)
    assert a.valid and a.records==()
    assert any("unresolved by the runtime" in n for n in a.notes)


def test_resp_record_has_no_ranking_authority_or_gate_fields():
    names=set(ObjectiveResponsivenessRecord.__dataclass_fields__)
    forbidden={"rank","weight","utility","authorized","admitted","adequate","viable","selected"}
    assert not (names & forbidden)


def test_discovery_hint_may_reference_only_registered_graph_structure():
    rt=runtime(with_graph=True); os=objectives(objective())
    a=rt.validate_objective_discovery_hints(os,(ObjectiveDiscoveryHint("o1",("t",),("i",),("cue",),"app"),))
    assert a.valid
    assert a.referenced_transformation_ids==("t",)
    assert a.referenced_instance_ids==("i",)
    assert a.retrieval_cues==("cue",)


def test_discovery_hint_cannot_invent_graph_structure():
    rt=runtime(with_graph=True); os=objectives(objective())
    a=rt.validate_objective_discovery_hints(os,(ObjectiveDiscoveryHint("o1",("future_capability_path",),(),()),))
    assert not a.valid
    assert any("unregistered graph transformation" in x for x in a.violations)


def test_discovery_hint_cannot_reference_inactive_or_absent_objective():
    rt=runtime(with_graph=True); os=objectives(objective())
    a=rt.validate_objective_discovery_hints(os,(ObjectiveDiscoveryHint("missing",("t",),(),()),))
    assert not a.valid
    assert any("inactive or absent objective" in x for x in a.violations)


def test_discovery_hints_require_active_O():
    a=runtime(with_graph=True).validate_objective_discovery_hints(None,(ObjectiveDiscoveryHint("o1",("t",),(),()),))
    assert not a.valid


def test_objective_relevance_does_not_change_graph_admission_or_reachability():
    rt=runtime(with_graph=True); os=objectives(objective())
    before=rt.construct_graph(PreliminaryPreservationObject("p","preserve"),"ordinary",("D",))
    hint=ObjectiveDiscoveryHint("o1",("t",),("i",),())
    da=rt.validate_objective_discovery_hints(os,(hint,))
    after=rt.construct_graph(PreliminaryPreservationObject("p","preserve"),"ordinary",("D",))
    assert da.valid
    assert before==after
    assert before.validated_transformation_ids==("t",)


def test_objective_relevance_cannot_make_unreachable_transformation_reachable():
    rt=runtime(with_graph=True); os=objectives(objective())
    tr=rt.registry.graph_transformations["t"]
    rt.registry.graph_transformations["t"]=replace(tr,reachability_status="unreachable")
    da=rt.validate_objective_discovery_hints(os,(ObjectiveDiscoveryHint("o1",("t",),(),()),))
    graph=rt.construct_graph(PreliminaryPreservationObject("p","preserve"),"ordinary",("D",))
    assert da.valid
    assert "t" in graph.excluded_transformation_ids
    assert "t" not in graph.validated_transformation_ids


def test_resp_does_not_change_pi_completeness():
    rt=runtime(); sp=space(); os=objectives(objective())
    before=rt.validate_pi_completeness(sp)
    resp=rt.evaluate_objective_responsiveness(WorldState(10.0,{}),sp,os,RespAdapter())
    after=rt.validate_pi_completeness(sp)
    assert resp.valid
    assert before==after


def test_conflicting_objectives_do_not_create_runtime_ordering_in_resp():
    os=objectives(objective("o1"),objective("o2"))
    a=runtime().evaluate_objective_responsiveness(WorldState(10.0,{}),space(),os,RespAdapter())
    assert a.valid
    assert [r.objective_id for r in a.records if r.policy_id=="direct"]==["o1","o2"]


def test_indirect_policy_not_pruned_for_neutral_resp():
    sp=space(); a=runtime().evaluate_objective_responsiveness(WorldState(10.0,{}),sp,objectives(objective()),RespAdapter())
    assert a.valid
    neutral=[r for r in a.records if r.policy_id=="prereq"][0]
    assert neutral.relation=="neutral"
    assert any(c.id=="prereq" for c in sp.candidates)


def test_impossible_objective_does_not_fabricate_supporting_policy():
    class Unresolved:
        def objective_responsiveness(self, st,pid,aids,obj):
            return ObjectiveResponsivenessRecord(pid,obj.id,"unresolved")
    sp=space(); a=runtime().evaluate_objective_responsiveness(WorldState(10.0,{}),sp,objectives(objective()),Unresolved())
    assert a.valid
    assert all(r.relation=="unresolved" for r in a.records)
    assert {r.policy_id for r in a.records}=={"direct","prereq"}
