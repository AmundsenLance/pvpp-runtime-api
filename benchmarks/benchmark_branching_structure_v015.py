import sys, time, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import PolicySetEvaluation

class DummyWorld:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def diamond_runtime(width:int, levels:int):
    r=PVPPRegistry()
    names=["ROOT"]
    for level in range(levels):
        names += [f"L{level}_{i}" for i in range(width)]
    names += ["SINK"]
    for d in names:
        r.register_domain(DomainDefinition(d,d,0,None))
    r.register_action(ActionDefinition("steady","steady",tuple(names)))
    prev=["ROOT"]
    rel_idx=0
    for level in range(levels):
        cur=[f"L{level}_{i}" for i in range(width)]
        for s in prev:
            for t in cur:
                r.register_domain_relation(DomainRelationDefinition(
                    f"r{rel_idx}","dependency_floor",s,t,1.0))
                rel_idx+=1
        prev=cur
    for s in prev:
        r.register_domain_relation(DomainRelationDefinition(
            f"r{rel_idx}","dependency_floor",s,"SINK",1.0))
        rel_idx+=1
    rt=PVPPRuntime(r,DummyWorld())
    ev=PolicySetEvaluation("p",("x",),True,True,{d:(0.0 if d=="ROOT" else 2.0) for d in names})
    return rt, ev, rel_idx

if __name__=="__main__":
    for width,levels in [(2,10),(4,10),(8,10),(16,10),(32,10)]:
        rt,ev,edges=diamond_runtime(width,levels)
        times=[]
        assessment=None
        for _ in range(20):
            t=time.perf_counter()
            _,assessment=rt._apply_registered_policy_structure([ev])
            times.append((time.perf_counter()-t)*1e6)
        print(width,levels,edges,round(statistics.median(times),2),
              len(assessment.immediate_causes("p","SINK")))
