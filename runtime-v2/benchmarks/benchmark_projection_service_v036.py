import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass

def runtime(n):
    r=PVPPRegistry()
    for i in range(n): r.register_domain(DomainDefinition(f'D{i}','d',0.0))
    r.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(r,W())

def bench(n,reps=5):
    rt=runtime(n); st=WorldState(0,{},{'state_id':'s0'})
    hs={f'D{i}':100.0 for i in range(n)}
    req=ProjectionRequest(st,'p',(),'ordinary_adequacy',100.0,None,'s0',{'snapshot':'s0'})
    rec=PolicyProjectionRecord('p',True,None,hs,(),projection_horizon=100.0,
        state_id='s0',state_time=0.0,candidate_mode='ordinary_adequacy',
        projected_domain_trajectories={},reachable_viable={},information_quality_trace={},
        model_version='m1',projection_input_trace={'snapshot':'s0'})
    times=[]
    for _ in range(reps):
        t=time.perf_counter(); rt.validate_projection_record(req,rec); times.append((time.perf_counter()-t)*1000)
    return statistics.median(times)

if __name__=='__main__':
    for n in (100,1000,5000,10000,50000): print(f'{n}: {bench(n):.3f} ms')
