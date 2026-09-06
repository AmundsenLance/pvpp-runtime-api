import pytest
from pvpp_runtime import CandidatePolicySet, DependencyRequirementDefinition, DomainDefinition, PVPPRegistry
from examples.tiny_dependency_requirement_world.run_requirement_modes import build_runtime, state, candidate

def test_all_of_requires_every_source():
    a=build_runtime("all_of").evaluate_policy_sets(state(),(candidate("preserve_b"),candidate("preserve_c")))
    assert a.status == "no_structurally_admissible_policy_set"
    assert set(a.structural_assessment.excluded_policy_ids) == {"preserve_b","preserve_c"}
    assert a.structural_assessment.requirement_failure_sources("preserve_b","D","BC_supports_D") == ("C",)
    assert a.structural_assessment.requirement_failure_sources("preserve_c","D","BC_supports_D") == ("B",)

def test_any_of_preserves_target_when_one_substitute_survives():
    a=build_runtime("any_of").evaluate_policy_sets(state(),(candidate("preserve_b"),candidate("preserve_c")))
    assert a.status == "crossing_governing_consequences_unresolved"
    assert a.selected_policy_id is None
    assert a.structural_assessment.excluded_policy_ids == ()

def test_any_of_fails_only_when_all_substitutes_fail():
    a=build_runtime("any_of").evaluate_policy_sets(state(),(candidate("preserve_b"),candidate("lose_both")))
    assert a.status == "unique_structurally_admissible_policy_set"
    assert a.selected_policy_id == "preserve_b"
    assert a.structural_assessment.excluded_policy_ids == ("lose_both",)
    assert a.structural_assessment.requirement_failure_sources("lose_both","D","BC_supports_D") == ("B","C")

def test_requirement_validation_rejects_empty_sources_and_unknown_mode():
    r=PVPPRegistry()
    r.register_domain(DomainDefinition("D","D",0,None))
    with pytest.raises(ValueError):
        r.register_dependency_requirement(DependencyRequirementDefinition("bad","any_of",(),"D",1))
    with pytest.raises(ValueError):
        r.register_dependency_requirement(DependencyRequirementDefinition("bad2","xor_of",("D",),"D",1))

def test_any_of_source_order_does_not_change_admissibility():
    from pvpp_runtime import ActionDefinition, ProductivePowerDefinition, PVPPRuntime
    from examples.tiny_dependency_requirement_world.requirement_world import RequirementWorld
    def build(sources):
        r=PVPPRegistry()
        for d in ("A","B","C","D"):
            r.register_domain(DomainDefinition(d,d,0,3))
            r.register_power(ProductivePowerDefinition(d.lower(),d,d))
        for aid in ("steady","preserve_b","preserve_c"):
            r.register_action(ActionDefinition(aid,aid,("A","B","C","D")))
        r.register_dependency_requirement(DependencyRequirementDefinition("BC_supports_D","any_of",sources,"D",4.5))
        return PVPPRuntime(r,RequirementWorld())
    a=build(("B","C")).evaluate_policy_sets(state(),(candidate("preserve_b"),candidate("preserve_c")))
    b=build(("C","B")).evaluate_policy_sets(state(),(candidate("preserve_b"),candidate("preserve_c")))
    assert a.status == b.status == "crossing_governing_consequences_unresolved"
    assert a.selected_policy_id is b.selected_policy_id is None
