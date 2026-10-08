import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *


def build_runtime():
    r=PVPPRegistry(); r.register_domain(DomainDefinition("K","Knowledge",0,3))
    r.register_power(ProductivePowerDefinition("knowledge","K","Persistence-bearing knowledge"))
    r.register_action(ActionDefinition("steady","No intervention",("K",)))
    for prefix in ("A","B"):
        for i in range(1,4):
            r.register_action(ActionDefinition(f"teach_{prefix}{i}",f"Teach {prefix} step {i}",("K",),{"capacity_demands":{"teacher":1,"learner":1}}))
    r.register_action(ActionDefinition(
        "document_knowledge", "Document noncritical knowledge", ("K",),
        {"capacity_demands":{"teacher":1}, "policy_role":"discretionary"}
    ))
    r.register_action(ActionDefinition(
        "catalog_archive", "Catalog noncritical archive", ("K",),
        {"capacity_demands":{"teacher":1}, "policy_role":"discretionary"}
    ))
    # Plans are registered so the same action semantics are usable by the ordinary runtime ledger.
    r.register_recovery_plan(RecoveryPlanDefinition("corridor_A","K","function_A","teach_A1",("teach_A2","teach_A3"),5))
    r.register_recovery_plan(RecoveryPlanDefinition("corridor_B","K","function_B","teach_B1",("teach_B2","teach_B3"),5))
    # This example focuses on the feasibility interface; no world projection is required.
    class NullWorld:
        def perceive(self,s): return s
        def domain_value(self,s,d): return s.power_value("knowledge")
        def project(self,s,a):
            from pvpp_runtime import ActionProjection
            return ActionProjection(a.id,s,True)
        def execute(self,s,a): return ExecutionResult(a,s,True)
    rt=PVPPRuntime(r,NullWorld())
    rt.active_corridors={
        "corridor_A":ActiveRecoveryCorridor("corridor_A","K","function_A",("teach_A1","teach_A2","teach_A3"),5),
        "corridor_B":ActiveRecoveryCorridor("corridor_B","K","function_B",("teach_B1","teach_B2","teach_B3"),5),
    }
    return rt

def calendar(periods):
    return CapacityCalendar({p:{"teacher":1,"learner":1} for p in range(periods)})

if __name__=="__main__":
    rt=build_runtime()
    for periods in (5,6):
        report=rt.assess_recovery_feasibility(calendar(periods),now=0)
        print(f"capacity_periods={periods} jointly_feasible={report.jointly_feasible}")
        if report.schedule:
            print(" schedule=",[(s.period_offset,s.corridor_id,s.action_id) for s in report.schedule])
        if report.infeasible_corridor_sets:
            print(" minimal_infeasible_sets=",report.infeasible_corridor_sets)

# v0.5 ordinary-assessment integration demonstration
if __name__=="__main__":
    from pvpp_runtime import WorldState, ProductivePowerState
    s=WorldState(0,{"knowledge":ProductivePowerState("knowledge",1)})
    print("ordinary assessment integration:")
    for periods in (5,6):
        rt=build_runtime()
        a=rt.assess(s,capacity_calendar=calendar(periods))
        ra=a.recovery_adequacy
        print(f" assess capacity_periods={periods} status={ra.status} selected_action={a.selected_action}")
        print("  infeasible_sets=",ra.infeasible_corridor_sets)
        print("  bottlenecks=",dict(ra.bottleneck_resources))
        print("  deadline_slack=",dict(ra.deadline_slack))
