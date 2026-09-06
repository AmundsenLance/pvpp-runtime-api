import sys,time,gc,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection
class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def runtime():
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G1','G1',0)); r.register_domain(DomainDefinition('G2','G2',0)); r.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(r,W())

def run(n,reps=7):
    ev=tuple(PolicySetEvaluation(f'p{i}',(),True,False,{'G1':float(i+1),'G2':float(i+1)}) for i in range(n))
    rt=runtime(); vals=[]
    for _ in range(reps):
        gc.collect(); t=time.perf_counter(); out=rt.evaluate_sigma_fallback(ev,('G1','G2')); vals.append((time.perf_counter()-t)*1000)
        assert out.selected_policy_id==f'p{n-1}'
    return statistics.median(vals)
for n in (100,1000,5000,10000,50000): print(f'{n}: {run(n):.3f} ms')
