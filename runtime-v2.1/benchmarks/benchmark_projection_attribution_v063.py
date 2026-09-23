import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import *
from test_projection_model_authority_v062 import AuthorityEchoService, authority, request_with_authority
from test_projection_service_v036 import build as build_projection

p=PerceivedDecisionState('a','s0',0.0,WorldState(0.0,{'G':10.0},{'state_id':'s0'}),ppp={'G':'p'})
svc=AuthorityEchoService(); rt,_=build_projection(svc)
out=rt.evaluate_canonical_decision_cycle(p.represented_state,request_with_authority(authority()),perceived_decision_state=p)
snap=capture_projection_attribution_snapshot(p,out)
for n in (1000,10000,50000):
    t=time.perf_counter()
    for _ in range(n): compare_projection_attribution_across_cycles(snap,snap)
    dt=time.perf_counter()-t
    print(f'{n}: {dt*1000:.3f} ms total; {dt*1000/n:.6f} ms/call')
