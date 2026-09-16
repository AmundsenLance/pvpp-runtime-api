import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from test_integrated_canonical_cycle_v041 import build, req, actual
from pvpp_runtime import ExecutionObservation

rt,_,_=build()
out=rt.evaluate_integrated_canonical_cycle(actual(),req(),execute=True,episode_id='ep',execution_observations=(ExecutionObservation('e',completed=True),))
p=out.transition_provenance
state=out.final_actual_state
for n in (1000,10000,50000):
    t0=time.perf_counter()
    for _ in range(n):
        a=rt.validate_execution_transition_provenance(p,state)
        assert a.valid
    dt=time.perf_counter()-t0
    print(f'provenance_validate n={n}: {dt*1000:.3f} ms total; {dt/n*1000:.6f} ms/call')

for n in (100,1000,5000):
    t0=time.perf_counter()
    for i in range(n):
        rt.evaluate_integrated_canonical_cycle(state,req(),prior_transition_provenance=p)
    dt=time.perf_counter()-t0
    print(f'next_cycle_crosscheck n={n}: {dt*1000:.3f} ms total; {dt/n*1000:.6f} ms/cycle')
