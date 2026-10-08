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


def make_runtime(n, source_order=None):
    r=PVPPRegistry()
    sources=tuple(f"S{i}" for i in range(n)) if source_order is None else tuple(source_order)
    for d in sources+("C","D","E"):
        r.register_domain(DomainDefinition(d,d,0,None))
    r.register_action(ActionDefinition("steady","steady",sources+("C","D","E")))
    r.register_dependency_requirement(DependencyRequirementDefinition("substitutes","any_of",sources,"D",1.0))
    r.register_dependency_requirement(DependencyRequirementDefinition("mandatory","all_of",("C",),"D",1.0))
    r.register_dependency_requirement(DependencyRequirementDefinition("downstream","all_of",("D",),"E",1.0))
    return PVPPRuntime(r,DummyWorld()),sources


def bench(n,case):
    rt,sources=make_runtime(n)
    if case == "one_substitute_survives":
        horizons={s:(2.0 if i==0 else 0.0) for i,s in enumerate(sources)}
        horizons.update(C=2.0,D=2.0,E=2.0)
    elif case == "substitute_set_exhausted":
        horizons={s:0.0 for s in sources}
        horizons.update(C=2.0,D=2.0,E=2.0)
    elif case == "mandatory_failure":
        horizons={s:(2.0 if i==0 else 0.0) for i,s in enumerate(sources)}
        horizons.update(C=0.0,D=2.0,E=2.0)
    else:
        raise ValueError(case)
    ev=PolicySetEvaluation("p",(),True,True,horizons)
    ts=[]
    for _ in range(30):
        t=time.perf_counter(); rt._apply_registered_policy_structure([ev]); ts.append((time.perf_counter()-t)*1e6)
    return statistics.median(ts)

if __name__=='__main__':
    print('sources case median_us')
    for n in (10,100,1000,5000):
        for case in ('one_substitute_survives','substitute_set_exhausted','mandatory_failure'):
            print(n,case,round(bench(n,case),2))
