from pvpp_runtime import CandidatePolicySet, DomainRelationDefinition
from examples.tiny_crossing_policy_world.run_crossing_choice import build_runtime, state

def candidates():
    return (
        CandidatePolicySet("food_policy",("favor_food",),(),("favor_food",)),
        CandidatePolicySet("material_policy",("favor_material",),(),("favor_material",)),
    )

def test_crossing_stays_unresolved_without_registered_relation():
    rt=build_runtime()
    a=rt.evaluate_policy_sets(state(),candidates())
    assert a.status == "crossing_governing_consequences_unresolved"
    assert a.selected_policy_id is None
    assert a.structural_assessment.status == "no_registered_policy_structure"

def test_registered_dependency_floor_can_resolve_crossing_without_ranking():
    rt=build_runtime()
    rt.registry.register_domain_relation(DomainRelationDefinition(
        "F_supports_M","dependency_floor","F","M",4.25,
        "M depends on preserving a registered F horizon floor."
    ))
    a=rt.evaluate_policy_sets(state(),candidates())
    assert a.status == "unique_structurally_admissible_policy_set"
    assert a.selected_policy_id == "food_policy"
    assert a.structural_assessment.excluded_policy_ids == ("material_policy",)
    assert a.structural_assessment.surviving_policy_ids == ("food_policy",)
    assert "F horizon 4" in a.structural_assessment.reasons[0]

def test_nonbinding_registered_relation_does_not_create_preference():
    rt=build_runtime()
    rt.registry.register_domain_relation(DomainRelationDefinition(
        "F_supports_M","dependency_floor","F","M",3.5
    ))
    a=rt.evaluate_policy_sets(state(),candidates())
    assert a.status == "crossing_governing_consequences_unresolved"
    assert a.selected_policy_id is None
    assert a.structural_assessment.status == "registered_structure_nonbinding"
