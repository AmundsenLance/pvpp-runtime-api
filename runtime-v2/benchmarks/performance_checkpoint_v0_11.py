"""PV-PP Runtime v0.11 performance checkpoint.

Intentionally bounded benchmark. It does not execute the known >5 second
infeasible cases automatically; those are recorded in PERFORMANCE_RESULTS_v0_11.txt.
"""
from __future__ import annotations
import time, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'examples'/'tiny_food_world'))
sys.path.insert(0,str(ROOT/'examples'/'tiny_crossing_policy_world'))
from pvpp_runtime import *
from examples.tiny_food_world.run_food import build_runtime as build_food, initial_state
from examples.tiny_crossing_policy_world.run_crossing_choice import build_runtime as build_cross, state as crossing_state, calendar as crossing_calendar


def timed_assess(name,rt,state,calendar=None,n=1000):
    for _ in range(25): rt.assess(state,capacity_calendar=calendar)
    t=time.perf_counter()
    for _ in range(n): rt.assess(state,capacity_calendar=calendar)
    dt=time.perf_counter()-t
    print(f"{name}: {dt/n*1e6:.1f} us/call; {n/dt:.0f} calls/s")


def synthetic(n, periods, cap=1, steps=3):
    r=PVPPRegistry(); r.register_domain(DomainDefinition('K','Knowledge',0,3)); r.register_power(ProductivePowerDefinition('k','K','k')); r.register_action(ActionDefinition('steady','steady',('K',)))
    for j in range(n):
        ids=[]
        for i in range(steps):
            aid=f'c{j}_s{i}'; ids.append(aid)
            r.register_action(ActionDefinition(aid,aid,('K',),{'capacity_demands':{'slot':1}}))
        r.register_recovery_plan(RecoveryPlanDefinition(f'c{j}','K',f'f{j}',ids[0],tuple(ids[1:]),periods-1))
    class W:
        def perceive(self,s): return s
        def domain_value(self,s,d): return s.power_value('k')
        def project(self,s,a): return ActionProjection(a.id,s,True)
    rt=PVPPRuntime(r,W())
    rt.active_corridors={f'c{j}':ActiveRecoveryCorridor(f'c{j}','K',f'f{j}',tuple(f'c{j}_s{i}' for i in range(steps)),periods-1) for j in range(n)}
    cal=CapacityCalendar({p:{'slot':cap} for p in range(periods)})
    return rt,cal


def timed_feas(n,periods):
    rt,cal=synthetic(n,periods)
    t=time.perf_counter(); rep=rt.assess_recovery_feasibility(cal); dt=time.perf_counter()-t
    print(f"corridors={n} periods={periods} feasible={rep.jointly_feasible}: {dt*1000:.3f} ms")

if __name__=='__main__':
    timed_assess('tiny_food assess',build_food(),initial_state(),n=2000)
    timed_assess('crossing-policy assess',build_cross(),crossing_state(),crossing_calendar(),n=500)
    print('feasible scheduler boundary:')
    for n in range(2,8): timed_feas(n,n*3)
    print('bounded infeasible cases:')
    timed_feas(2,5)
    timed_feas(3,8)
