import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def runtime():
    reg=PVPPRegistry()
    reg.register_domain(DomainDefinition('D0','d',0))
    reg.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(reg,W())

def run_domains(n,reps=9):
    rt=runtime()
    frame=DomainFrame(tuple(DomainFrameTarget(f'D{i}',f'F{i}') for i in range(n)))
    gov={f'D{i}' for i in range(n)}
    rec=PolicyProjectionRecord('p',True,None,{},
        tuple(RecoveryCorridorProjection(f'D{i}',f'F{i}',True,True,True,1.0,10.0) for i in range(n)))
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); a=rt.evaluate_restoration_adequacy(frame,gov,(rec,)); ts.append((time.perf_counter()-t)*1000)
        assert a.adequate_policy_ids==('p',)
    return statistics.median(ts)

def run_policies(n,reps=7):
    rt=runtime()
    domains=10
    frame=DomainFrame(tuple(DomainFrameTarget(f'D{i}',f'F{i}') for i in range(domains)))
    gov={f'D{i}' for i in range(domains)}
    corr=tuple(RecoveryCorridorProjection(f'D{i}',f'F{i}',True,True,True,1.0,10.0) for i in range(domains))
    records=tuple(PolicyProjectionRecord(f'p{j}',True,None,{},corr) for j in range(n))
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); a=rt.evaluate_restoration_adequacy(frame,gov,records); ts.append((time.perf_counter()-t)*1000)
        assert len(a.adequate_policy_ids)==n
    return statistics.median(ts)

if __name__=='__main__':
    print('Domains, one policy')
    for n in (100,1000,5000,10000,50000):
        print(n,f'{run_domains(n):.3f} ms')
    print('Policies, ten domains')
    for n in (100,1000,5000,10000):
        print(n,f'{run_policies(n):.3f} ms')
