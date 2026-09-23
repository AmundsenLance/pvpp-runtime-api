from dataclasses import replace
import pytest

from pvpp_runtime import (
    ActualPersistentStateEnvelope, ObjectiveTemporalBounds, ObjectiveRelation,
    QualifiedObjectiveRecord, ObjectiveSet, WorldState, ActionDefinition, PVPPRuntime, PVPPRegistry,
)


class ObjectiveWorld:
    def represented_state_from_actual(self, actual):
        return WorldState(time=actual.time, powers={}, metadata={"state_id": actual.state_id})


def runtime():
    r=PVPPRegistry(); r.register_action(ActionDefinition("steady","steady",()))
    return PVPPRuntime(r, ObjectiveWorld())


def state(t=10.0):
    return ActualPersistentStateEnvelope("actor", "s1", t, {}, {}, {}, {})


def objective(oid="o1", **kw):
    base=dict(id=oid, content="maintain condition", source="self-adopted", scope="task", status="active", authority={"basis":"self-adopted"}, version="v1")
    base.update(kw)
    return QualifiedObjectiveRecord(**base)


def objectives(*items, t=10.0):
    return ObjectiveSet("actor", t, tuple(items), "os1", "v1")


def test_objective_free_viability_input_is_valid():
    a=runtime().validate_objective_set(None,state())
    assert a.valid
    assert "objective-free viability analysis remains valid" in a.notes


def test_active_objective_set_validates_and_is_adjacent_to_p_not_inside_it():
    rt=runtime(); st=state()
    os=objectives(objective())
    snap=rt.prepare_canonical_cycle_snapshot(st,os)
    assert snap.objective_set is os
    assert snap.perceived_decision_state is not None
    assert not hasattr(snap.perceived_decision_state,"objective_set")
    assert snap.actual_state is st


def test_conflicting_objectives_can_coexist_without_runtime_ordering():
    a=objective("a",relations=(ObjectiveRelation("b","conflict"),))
    b=objective("b",relations=(ObjectiveRelation("a","conflict"),))
    assessment=runtime().validate_objective_set(objectives(a,b),state())
    assert assessment.valid
    assert [x.id for x in objectives(a,b).objectives] == ["a","b"]


@pytest.mark.parametrize("status",["suspended","completed","abandoned","expired"])
def test_inactive_lifecycle_status_cannot_remain_in_active_O(status):
    a=runtime().validate_objective_set(objectives(objective(status=status)),state())
    assert not a.valid
    assert any(status in v and "cannot remain in active O_i(t)" in v for v in a.violations)


def test_objective_actor_and_time_must_match_cycle():
    rt=runtime(); st=state()
    wrong_actor=replace(objectives(objective()),actor_id="other")
    wrong_time=replace(objectives(objective()),time=11.0)
    assert not rt.validate_objective_set(wrong_actor,st).valid
    assert not rt.validate_objective_set(wrong_time,st).valid


def test_duplicate_objective_identity_rejected():
    a=runtime().validate_objective_set(objectives(objective(),objective()),state())
    assert not a.valid
    assert any("duplicate objective id" in v for v in a.violations)


def test_temporally_not_yet_applicable_or_expired_rejected():
    rt=runtime(); st=state(10.0)
    future=objective(temporal_bounds=ObjectiveTemporalBounds(start=11.0))
    expired=objective("o2",temporal_bounds=ObjectiveTemporalBounds(expiration=10.0))
    assert not rt.validate_objective_set(objectives(future),st).valid
    assert not rt.validate_objective_set(objectives(expired),st).valid


def test_objective_content_source_scope_and_version_are_required():
    rt=runtime(); st=state()
    bad=QualifiedObjectiveRecord("",None,"","",authority=None,version="")
    a=rt.validate_objective_set(objectives(bad),st)
    assert not a.valid
    joined=" | ".join(a.violations)
    for token in ("stable id","content","source","scope","authority/provenance","version"):
        assert token in joined


def test_objective_record_does_not_expose_utility_ranking_or_execution_authority_fields():
    names=set(QualifiedObjectiveRecord.__dataclass_fields__)
    forbidden={"utility","weight","rank","selected_policy_id","execution_authority","adequacy","viability"}
    assert not (names & forbidden)


def test_objective_set_does_not_mutate_actual_state_or_perceived_state_semantics():
    rt=runtime(); st=state(); os=objectives(objective())
    snap0=rt.prepare_canonical_cycle_snapshot(st,None)
    snap1=rt.prepare_canonical_cycle_snapshot(st,os)
    assert snap0.actual_state == snap1.actual_state == st
    assert snap0.represented_state == snap1.represented_state
    assert snap0.perceived_decision_state == snap1.perceived_decision_state
    assert snap0.objective_set is None and snap1.objective_set is os
