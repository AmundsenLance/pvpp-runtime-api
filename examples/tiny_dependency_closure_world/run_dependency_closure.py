import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from examples.tiny_dependency_closure_world.closure_world import DependencyClosureWorld

def build_runtime(with_relations=True):
    r=PVPPRegistry()
    for d in ("A","B","C"):
        r.register_domain(DomainDefinition(d,f"Domain {d}",0,3))
        r.register_power(ProductivePowerDefinition(d.lower(),d,f"Power {d}"))
    r.register_action(ActionDefinition("steady","No intervention",("A","B","C")))
    r.register_action(ActionDefinition("favor_upstream","Preserve upstream prerequisite",("A","B","C")))
    r.register_action(ActionDefinition("favor_downstream","Favor downstream domains",("A","B","C")))
    if with_relations:
        r.register_domain_relation(DomainRelationDefinition("A_supports_B","dependency_floor","A","B",4.5))
        r.register_domain_relation(DomainRelationDefinition("B_supports_C","dependency_floor","B","C",4.5))
    return PVPPRuntime(r,DependencyClosureWorld())

def state():
    return WorldState(0,{d.lower():ProductivePowerState(d.lower(),25) for d in ("A","B","C")})

def candidates():
    return (
        CandidatePolicySet("upstream_policy",("favor_upstream",)),
        CandidatePolicySet("downstream_policy",("favor_downstream",)),
    )

if __name__ == "__main__":
    for rel in (False,True):
        a=build_runtime(rel).evaluate_policy_sets(state(),candidates())
        print("relations=",rel)
        print("status=",a.status)
        print("selected=",a.selected_policy_id)
        print("conflicts=",a.conflicting_domains)
        print("structural=",a.structural_assessment)
        for e in a.evaluations:
            print(e.policy_id,dict(e.projected_horizons))
        print()
