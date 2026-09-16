import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_dual import build_runtime
from pvpp_runtime import WorldState, ProductivePowerState, CapacityCalendar

state=WorldState(0,{"knowledge":ProductivePowerState("knowledge",1)})
for cap in (2,3):
    rt=build_runtime()
    cal=CapacityCalendar({p:{"teacher":cap,"learner":cap} for p in range(3)})
    a=rt.assess(state,capacity_calendar=cal)
    print(f"capacity_per_period={cap}")
    print(" recovery_status=",a.recovery_adequacy.status)
    print(" selected_policy=",None if a.selected_policy is None else a.selected_policy.action_ids)
    print(" selected_action=",a.selected_action)
    print(" period0_residual=",dict(a.recovery_adequacy.residual_capacity.get(0,{})))
