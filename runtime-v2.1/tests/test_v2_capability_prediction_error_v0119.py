from pvpp_runtime import *


def traj(snapshot="s2", entity="agent", cap="tool", asof=20):
    o=CapabilityChangeObservation("o1",entity,cap,asof,"increased","s1",snapshot,"sensor","pobs",.9)
    return project_capability_trajectory("tr1",(o,),as_of=asof)

def exp(snapshot="s2", **kw):
    d=dict(expectation_id="e1",entity_id="agent",capability_id="tool",expected_at=15,expected_snapshot_id=snapshot,source_id="model",provenance_id="pexp",configuration_ids=("cfg",))
    d.update(kw); return CapabilityFormationExpectation(**d)

def dep(stage="Graph/Seed", **kw):
    d=dict(dependency_id="d1",expectation_id="e1",artifact_id="graph-old",stage=stage,provenance_ids=("pdep",))
    d.update(kw); return CapabilityPredictionArtifactDependency(**d)

def test_matching_expectation_creates_no_prediction_error_or_invalidation():
    a=assess_capability_formation_prediction_error(exp("s2"),traj("s2"),(dep(),),error_id="err")
    assert a.valid and a.prediction_error is None and not a.invalidation_signals and a.reentry_plan.recompute_from_stage is None

def test_mismatch_is_provenance_bearing_non_scalar_prediction_error():
    a=assess_capability_formation_prediction_error(exp("EXPECTED"),traj("OBSERVED"),(dep(),),error_id="err")
    assert a.valid and a.prediction_error.expected_snapshot_id=="EXPECTED" and a.prediction_error.observed_snapshot_id=="OBSERVED"
    assert "pexp" in a.invalidation_signals[0].evidence_ids and "pobs" in a.invalidation_signals[0].evidence_ids

def test_mismatch_invalidates_only_explicit_declared_artifact():
    a=assess_capability_formation_prediction_error(exp("x"),traj("y"),(dep(),),error_id="err")
    assert a.invalidation_signals[0].artifact_ids==("graph-old",) and a.reentry_plan.recompute_from_stage=="Graph/Seed"

def test_no_declared_dependency_means_no_inferred_canonical_stage():
    a=assess_capability_formation_prediction_error(exp("x"),traj("y"),(),error_id="err")
    assert a.valid and a.prediction_error and not a.invalidation_signals and a.reentry_plan.recompute_from_stage is None

def test_multiple_declared_dependencies_choose_earliest_stage():
    ds=(dep("Sigma"),dep("Phi",dependency_id="d2",artifact_id="phi-old"))
    a=assess_capability_formation_prediction_error(exp("x"),traj("y"),ds,error_id="err")
    assert a.reentry_plan.recompute_from_stage=="Phi" and len(a.invalidation_signals)==2

def test_expectation_must_match_entity_and_capability():
    a=assess_capability_formation_prediction_error(exp("x",entity_id="other"),traj("y"),(dep(),),error_id="err")
    assert not a.valid and not a.invalidation_signals

def test_expectation_cannot_be_evaluated_before_expected_time():
    a=assess_capability_formation_prediction_error(exp("x",expected_at=30),traj("y",asof=20),(dep(),),error_id="err")
    assert not a.valid

def test_prediction_error_creates_no_execution_or_graph_admission_authority():
    a=assess_capability_formation_prediction_error(exp("x"),traj("y"),(dep(),),error_id="err")
    assert a.valid and not hasattr(a,"execution_result") and not hasattr(a,"admission_request")
