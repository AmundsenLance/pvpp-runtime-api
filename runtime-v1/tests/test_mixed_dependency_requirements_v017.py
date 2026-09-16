import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from examples.tiny_dependency_requirement_world.run_mixed_requirements_v017 import build_runtime, state, candidate


def assess(*ids, **kwargs):
    return build_runtime(**kwargs).evaluate_policy_sets(state(), tuple(candidate(i) for i in ids))


def test_a_survives_b_fails_c_survives_d_remains_available():
    a = assess("keep_a_c")
    s = a.structural_assessment
    assert s.excluded_policy_ids == ()
    assert s.surviving_policy_ids == ("keep_a_c",)


def test_b_survives_a_fails_c_survives_d_remains_available():
    a = assess("keep_b_c")
    s = a.structural_assessment
    assert s.excluded_policy_ids == ()
    assert s.surviving_policy_ids == ("keep_b_c",)


def test_both_substitutes_fail_exhausting_any_of_and_propagating_to_e():
    a = assess("lose_ab_keep_c")
    s = a.structural_assessment
    assert s.excluded_policy_ids == ("lose_ab_keep_c",)
    assert s.requirement_failure_sources("lose_ab_keep_c", "D", "AB_any_supports_D") == ("A", "B")
    assert s.immediate_causes("lose_ab_keep_c", "D") == (("AB_any_supports_D", None),)
    assert s.immediate_causes("lose_ab_keep_c", "E") == (("D_supports_E", "D"),)
    assert s.provenance_path("lose_ab_keep_c", "E") == ("AB_any_supports_D", "D_supports_E")


def test_mandatory_c_failure_makes_d_unavailable_and_propagates_to_e():
    a = assess("keep_a_lose_c")
    s = a.structural_assessment
    assert s.excluded_policy_ids == ("keep_a_lose_c",)
    assert s.requirement_failure_sources("keep_a_lose_c", "D", "C_supports_D") == ("C",)
    assert s.immediate_causes("keep_a_lose_c", "D") == (("C_supports_D", None),)
    assert s.immediate_causes("keep_a_lose_c", "E") == (("D_supports_E", "D"),)
    assert s.provenance_path("keep_a_lose_c", "E") == ("C_supports_D", "D_supports_E")


def test_substitution_is_admissibility_not_preference():
    a = assess("keep_a_c", "keep_b_c")
    assert a.structural_assessment.excluded_policy_ids == ()
    assert set(a.structural_assessment.surviving_policy_ids) == {"keep_a_c", "keep_b_c"}
    assert a.status == "crossing_governing_consequences_unresolved"
    assert set(a.undominated_policy_ids) == {"keep_a_c", "keep_b_c"}
    assert a.selected_policy_id is None


def test_source_order_does_not_change_mixed_requirement_semantics():
    normal = assess("keep_a_c", "keep_b_c", "lose_ab_keep_c", "keep_a_lose_c")
    reversed_sources = assess(
        "keep_a_c", "keep_b_c", "lose_ab_keep_c", "keep_a_lose_c", source_order=("B", "A")
    )
    assert normal.status == reversed_sources.status
    assert set(normal.structural_assessment.excluded_policy_ids) == set(reversed_sources.structural_assessment.excluded_policy_ids)
    assert set(normal.structural_assessment.surviving_policy_ids) == set(reversed_sources.structural_assessment.surviving_policy_ids)
    assert normal.selected_policy_id == reversed_sources.selected_policy_id
    assert set(normal.undominated_policy_ids) == set(reversed_sources.undominated_policy_ids)


def test_requirement_registration_order_does_not_change_semantics():
    normal = assess("keep_a_c", "keep_b_c", "lose_ab_keep_c", "keep_a_lose_c")
    reversed_requirements = assess(
        "keep_a_c", "keep_b_c", "lose_ab_keep_c", "keep_a_lose_c",
        requirement_order=("downstream", "mandatory", "substitutes")
    )
    assert normal.status == reversed_requirements.status
    assert set(normal.structural_assessment.excluded_policy_ids) == set(reversed_requirements.structural_assessment.excluded_policy_ids)
    assert set(normal.structural_assessment.surviving_policy_ids) == set(reversed_requirements.structural_assessment.surviving_policy_ids)
    assert normal.selected_policy_id == reversed_requirements.selected_policy_id
    assert set(normal.undominated_policy_ids) == set(reversed_requirements.undominated_policy_ids)


def test_simultaneous_substitute_exhaustion_and_mandatory_failure_preserve_both_immediate_causes():
    a = assess("lose_ab_c")
    s = a.structural_assessment
    assert s.excluded_policy_ids == ("lose_ab_c",)
    assert s.requirement_failure_sources("lose_ab_c", "D", "AB_any_supports_D") == ("A", "B")
    assert s.requirement_failure_sources("lose_ab_c", "D", "C_supports_D") == ("C",)
    assert set(s.immediate_causes("lose_ab_c", "D")) == {
        ("AB_any_supports_D", None), ("C_supports_D", None)
    }
    assert s.immediate_causes("lose_ab_c", "E") == (("D_supports_E", "D"),)
