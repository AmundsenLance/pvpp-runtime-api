import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import *
from test_integrated_canonical_cycle_v041 import build, actual, req

for mode in ('legacy','typed'):
    for reps in (100,1000,10000,50000):
        vals=[]
        for _ in range(3):
            rt,w,t=build()
            if mode=='typed':
                def pds(a):
                    represented=WorldState(a.time,{'G':10.0},{'state_id':a.state_id})
                    return PerceivedDecisionState(
                        a.actor_id,a.state_id,a.time,represented,
                        ppp={'G':10.0},spv_hat={'stock':1},pvs={'G':'viable'},x_hat={'context':'represented'},
                        confidence={'G':'bounded'},uncertainty={'G':'partial'}
                    )
                w.perceived_decision_state_from_actual=pds
            t0=time.perf_counter()
            for i in range(reps):
                snap=rt.prepare_canonical_cycle_snapshot(actual())
                assert snap.perceived_decision_state is not None
            vals.append((time.perf_counter()-t0)*1000)
        med=statistics.median(vals)
        print(f'{mode} {reps} P_i snapshot preparations: {med:.3f} ms total; {med/reps:.5f} ms/call')
