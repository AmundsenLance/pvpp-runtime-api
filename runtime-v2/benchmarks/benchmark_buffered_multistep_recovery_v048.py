
import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'benchmarks'))
from three_domain_buffered_multistep_scenario_v048 import run_runtime
from three_domain_oscillation_scenario_v047 import run_runtime as run_baseline

for label,runner,cycles_per_run in (
    ('baseline-v047',run_baseline,18),
    ('buffered-v048',run_runtime,3),
):
    for reps in (10,100,500,1000):
        vals=[]
        for _ in range(3):
            t0=time.perf_counter()
            for _i in range(reps):
                out=runner(cycles_per_run)
            vals.append((time.perf_counter()-t0)*1000)
        med=statistics.median(vals)
        cycles=reps*cycles_per_run
        print(f"{label} {cycles} decision cycles: {med:.3f} ms; {med/cycles:.4f} ms/cycle")
