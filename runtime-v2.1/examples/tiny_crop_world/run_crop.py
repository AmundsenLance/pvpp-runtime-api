import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from crop_world import TinyCropWorld

def build_runtime():
    r=PVPPRegistry(); r.register_domain(DomainDefinition("F","Food",0,3)); r.register_domain(DomainDefinition("L","Labor",0,1))
    r.register_power(ProductivePowerDefinition("food_stock","F","Food stock")); r.register_power(ProductivePowerDefinition("labor_available","L","Labor",False))
    for aid,desc in [("steady","No intervention"),("plant","Plant crop"),("maintain_crop","Maintain crop"),("harvest_crop","Harvest crop")]: r.register_action(ActionDefinition(aid,desc,("F","L")))
    r.register_recovery_plan(RecoveryPlanDefinition("crop_recovery","F","crop_cycle","plant",("maintain_crop","harvest_crop"),3))
    return PVPPRuntime(r,TinyCropWorld())
def initial_state(): return WorldState(0,{"food_stock":ProductivePowerState("food_stock",25),"labor_available":ProductivePowerState("labor_available",10,10)},{"crop_stage":"none"})
if __name__=="__main__":
    rt=build_runtime(); s=initial_state()
    for _ in range(4):
        a=rt.decide(s); print(f"t={s.time:g} F={s.power_value('food_stock'):g} stage={s.metadata['crop_stage']} G={a.governing_domains} selected={a.selected_action} corridors={[(k,v.status,v.remaining_actions) for k,v in rt.active_corridors.items()]}")
        if a.selected_action is None: break
        er=rt.world.execute(s,a.selected_action); rt.record_execution(er); s=er.next_state
