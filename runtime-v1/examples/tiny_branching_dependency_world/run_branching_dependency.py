import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from examples.tiny_branching_dependency_world.branching_world import BranchingDependencyWorld

def build_runtime(binding=True, reverse=False):
    r=PVPPRegistry()
    for d in ("A","B","C","D"):
        r.register_domain(DomainDefinition(d,f"Domain {d}",0,3))
        r.register_power(ProductivePowerDefinition(d.lower(),d,f"Power {d}"))
    r.register_action(ActionDefinition("steady","No intervention",("A","B","C","D")))
    r.register_action(ActionDefinition("root_secure","Preserve root prerequisite",("A","B","C","D")))
    r.register_action(ActionDefinition("branch_boost","Favor downstream branches",("A","B","C","D")))
    if binding is not None:
        floor=4.25 if binding else 3.5
        rels=[
            DomainRelationDefinition("A_supports_B","dependency_floor","A","B",floor),
            DomainRelationDefinition("A_supports_C","dependency_floor","A","C",floor),
            DomainRelationDefinition("B_supports_D","dependency_floor","B","D",floor),
            DomainRelationDefinition("C_supports_D","dependency_floor","C","D",floor),
        ]
        if reverse:
            rels.reverse()
        for rel in rels:
            r.register_domain_relation(rel)
    return PVPPRuntime(r,BranchingDependencyWorld())

def state():
    return WorldState(0,{d.lower():ProductivePowerState(d.lower(),25) for d in ("A","B","C","D")})

def candidates():
    return (
        CandidatePolicySet("root_policy",("root_secure",),(),("root_secure",)),
        CandidatePolicySet("branch_policy",("branch_boost",),(),("branch_boost",)),
    )

if __name__=="__main__":
    for label,binding in (("no structure",None),("nonbinding",False),("binding",True)):
        rt=build_runtime(binding)
        a=rt.evaluate_policy_sets(state(),candidates())
        print(label)
        print(" status=",a.status)
        print(" selected=",a.selected_policy_id)
        print(" undominated=",a.undominated_policy_ids)
        if a.structural_assessment:
            s=a.structural_assessment
            print(" excluded=",s.excluded_policy_ids)
            print(" D causes=",s.immediate_causes("branch_policy","D"))
            print(" D witness=",s.provenance_path("branch_policy","D"))
        print()
