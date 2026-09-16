from pvpp_runtime.models import CandidatePolicySet
from examples.tiny_structural_resolution_world.structural_world import build_runtime

def candidates():
    return (
        CandidatePolicySet("food_policy",("favor_food",),(),("favor_food",)),
        CandidatePolicySet("material_policy",("favor_material",),(),("favor_material",)),
    )

def test_crossing_remains_unresolved_without_binding_constraint():
    rt,state=build_runtime(False)
    a=rt.evaluate_policy_sets(state,candidates())
    assert a.status == "crossing_governing_consequences_unresolved"
    assert a.selected_policy_id is None
    assert set(a.conflicting_domains)=={"F","M"}

def test_binding_constraint_resolves_by_eliminating_one_policy():
    rt,state=build_runtime(True)
    a=rt.evaluate_policy_sets(state,candidates())
    assert a.status == "unique_feasible_adequate_policy_set"
    assert a.selected_policy_id == "food_policy"
    ev={e.policy_id:e for e in a.evaluations}
    assert ev["material_policy"].feasible is False
    assert "binding host constraint" in ev["material_policy"].reasons[0]
