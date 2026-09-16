
import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'benchmarks'))
from three_domain_oscillation_scenario_v047 import run_runtime, viability_precheck

w=viability_precheck(12)
assert w.feasible
for reps in (10,100,500,1000):
    vals=[]
    for _ in range(3):
        t0=time.perf_counter()
        for _i in range(reps):
            out=run_runtime(18)
            assert len(out[1])==18
        vals.append((time.perf_counter()-t0)*1000)
    med=statistics.median(vals)
    cycles=reps*18
    print(f"{cycles} full stress cycles: {med:.3f} ms; {med/cycles:.4f} ms/cycle")
