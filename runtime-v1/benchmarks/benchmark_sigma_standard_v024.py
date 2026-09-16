import sys,time,statistics,math
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
    for d in ('G1','G2','N1','N2'):
        reg.register_domain(DomainDefinition(d,d,0))
    reg.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(reg,W())

def dominated_case(n):
    # One monotone chain: frontier size 1; representative easy case.
    return tuple(PolicySetEvaluation(
        f'p{i}',(),True,True,{'G1':float(i),'G2':float(i),'N1':float(i),'N2':float(i)}
    ) for i in range(n))

def crossing_case(n):
    # All points mutually non-dominated on G1/G2 and on global coordinates.
    return tuple(PolicySetEvaluation(
        f'p{i}',(),True,True,{'G1':float(i),'G2':float(n-i),'N1':float(i%7),'N2':float((i*3)%11)}
    ) for i in range(n))

def run(case,n,reps=5):
    rt=runtime(); evs=case(n); ts=[]
    for _ in range(reps):
        t=time.perf_counter(); rt.evaluate_sigma_standard(evs,('G1','G2')); ts.append((time.perf_counter()-t)*1000)
    return statistics.median(ts)

if __name__=='__main__':
    print('Dominated chain')
    for n in (100,1000,5000,10000):
        print(n,f'{run(dominated_case,n):.3f} ms')
    print('Worst-style all-nondominated crossing')
    for n in (100,250,500,1000):
        print(n,f'{run(crossing_case,n,3):.3f} ms')

# Governing-equivalent A1 fiber; Stage 2 sees two crossing non-governing dimensions.
def stage2_fiber_case(n):
    return tuple(PolicySetEvaluation(
        f'f{i}',(),True,True,{'G1':10.0,'G2':10.0,'N1':float(i),'N2':float(n-i)}
    ) for i in range(n))

if __name__=='__main__':
    print('Stage-2 governing-equivalent crossing fiber')
    for n in (100,1000,5000,10000):
        print(n,f'{run(stage2_fiber_case,n,3):.3f} ms')
