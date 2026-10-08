
import sys, time, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass

def make(n):
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',0))
    r.register_action(ActionDefinition('steady','steady',('G',)))
    for i in range(n):
        aid=f'a{i}'
        r.register_action(ActionDefinition(aid,aid,('G',)))
        r.register_recovery_plan(RecoveryPlanDefinition(f'p{i}','G',f'f{i}',aid,(),1.0))
    rt=PVPPRuntime(r,W())
    lic=ExecutionLicenseEnvelope('pol',('a0',),('G',),('f',),True,True,True,True)
    ep=ExecutionEpisode('ep',lic,1,1,True,None,False)
    return rt,EpsilonStepResult(ep,'completed',True,False)

for n in (100,1000,5000,10000,50000):
    rt,res=make(n)
    vals=[]
    for _ in range(9):
        rt.active_corridors.pop(f'p{n-1}',None)
        t0=time.perf_counter()
        rt.record_layer1_execution_commit(
            res,Layer1ExecutionCommit('ep',1.0,True,(RecoveryActionConfirmation(f'a{n-1}'),))
        )
        vals.append((time.perf_counter()-t0)*1000)
    print(f'{n}: {statistics.median(vals):.3f} ms')
