import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def make(n):
    r=PVPPRegistry()
    r.register_domain(DomainDefinition("G","g",0))
    r.register_action(ActionDefinition("steady","steady",("G",)))
    r.register_action(ActionDefinition("continue","continue",("G",)))
    r.register_graph_instance(GraphInstanceDefinition("root","asset",("G",),"active"))
    r.register_graph_transformation(GraphTransformationDefinition(
        "cont","root","root","continuation",("G",),"reachable","continue",("continuation",)
    ))
    for i in range(n-1):
        iid=f"i{i}"; aid=f"a{i}"; tid=f"t{i}"
        r.register_graph_instance(GraphInstanceDefinition(iid,"option",("G",),"available"))
        r.register_action(ActionDefinition(aid,aid,("G",)))
        r.register_graph_transformation(GraphTransformationDefinition(
            tid,"root",iid,"maintenance_local_adjustment",("G",),"reachable",aid,(f"k{i}",)
        ))
    rt=PVPPRuntime(r,W())
    po=PreliminaryPreservationObject("p","governing function","mechanism independent")
    return rt,po

def run(n,reps=7):
    rt,po=make(n)
    ts=[]
    for _ in range(reps):
        t=time.perf_counter()
        g=rt.construct_graph(po,"Mission",("G",),required_family_ids=("continuation",),
                             config=GraphConstructionConfig(max_seeds=n+1))
        ts.append((time.perf_counter()-t)*1000)
        assert g.status=="PASS" and len(g.policy_seeds)==n
    return statistics.median(ts)

if __name__=="__main__":
    for n in (100,1000,5000,10000,50000):
        print(n,f"{run(n):.3f} ms")
