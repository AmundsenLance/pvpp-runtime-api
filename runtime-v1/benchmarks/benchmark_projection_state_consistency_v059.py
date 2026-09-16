import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from test_projection_state_and_consistency_v059 import typed_nonmemory_world
from test_projection_service_v036 import req
from test_integrated_canonical_cycle_v041 import actual

for n in (100,1000,5000,10000):
    vals=[]
    for _ in range(5):
        rt,w,svc=typed_nonmemory_world(); rq=req(); a=actual()
        t0=time.perf_counter()
        for i in range(n):
            out=rt.evaluate_integrated_canonical_cycle(a,rq)
            assert out.decision.projection_consistency_audit.unchanged_through_sigma
        vals.append((time.perf_counter()-t0)*1000)
    med=statistics.median(vals)
    print(f'{n} typed integrated Q-consistency cycles: {med:.3f} ms total; {med/n:.4f} ms/cycle')
