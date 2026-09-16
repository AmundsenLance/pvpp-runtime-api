import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import *
from test_canonical_decision_cycle_v032 import build, req, state

def attach(rt):
    for aid in ('crop_maintain','crop_harvest','teach_complete'):
        rt.registry.register_action(ActionDefinition(aid,aid,('G',),{'capacity_demands':{'skilled_labor_session':1}}))
    rt.active_corridors={
        'crop_cycle':ActiveRecoveryCorridor('crop_cycle','G','crop_cycle_continuity',('crop_maintain','crop_harvest'),1.0),
        'k_transfer':ActiveRecoveryCorridor('k_transfer','G','cultivation_technique_continuity',('teach_complete',),1.0),
    }
    return rt
scarce=CapacityCalendar({0:{'skilled_labor_session':1},1:{'skilled_labor_session':1}})
sufficient=CapacityCalendar({0:{'skilled_labor_session':2},1:{'skilled_labor_session':1}})
for label,cal,expect in (('joint-infeasible',scarce,'joint_recovery_feasibility_failed'),('joint-feasible',sufficient,'sigma_standard_policy_selected')):
    for reps in (100,1000,5000,10000):
        vals=[]
        for _ in range(3):
            rt,w=build(); attach(rt); rq=req(joint_recovery_capacity_calendar=cal)
            t0=time.perf_counter()
            for i in range(reps):
                out=rt.evaluate_canonical_decision_cycle(state(),rq); assert out.status==expect
            vals.append((time.perf_counter()-t0)*1000)
        med=statistics.median(vals)
        print(f"{label} {reps} cycles: {med:.3f} ms total; {med/reps:.4f} ms/cycle")
