import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_dual import build_runtime
from pvpp_runtime import WorldState, ProductivePowerState, CapacityCalendar
s=WorldState(0,{"knowledge":ProductivePowerState("knowledge",1)})
for cap in (2,3,4):
    a=build_runtime().assess(s,capacity_calendar=CapacityCalendar({p:{"teacher":cap,"learner":cap} for p in range(3)}))
    ds=a.discretionary_selection; sp=a.selected_policy
    print(f"capacity={cap}")
    print(" required=",sp.required_action_ids)
    print(" discretionary_status=",ds.status)
    print(" maximal_sets=",ds.maximal_feasible_sets)
    print(" supplemental=",sp.supplemental_action_ids)
    print(" residual=",dict(sp.residual_capacity))
