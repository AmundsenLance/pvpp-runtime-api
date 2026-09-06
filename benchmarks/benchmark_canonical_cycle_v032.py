import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection
class W:
 def perceive(self,s):return s
 def domain_value(self,s,d):return float(s.powers[d])
 def project(self,s,a):
  if a.id=='steady':return ActionProjection(a.id,WorldState(s.time+1,{'G':9.0}),True)
  return ActionProjection(a.id,s,True)
 def pressure_factors(self,s,d,dr):return PressureFactors(d,self.domain_value(s,d)-5.0,dr)
 def pressure_value(self,d,f):return 1/max(f.margin,.1)
 def expected_deterioration(self,s,d,dr,p,f):return dr
 def constraint_profile(self,s,pid,actions,regime,gov):return PolicyConstraintProfile(pid,(ConstraintObservation('S',False),))
 def project_policy_record(self,s,pid,actions):return PolicyProjectionRecord(pid,True,s,{'G':20.0},(RecoveryCorridorProjection('G','continuity',True,True,True,1,20),),projection_horizon=30)
def build(n):
 r=PVPPRegistry();r.register_domain(DomainDefinition('G','G',5));r.register_action(ActionDefinition('steady','steady',('G',)))
 r.register_governing_configuration(GoverningConfiguration(0));r.register_regime_configuration(RegimeConfiguration(1,2,4,100,50,10));r.register_constraint_rule(ConstraintRuleDefinition('S','soft'));r.register_graph_instance(GraphInstanceDefinition('i','system',('G',),'active'))
 for i in range(n):
  aid=f'a{i}';tid=f't{i}';r.register_action(ActionDefinition(aid,aid,('G',)));fam='continuation' if i==0 else 'maintenance_local_adjustment';cls='continuation' if i==0 else f'c{i}';r.register_graph_transformation(GraphTransformationDefinition(tid,'i','i',fam,('G',),'reachable',aid,(cls,)));r.register_sigma_order(SigmaOrderDefinition('graph:'+tid,i))
 rt=PVPPRuntime(r,W());req=CanonicalDecisionCycleRequest(PreliminaryPreservationObject('p','preserve'),DomainFrame((DomainFrameTarget('G','continuity'),)),('continuation',),(),(),False,None,GraphConstructionConfig(n+1),PiConstructionConfig(n+1));return rt,req
def run(n):
 rt,req=build(n);ts=[]
 for _ in range(3):
  t=time.perf_counter();a=rt.evaluate_canonical_decision_cycle(WorldState(0,{'G':10.0}),req);ts.append((time.perf_counter()-t)*1000);assert a.selection.selected_policy_id=='graph:t0'
 return statistics.median(ts)
if __name__=='__main__':
 for n in (100,1000,5000,10000):print(n,f'{run(n):.3f} ms')
