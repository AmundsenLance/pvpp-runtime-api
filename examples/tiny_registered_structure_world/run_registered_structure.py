import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime import *
from examples.tiny_crossing_policy_world.crossing_world import CrossingPolicyWorld

def build_runtime():
    r=PVPPRegistry()
    r.register_domain(DomainDefinition("F","Food continuity",0,3))
    r.register_domain(DomainDefinition("M","Material continuity",0,3))
    r.register_domain(DomainDefinition("K","Knowledge continuity",0,None))
    r.register_power(ProductivePowerDefinition("food","F","Stored food"))
    r.register_power(ProductivePowerDefinition("material","M","Material reserve"))
    r.register_power(ProductivePowerDefinition("knowledge","K","Persistence-bearing knowledge"))
    r.register_action(ActionDefinition("steady","No intervention",("F","M","K")))
    r.register_action(ActionDefinition("favor_food","Residual policy favoring F",("F","M")))
    r.register_action(ActionDefinition("favor_material","Residual policy favoring M",("F","M")))
    return PVPPRuntime(r,CrossingPolicyWorld())

def state():
    return WorldState(0,{
        "food":ProductivePowerState("food",25),
        "material":ProductivePowerState("material",25),
        "knowledge":ProductivePowerState("knowledge",1),
    })

def candidates():
    return (
        CandidatePolicySet("food_policy",("favor_food",),(),("favor_food",)),
        CandidatePolicySet("material_policy",("favor_material",),(),("favor_material",)),
    )

def run(with_relation):
    rt=build_runtime()
    if with_relation:
        rt.registry.register_domain_relation(DomainRelationDefinition(
            "F_supports_M","dependency_floor","F","M",4.25,
            "Material continuity remains structurally admissible only while food continuity preserves at least H_F=4.25."
        ))
    a=rt.evaluate_policy_sets(state(),candidates())
    print("relation=",with_relation)
    print("status=",a.status)
    print("selected=",a.selected_policy_id)
    print("undominated=",a.undominated_policy_ids)
    print("structural=",a.structural_assessment)
    print()

if __name__=="__main__":
    run(False)
    run(True)
