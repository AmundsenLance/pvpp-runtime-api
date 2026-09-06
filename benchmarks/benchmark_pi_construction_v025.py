import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection
class W:
 def perceive(self,s):return s
 def domain_value(self,s,d):return 1
 def project(self,s,a):return ActionProjection(a.id,s,True)
def run(n):
 r=PVPPRegistry();r.register_domain(DomainDefinition('G','g',0));r.register_action(ActionDefinition('steady','steady',('G',)));r.register_action(ActionDefinition('c','c',('G',)));r.register_policy_seed(PolicySeedDefinition('cont',('c',),'continuation',('G',)))
 for i in range(n-1):
  aid=f'a{i}';r.register_action(ActionDefinition(aid,aid,('G',)));r.register_policy_seed(PolicySeedDefinition(f'p{i}',(aid,),'local_adjustment',('G',),(f'k{i}',)))
 rt=PVPPRuntime(r,W());ts=[]
 for _ in range(7):
  t=time.perf_counter();a=rt.construct_pi('Mission',('G',),(),config=PiConstructionConfig(max_candidates=n+1));ts.append((time.perf_counter()-t)*1000)
 return statistics.median(ts)
if __name__=='__main__':
 for n in (100,1000,5000,10000,50000): print(n,f'{run(n):.3f} ms')
