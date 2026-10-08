from examples.tiny_branching_dependency_world.run_branching_dependency import build_runtime, state, candidates

def test_branching_case_is_crossing_without_registered_structure():
    a=build_runtime(None).evaluate_policy_sets(state(),candidates())
    assert a.status == "crossing_governing_consequences_unresolved"
    assert a.selected_policy_id is None

def test_binding_branching_structure_resolves_by_admissibility():
    a=build_runtime(True).evaluate_policy_sets(state(),candidates())
    assert a.status == "unique_structurally_admissible_policy_set"
    assert a.selected_policy_id == "root_policy"
    s=a.structural_assessment
    assert s.excluded_policy_ids == ("branch_policy",)
    assert set(s.immediate_causes("branch_policy","D")) == {
        ("B_supports_D","B"), ("C_supports_D","C")
    }
    assert s.provenance_path("branch_policy","D") in {
        ("A_supports_B","B_supports_D"),
        ("A_supports_C","C_supports_D"),
    }

def test_nonbinding_branching_topology_does_not_create_priority():
    a=build_runtime(False).evaluate_policy_sets(state(),candidates())
    assert a.status == "crossing_governing_consequences_unresolved"
    assert a.selected_policy_id is None
    assert a.structural_assessment.status == "registered_structure_nonbinding"

def test_relation_registration_order_does_not_change_selection_or_converging_causes():
    a=build_runtime(True,False).evaluate_policy_sets(state(),candidates())
    b=build_runtime(True,True).evaluate_policy_sets(state(),candidates())
    assert a.selected_policy_id == b.selected_policy_id == "root_policy"
    assert set(a.structural_assessment.immediate_causes("branch_policy","D")) == set(
        b.structural_assessment.immediate_causes("branch_policy","D")
    )
