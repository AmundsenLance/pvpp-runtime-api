import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from policy_world import PolicyChoiceWorld


def build_runtime(equal=False):
    r=PVPPRegistry()
    r.register_domain(DomainDefinition("F","Food continuity",0,3))
    r.register_domain(DomainDefinition("K","Knowledge continuity",0,None))
    r.register_power(ProductivePowerDefinition("food","F","Stored food"))
    r.register_power(ProductivePowerDefinition("knowledge","K","Persistence-bearing knowledge"))
    r.register_action(ActionDefinition("steady","No intervention",("F","K")))
    for prefix in ("A","B"):
        for i in range(1,4):
            r.register_action(ActionDefinition(f"teach_{prefix}{i}",f"Teach {prefix} step {i}",("K",),{"capacity_demands":{"teacher":1,"learner":1}}))
    r.register_action(ActionDefinition("gather_small","Gather food route 1",("F",),{"capacity_demands":{"teacher":1},"policy_role":"discretionary"}))
    r.register_action(ActionDefinition("gather_large","Gather food route 2",("F",),{"capacity_demands":{"teacher":1},"policy_role":"discretionary"}))
    r.register_recovery_plan(RecoveryPlanDefinition("corridor_A","K","function_A","teach_A1",("teach_A2","teach_A3"),5))
    r.register_recovery_plan(RecoveryPlanDefinition("corridor_B","K","function_B","teach_B1",("teach_B2","teach_B3"),5))
    world=PolicyChoiceWorld({"gather_small":15.0,"gather_large":15.0 if equal else 20.0})
    rt=PVPPRuntime(r,world)
    rt.active_corridors={
        "corridor_A":ActiveRecoveryCorridor("corridor_A","K","function_A",("teach_A1","teach_A2","teach_A3"),5),
        "corridor_B":ActiveRecoveryCorridor("corridor_B","K","function_B",("teach_B1","teach_B2","teach_B3"),5),
    }
    return rt


def state():
    return WorldState(0,{"food":ProductivePowerState("food",25),"knowledge":ProductivePowerState("knowledge",1)})

def calendar():
    return CapacityCalendar({p:{"teacher":3,"learner":3} for p in range(3)})

if __name__=='__main__':
    for equal in (False,True):
        a=build_runtime(equal=equal).assess(state(),capacity_calendar=calendar())
        print('equal=',equal)
        print(' policy_selection=',a.policy_selection.status if a.policy_selection else None)
        print(' undominated=',a.policy_selection.undominated_policy_ids if a.policy_selection else ())
        print(' selected_policy=',a.selected_policy.action_ids if a.selected_policy else None)
        if a.policy_selection:
            for e in a.policy_selection.evaluations:
                print(' ',e.policy_id,e.action_ids,'H_F=',e.projected_horizons.get('F'))
