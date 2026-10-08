
import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass
class S:
    def update(self,req):
        m=MemoryStateReference(req.actor_id,'m1',req.next_actual_time,{})
        k=ExpectationStateReference(req.actor_id,'k1',req.next_actual_time,{})
        return PostExecutionEpistemicUpdateResult(req.actor_id,req.episode_id,m,k,True,True)

r=PVPPRegistry(); r.register_action(ActionDefinition('steady','steady',()))
rt=PVPPRuntime(r,W(),epistemic_update_service=S())
prior=ActualPersistentStateEnvelope('a','s0',1.0,{}, {}, {}, {})
nexts=ActualPersistentStateEnvelope('a','s1',2.0,{}, {}, {}, {})
mem=MemoryStateReference('a','m0',1.0,{})
k=ExpectationStateReference('a','k0',1.0,{})
lic=ExecutionLicenseEnvelope('p',('a',),('G',),('f',),True,True,True,True,())
ep=ExecutionEpisode('ep',lic,1,1,True,None,False)
eps=EpsilonStepResult(ep,'completed',True,False,({'pv':1},),({'info':1},),('e',))
tr=Layer1TransitionResult('ep','p','s0',nexts,True,{'ok':True})

for n in (100,1000,5000,10000,50000):
    vals=[]
    for _ in range(5):
        t0=time.perf_counter()
        for _i in range(n):
            rt.apply_post_execution_epistemic_update(prior,eps,tr,mem,k)
        vals.append((time.perf_counter()-t0)*1000)
    med=statistics.median(vals)
    print(f"{n}: total {med:.3f} ms; per update {med/n*1000:.3f} us")
