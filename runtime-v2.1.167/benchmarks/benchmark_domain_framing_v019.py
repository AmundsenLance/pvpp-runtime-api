import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return s.powers[d].value
    def project(self,s,a):
        return ActionProjection(a.id,WorldState(s.time+1,{k:ProductivePowerState(v.power_id,v.value-0.1) for k,v in s.powers.items()}),True)
def run(n,reps=7):
    reg=PVPPRegistry()
    powers={}
    for i in range(n):
        d=f'D{i}'; reg.register_domain(DomainDefinition(d,d,0.0,governing_horizon=20.0))
        powers[d]=ProductivePowerState(d,1.0)
    reg.register_action(ActionDefinition('steady','steady',tuple()))
    rt=PVPPRuntime(reg,W()); st=WorldState(0,powers)
    frame=DomainFrame(tuple(DomainFrameTarget(f'D{i}',f'function_{i}') for i in range(n)))
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); a=rt.validate_domain_framing(st,frame); ts.append((time.perf_counter()-t)*1000)
        assert a.valid
    return statistics.median(ts)
if __name__=='__main__':
    for n in (100,1000,5000,10000):
        print(n, f'{run(n):.3f} ms')
