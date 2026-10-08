import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import ProjectionCausalStateInput, PerceivedDecisionState, WorldState
from test_projection_service_v036 import build

rt,w=build(None)
state=WorldState(0.0,{'G':10.0},{'state_id':'s0'})
inputs=tuple(ProjectionCausalStateInput(f'i:{n}','represented_causal',n,'benchmark-license',0.0) for n in range(16))
pds=PerceivedDecisionState('a','s0',0.0,state,ppp={},projection_causal_inputs=inputs)
required=tuple(i.input_id for i in inputs)
for N in (1000,10000,50000):
    t=time.perf_counter()
    for _ in range(N):
        x=rt.validate_projection_causal_inputs(pds,required)
        if not x.valid: raise RuntimeError(x)
    ms=(time.perf_counter()-t)*1000
    print(f'{N}: {ms:.3f} ms total; {ms/N:.6f} ms/validation')
