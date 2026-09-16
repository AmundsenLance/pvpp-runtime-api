
import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class M:
    def retrieve(self,request):
        return MemoryRetrievalPackage(
            request.actor_id,'r',request.memory_state.memory_state_id,request.current_time,
            {'x':1},RetrievalQualityMetadata(confidence='bounded'),
            query_trace=request.query
        )
class W:
    def represented_state_from_perception_inputs(self,actual,retrieval,expectation):
        return WorldState(actual.time,{'G':10.0},{'state_id':actual.state_id})
class DummyRegistry:
    actions={'steady':object()}

# Bypass normal runtime constructor requirement with a minimal real registry.
r=PVPPRegistry()
r.register_action(ActionDefinition('steady','steady',()))
rt=PVPPRuntime(r,W(),memory_retrieval_service=M())
actual=ActualPersistentStateEnvelope('a','s',10.0,{}, {}, {}, {})
mem=MemoryStateReference('a','m',9.0,{'opaque':'history'})

for n in (100,1000,5000,10000,50000):
    vals=[]
    for _ in range(5):
        t0=time.perf_counter()
        for i in range(n):
            rt.prepare_memory_conditioned_cycle_snapshot(actual,mem,query=i)
        vals.append((time.perf_counter()-t0)*1000)
    med=statistics.median(vals)
    print(f"{n}: total {med:.3f} ms; per retrieval+snapshot {med/n*1000:.3f} us")
