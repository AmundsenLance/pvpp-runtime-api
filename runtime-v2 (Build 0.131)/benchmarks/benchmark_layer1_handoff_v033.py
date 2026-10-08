import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection
class W:
 def perceive(self,s):return s
 def domain_value(self,s,d):return 1
 def project(self,s,a):return ActionProjection(a.id,s,True)
def runtime():
 r=PVPPRegistry();r.register_action(ActionDefinition('steady','steady',()));return PVPPRuntime(r,W())
def run(n):
 rt=runtime();lic=ExecutionLicenseEnvelope('P',('steady',),('G',),('F',),True,True,True,True)
 ep=ExecutionEpisode('ep',lic,n,n,True,None,False)
 path=tuple(f'e{i}' for i in range(n));bundles=tuple({'pv':i} for i in range(n));infos=tuple({'i':i} for i in range(n))
 result=EpsilonStepResult(ep,'completed',True,False,bundles,infos,path)
 ts=[]
 for _ in range(7):
  t=time.perf_counter();h=rt.build_layer1_transition_handoff(result);ts.append((time.perf_counter()-t)*1000);assert len(h.execution_path)==n
 return statistics.median(ts)
if __name__=='__main__':
 for n in (1,100,1000,10000,50000):print(n,f'{run(n):.3f} ms')
