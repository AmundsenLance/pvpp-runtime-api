from pvpp_runtime import DomainRelationDefinition
from examples.tiny_dependency_closure_world.run_dependency_closure import build_runtime, state, candidates

def test_three_domain_crossing_is_unresolved_without_structure():
    a=build_runtime(False).evaluate_policy_sets(state(),candidates())
    assert a.status == "crossing_governing_consequences_unresolved"
    assert a.selected_policy_id is None
    assert set(a.conflicting_domains)=={"A","B","C"}

def test_dependency_closure_excludes_policy_and_preserves_path_provenance():
    a=build_runtime(True).evaluate_policy_sets(state(),candidates())
    assert a.status == "unique_structurally_admissible_policy_set"
    assert a.selected_policy_id == "upstream_policy"
    s=a.structural_assessment
    assert s.excluded_policy_ids == ("downstream_policy",)
    assert s.provenance_path("downstream_policy","B") == ("A_supports_B",)
    assert s.provenance_path("downstream_policy","C") == ("A_supports_B","B_supports_C")

def test_cycle_in_registered_structure_terminates_and_does_not_duplicate_forever():
    rt=build_runtime(True)
    rt.registry.register_domain_relation(DomainRelationDefinition("C_supports_A","dependency_floor","C","A",3.0))
    a=rt.evaluate_policy_sets(state(),candidates())
    assert a.selected_policy_id == "upstream_policy"
    graph=a.structural_assessment.provenance["downstream_policy"]
    assert len(graph) <= 3
    assert len(a.structural_assessment.provenance_path("downstream_policy","C")) <= 3

def test_nonbinding_chain_does_not_create_preference():
    rt=build_runtime(False)
    rt.registry.register_domain_relation(DomainRelationDefinition("A_supports_B","dependency_floor","A","B",3.5))
    rt.registry.register_domain_relation(DomainRelationDefinition("B_supports_C","dependency_floor","B","C",3.5))
    a=rt.evaluate_policy_sets(state(),candidates())
    assert a.status == "crossing_governing_consequences_unresolved"
    assert a.selected_policy_id is None
    assert a.structural_assessment.status == "registered_structure_nonbinding"
