import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *


def state(t,n=16,delta=False):
    rs=WorldState(t,{}, {'state_id':f's{t}'})
    items=[]
    for i in range(n):
        v={'value':i + (1 if delta and i==n//2 else 0)}
        rt=t if delta and i==n//2 else 0.0
        items.append(ProjectionCausalStateInput(f'i:{i}','estimate',v,'benchmark',rt,('src',)))
    return PerceivedDecisionState('a',f's{t}',t,rs,ppp={},projection_causal_inputs=tuple(items))

p=state(0); c=state(1,delta=True)
for reps in (100,1000,10000,50000):
    t0=time.perf_counter()
    for _ in range(reps):
        compare_projection_causal_state_across_cycles(p,c)
    dt=time.perf_counter()-t0
    print(f'{reps}: {dt*1000:.3f} ms total; {dt/reps*1000:.6f} ms/call')
