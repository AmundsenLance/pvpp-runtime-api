import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def make_chain(n):
    r=PVPPRegistry()
    for i in range(n): r.register_domain(DomainDefinition(f'D{i}',f'D{i}',0))
    r.register_action(ActionDefinition('steady','steady',tuple(r.domains)))
    r.register_governing_configuration(GoverningConfiguration(0.0))
    # D0 is seed; every next domain is recovery-necessary for prior domain.
    for i in range(n-1):
        r.register_recovery_necessity(RecoveryNecessityDefinition(f'R{i}',f'D{i+1}',f'D{i}'))
    rt=PVPPRuntime(r,W())
    hs={f'D{i}':float(i+1) for i in range(n)}
    return rt,hs

def run(n,reps=7):
    rt,hs=make_chain(n);vals=[]
    for _ in range(reps):
        t=time.perf_counter(); g=rt.identify_governing_domains(hs); vals.append((time.perf_counter()-t)*1000)
        assert len(g.governing_domain_ids)==n
    return statistics.median(vals)

if __name__=='__main__':
    for n in (100,1000,5000,10000,50000): print(n,f'{run(n):.3f} ms')
