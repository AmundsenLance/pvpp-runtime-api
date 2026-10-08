import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_dual import build_runtime
from pvpp_runtime import WorldState, ProductivePowerState, CapacityCalendar
s=WorldState(0,{"knowledge":ProductivePowerState("knowledge",1)})
for cap in (2,3):
    rt=build_runtime(); cal=CapacityCalendar({p:{"teacher":cap,"learner":cap} for p in range(3)})
    a=rt.assess(s,capacity_calendar=cal); p=a.selected_policy
    print(f"capacity_per_period={cap}")
    print(" required=",p.required_action_ids)
    print(" supplemental=",p.supplemental_action_ids)
    print(" selected_policy=",p.action_ids)
    print(" residual_after_policy=",dict(p.residual_capacity))
