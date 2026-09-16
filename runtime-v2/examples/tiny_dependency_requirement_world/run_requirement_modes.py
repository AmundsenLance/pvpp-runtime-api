import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from examples.tiny_dependency_requirement_world.requirement_world import RequirementWorld

def build_runtime(mode):
    r=PVPPRegistry()
    for d in ("A","B","C","D"):
        r.register_domain(DomainDefinition(d,f"Domain {d}",0,3))
        r.register_power(ProductivePowerDefinition(d.lower(),d,f"Power {d}"))
    for aid in ("steady","preserve_b","preserve_c","lose_both"):
        r.register_action(ActionDefinition(aid,aid.replace('_',' '),("A","B","C","D")))
    r.register_dependency_requirement(DependencyRequirementDefinition(
        "BC_supports_D", mode, ("B","C"), "D", 4.5,
        "B and C are either joint prerequisites or substitutes for D."
    ))
    return PVPPRuntime(r,RequirementWorld())

def state():
    return WorldState(0,{d.lower():ProductivePowerState(d.lower(),25) for d in ("A","B","C","D")})

def candidate(aid):
    return CandidatePolicySet(aid,(aid,),(),(aid,))

if __name__=="__main__":
    for mode in ("all_of","any_of"):
        rt=build_runtime(mode)
        a=rt.evaluate_policy_sets(state(),(candidate("preserve_b"),candidate("preserve_c")))
        print(mode,"one substitute survives")
        print(" status=",a.status)
        print(" excluded=",a.structural_assessment.excluded_policy_ids)
        for p in ("preserve_b","preserve_c"):
            print(" ",p,"failed sources=",a.structural_assessment.requirement_failure_sources(p,"D","BC_supports_D"))
        print()
    rt=build_runtime("any_of")
    a=rt.evaluate_policy_sets(state(),(candidate("preserve_b"),candidate("lose_both")))
    print("any_of both substitutes lost")
    print(" status=",a.status)
    print(" selected=",a.selected_policy_id)
    print(" excluded=",a.structural_assessment.excluded_policy_ids)
    print(" failed sources=",a.structural_assessment.requirement_failure_sources("lose_both","D","BC_supports_D"))
