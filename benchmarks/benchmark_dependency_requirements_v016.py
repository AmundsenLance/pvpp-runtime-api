import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import PolicySetEvaluation

class DummyWorld:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def make_runtime(n,mode):
    r=PVPPRegistry()
    sources=tuple(f"S{i}" for i in range(n))
    for d in sources+("T",):
        r.register_domain(DomainDefinition(d,d,0,None))
    r.register_action(ActionDefinition("steady","steady",sources+("T",)))
    r.register_dependency_requirement(DependencyRequirementDefinition("group",mode,sources,"T",1.0))
    return PVPPRuntime(r,DummyWorld()),sources

def bench(n,mode,fail_count):
    rt,sources=make_runtime(n,mode)
    failed=set(sources[:fail_count])
    ev=PolicySetEvaluation("p",(),True,True,{s:(0.0 if s in failed else 2.0) for s in sources}|{"T":2.0})
    ts=[]
    for _ in range(30):
        t=time.perf_counter(); rt._apply_registered_policy_structure([ev]); ts.append((time.perf_counter()-t)*1e6)
    return statistics.median(ts)

if __name__=='__main__':
    print('sources mode failed median_us')
    for n in (10,100,1000,5000):
        print(n,'all_of',1,round(bench(n,'all_of',1),2))
        print(n,'any_of',max(1,n-1),round(bench(n,'any_of',max(1,n-1)),2))
        print(n,'any_of',n,round(bench(n,'any_of',n),2))
