import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection
class W:
 def perceive(self,s): return s
 def domain_value(self,s,d): return s.power_value('p')
 def project(self,s,a): return ActionProjection(a.id,s,True)
 def project_policy(self,s,ids): return ActionProjection('policy',s,True)
def run(n,reps=9):
 reg=PVPPRegistry(); reg.register_domain(DomainDefinition('D','d',0))
 reg.register_action(ActionDefinition('steady','steady',()))
 reg.register_action(ActionDefinition('a','a',('D',)))
 rt=PVPPRuntime(reg,W()); st=WorldState(0,{'p':ProductivePowerState('p',1)})
 cs=tuple(CandidatePolicySet(f'P{i}',('a',)) for i in range(n))
 ts=[]
 for _ in range(reps):
  t=time.perf_counter(); x=rt.evaluate_constraints(st,cs); ts.append((time.perf_counter()-t)*1000)
  assert len(x.feasible_policy_ids)==n
 return statistics.median(ts)
if __name__=='__main__':
 for n in (100,1000,5000,10000,50000): print(n,f'{run(n):.3f} ms')
