
import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import *
from test_post_execution_epistemic_update_v044 import prior_actual,expectation,epsilon,transition

class W: pass
class PE:
    def evaluate(self,req):
        return PredictionErrorAssessment(
            req.actor_id,req.episode_id,req.selected_policy_id,
            (PredictionErrorComponent('policy_outcome',True,False),),True
        )

r=PVPPRegistry(); r.register_action(ActionDefinition('steady','steady',()))
rt=PVPPRuntime(r,W(),prediction_error_service=PE())
proj=PolicyProjectionRecord('policy',True,None,{'G':10.0},(),projection_horizon=12.0)
for reps in (100,1000,10000,50000):
    vals=[]
    for _ in range(3):
        t0=time.perf_counter()
        for i in range(reps):
            out=rt.apply_prediction_error(prior_actual(),epsilon(),transition(),expectation(),proj)
            assert out[2].valid
        vals.append((time.perf_counter()-t0)*1000)
    med=statistics.median(vals)
    print(f"{reps} typed PE boundary calls: {med:.3f} ms total; {med/reps:.4f} ms/call")
