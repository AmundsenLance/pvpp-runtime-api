import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return s.powers[d].value
    def project(self,s,a):
        p={k:ProductivePowerState(k,v.value-1.0) for k,v in s.powers.items()}
        return ActionProjection(a.id,WorldState(s.time+1,p),True)
    def pressure_factors(self,s,d,drift):
        v=s.powers[d].value
        return PressureFactors(d,v,drift,0.1,0.2,0.05,{})
    def pressure_value(self,d,f):
        return 1.0/(1.0+max(f.margin,0.0)) + max(0.0,-f.local_trajectory) + f.discontinuity + f.persistence + f.propagation
    def expected_deterioration(self,s,d,drift,pressure_value,pressure_factors):
        return drift-0.05*pressure_value
    def execute(self,s,a): raise NotImplementedError

def make(n):
    r=PVPPRegistry()
    for i in range(n):
        d=f"d{i}";r.register_domain(DomainDefinition(d,d,0))
    r.register_action(ActionDefinition("steady","steady",tuple(r.domains)))
    r.register_governing_configuration(GoverningConfiguration(epsilon_h=0.0))
    r.register_horizon_configuration(HorizonConfiguration(1e-9))
    s=WorldState(0,{d:ProductivePowerState(d,100.0+(i%100)) for i,d in enumerate(r.domains)})
    return PVPPRuntime(r,W()),s

def run(n,reps=7):
    rt,s=make(n);vals=[]
    for _ in range(reps):
        t=time.perf_counter();rt._assess_domains(s);vals.append((time.perf_counter()-t)*1000)
    return statistics.median(vals)

if __name__=="__main__":
    for n in (100,1000,5000,10000,50000):
        print(n,f"{run(n):.3f} ms")
