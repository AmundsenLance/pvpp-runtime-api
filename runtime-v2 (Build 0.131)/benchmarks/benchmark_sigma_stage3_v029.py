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
 r=PVPPRegistry();r.register_domain(DomainDefinition('G1','G1',0));r.register_domain(DomainDefinition('G2','G2',0));r.register_action(ActionDefinition('steady','steady',()))
 ev=[]
 for i in range(n):
  pid=f'p{i}';r.register_sigma_order(SigmaOrderDefinition(pid,n-i));ev.append(PolicySetEvaluation(pid,(),True,True,{'G1':float(i),'G2':float(n-i)}))
 rt=PVPPRuntime(r,W());ts=[]
 for _ in range(3):
  t=time.perf_counter();s=rt.evaluate_sigma_standard(tuple(ev),('G1','G2'));ts.append((time.perf_counter()-t)*1000);assert s.selected_policy_id==f'p{n-1}'
 return statistics.median(ts)
if __name__=='__main__':
 for n in (100,1000,5000,10000,50000):print(n,f'{run(n):.3f} ms')
