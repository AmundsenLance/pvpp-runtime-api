import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pvpp_runtime import *
from examples.tiny_dependency_requirement_world.mixed_requirement_world import MixedRequirementWorld


def build_runtime(source_order=("A", "B"), requirement_order=("substitutes", "mandatory", "downstream")):
    r = PVPPRegistry()
    for d in ("A", "B", "C", "D", "E"):
        r.register_domain(DomainDefinition(d, f"Domain {d}", 0, 3))
        r.register_power(ProductivePowerDefinition(d.lower(), d, f"Power {d}"))
    for aid in ("steady", "keep_a_c", "keep_b_c", "lose_ab_keep_c", "keep_a_lose_c", "lose_ab_c"):
        r.register_action(ActionDefinition(aid, aid.replace("_", " "), ("A", "B", "C", "D", "E")))
    defs = {
        "substitutes": DependencyRequirementDefinition("AB_any_supports_D", "any_of", tuple(source_order), "D", 4.5),
        "mandatory": DependencyRequirementDefinition("C_supports_D", "all_of", ("C",), "D", 4.5),
        "downstream": DependencyRequirementDefinition("D_supports_E", "all_of", ("D",), "E", 4.5),
    }
    for key in requirement_order:
        r.register_dependency_requirement(defs[key])
    return PVPPRuntime(r, MixedRequirementWorld())


def state():
    return WorldState(0, {d.lower(): ProductivePowerState(d.lower(), 25) for d in ("A", "B", "C", "D", "E")})


def candidate(aid):
    return CandidatePolicySet(aid, (aid,), (), (aid,))


if __name__ == "__main__":
    rt = build_runtime()
    result = rt.evaluate_policy_sets(state(), tuple(candidate(a) for a in (
        "keep_a_c", "keep_b_c", "lose_ab_keep_c", "keep_a_lose_c"
    )))
    print("status=", result.status)
    print("survivors=", result.structural_assessment.surviving_policy_ids)
    print("excluded=", result.structural_assessment.excluded_policy_ids)
    for pid in result.structural_assessment.excluded_policy_ids:
        print(pid, "D causes=", result.structural_assessment.immediate_causes(pid, "D"))
        print(pid, "E causes=", result.structural_assessment.immediate_causes(pid, "E"))
        print(pid, "D witness=", result.structural_assessment.provenance_path(pid, "D"))
        print(pid, "E witness=", result.structural_assessment.provenance_path(pid, "E"))
