from benchmarks.benchmark_small_economy_v2_1_v0140 import run_benchmark, assert_benchmark_invariants


def results():
    return {r.case_id:r for r in run_benchmark()}


def test_small_economy_all_eight_cases_execute():
    rs=run_benchmark(); assert len(rs)==8; assert assert_benchmark_invariants(rs)

def test_attainable_objective_is_descriptive_not_graph_authority():
    r=results()["attainable"]
    assert ("expand","o_output","supports") in r.responsiveness and "t_teleport" in r.graph_excluded

def test_conflicting_objectives_coexist_without_pruning():
    r=results()["conflicting"]
    assert ("expand","o_output","supports") in r.responsiveness
    assert ("expand","o_work","conflicts") in r.responsiveness
    assert r.candidate_ids==("maintain","expand","train")

def test_objective_support_does_not_become_viability_override():
    r=results()["objective_vs_viability"]
    assert ("expand","o_anycost","supports") in r.responsiveness
    assert "maintain" in r.candidate_ids

def test_impossible_objective_does_not_create_reachability():
    r=results()["impossible"]
    assert "t_teleport" in r.graph_excluded and "t_teleport" not in r.graph_validated

def test_capability_development_uses_current_reachable_means_only():
    r=results()["capability_development"]
    assert "t_train" in r.graph_validated and "t_teleport" in r.graph_excluded
    assert ("train","o_skill","supports") in r.responsiveness

def test_lifecycle_change_reenters_at_explicit_dependency_not_phi():
    assert results()["lifecycle"].lifecycle_reentry_stage=="Graph/Seed"

def test_relevant_but_prohibited_evidence_stays_noncurrent_positive():
    assert results()["unauthorized_evidence"].memory_governance_current_positive is False

def test_no_objective_control_remains_valid():
    r=results()["no_objective"]
    assert r.objective_ids==() and r.responsiveness==()

def test_objective_perturbations_do_not_change_graph_substrate():
    rs=results(); b=rs["no_objective"]
    for r in rs.values(): assert r.graph_validated==b.graph_validated and r.graph_excluded==b.graph_excluded

def test_objective_perturbations_do_not_change_candidate_substrate():
    rs=results(); b=rs["no_objective"]
    for r in rs.values(): assert r.candidate_ids==b.candidate_ids
