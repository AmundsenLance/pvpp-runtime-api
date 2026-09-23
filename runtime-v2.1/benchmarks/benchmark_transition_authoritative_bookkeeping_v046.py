
import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass

def make(n):
    r=PVPPRegistry()
    r.register_domain(DomainDefinition('G','g',0))
    r.register_action(ActionDefinition('steady','steady',('G',)))
    for i in range(n):
        aid=f'a{i}'
        r.register_action(ActionDefinition(aid,aid,('G',)))
        r.register_recovery_plan(RecoveryPlanDefinition(f'r{i}','G',f'f{i}',aid,(),1.0))
    rt=PVPPRuntime(r,W())
    lic=ExecutionLicenseEnvelope('p',('a0',),('G',),('f',),True,True,True,True,())
    ep=ExecutionEpisode('ep',lic,1,1,True,None,False)
    eps=EpsilonStepResult(ep,'completed',True,False)
    prior=ActualPersistentStateEnvelope('actor','s0',0.0,{}, {}, {}, {})
    nxt=ActualPersistentStateEnvelope('actor','s1',1.0,{}, {}, {}, {})
    tr=Layer1TransitionResult('ep','p','s0',nxt,True,{'ok':True})
    return rt,eps,prior,tr

for n in (100,1000,5000,10000,50000):
    vals=[]
    for _ in range(5):
        rt,eps,prior,tr=make(n)
        confirmation=RecoveryActionConfirmation(f'a{n-1}')
        t0=time.perf_counter()
        a=rt.record_recovery_bookkeeping_from_transition(prior,eps,tr,(confirmation,))
        vals.append((time.perf_counter()-t0)*1000)
        assert a.started_corridor_ids==(f'r{n-1}',)
    med=statistics.median(vals)
    print(f"{n} registered plans: {med:.4f} ms transition validation + indexed trigger bookkeeping")
