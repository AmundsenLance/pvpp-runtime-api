import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def runtime_and_license():
    reg=PVPPRegistry(); reg.register_domain(DomainDefinition('D','d',0))
    reg.register_action(ActionDefinition('steady','steady',()))
    rt=PVPPRuntime(reg,W())
    lic=ExecutionLicenseEnvelope('p',('a',),('D',),('f',),True,True,True,True)
    return rt,lic

def active_steps(n):
    rt,lic=runtime_and_license()
    ep=rt.instantiate_execution('e',lic,entry_sufficient=True,max_steps=n+1).episode
    t=time.perf_counter()
    for i in range(n):
        ep=rt.advance_execution(ep,ExecutionObservation(str(i))).episode
    return (time.perf_counter()-t)*1000

def terminal_materialization(n):
    rt,lic=runtime_and_license()
    ep=rt.instantiate_execution('e',lic,entry_sufficient=True,max_steps=n+1).episode
    for i in range(n):
        ep=rt.advance_execution(ep,ExecutionObservation(str(i))).episode
    t=time.perf_counter()
    r=rt.advance_execution(ep,ExecutionObservation('done',completed=True,realized_pv_bundle={'x':1}))
    elapsed=(time.perf_counter()-t)*1000
    assert len(r.execution_path)==n+1
    return elapsed

if __name__=='__main__':
    for n in (100,1000,10000,50000):
        a=statistics.median(active_steps(n) for _ in range(5))
        m=statistics.median(terminal_materialization(n) for _ in range(5))
        print(n,f'active={a:.3f} ms',f'per_step={a/n*1000:.3f} us',f'terminal_materialize={m:.3f} ms')
