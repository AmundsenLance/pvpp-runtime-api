import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
class W: pass
def build(n):
 r=PVPPRegistry();r.register_domain(DomainDefinition("D","d",0));r.register_action(ActionDefinition("steady","steady",("D",)));r.register_action(ActionDefinition("a","a",("D",)));r.register_graph_instance(GraphInstanceDefinition("x","asset",("D",),"ok"))
 for i in range(n):r.register_graph_transformation(GraphTransformationDefinition(f"t{i}","x","x","continuation",("D",),"reachable","a",structural_effect="continuation"))
 r.register_graph_transformation(GraphTransformationDefinition("u","x","x","continuation",("D",),"uncertain","a",uncertainty_note="test uncertainty",structural_effect="continuation"))
 return PVPPRuntime(r,W()),PreliminaryPreservationObject("p","function")
for n in (10,100,1000,5000):
 rt,po=build(n);vals=[]
 for _ in range(7):
  t=time.perf_counter();g=rt.construct_graph(po,"Mission",("D",),required_family_ids=("continuation",));vals.append((time.perf_counter()-t)*1000)
 print(f"{n} reachable + 1 uncertain: {statistics.median(vals):.4f} ms/build; status={g.status}")
