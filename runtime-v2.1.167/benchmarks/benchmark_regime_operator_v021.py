import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import DomainAssessment, ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def run(n,reps=11):
    reg=PVPPRegistry()
    for i in range(n): reg.register_domain(DomainDefinition(f'D{i}','d',0))
    reg.register_action(ActionDefinition('steady','steady',()))
    reg.register_regime_configuration(RegimeConfiguration(
        1,3,7,.9,.6,.3,3,2,2.5,6.0,.5,2.0))
    rt=PVPPRuntime(reg,W())
    hs={f'D{i}':10.0+(i%3) for i in range(n)}
    ds={d:DomainAssessment(d,1.0,.1,hs[d],True,0) for d in hs}
    gov=set(hs)
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); a=rt.classify_regime(ds,hs,gov); ts.append((time.perf_counter()-t)*1000)
        assert a.regime=='Mission'
    return statistics.median(ts)

if __name__=='__main__':
    for n in (100,1000,5000,10000,50000):
        print(n,f'{run(n):.3f} ms')
