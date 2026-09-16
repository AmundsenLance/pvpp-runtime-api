import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from test_concurrent_recovery_execution_binding_v055 import build,state,request

for reps in (100,1000,5000,10000):
    vals=[]
    for _ in range(3):
        rt,w,ts=build(); rq=request()
        t0=time.perf_counter()
        for i in range(reps):
            out=rt.evaluate_canonical_decision_cycle(state(),rq)
            assert out.status=='sigma_standard_policy_selected'
            assert out.joint_recovery_execution_binding.mandatory_action_ids==('crop_maintain','teach_complete')
        vals.append((time.perf_counter()-t0)*1000)
    med=statistics.median(vals)
    print(f"{reps} M7 bound strict cycles: {med:.3f} ms total; {med/reps:.4f} ms/cycle")
