import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection
class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)
    def constraint_profile(self,state,pid,action_ids,regime,gov):
        i=int(pid[1:])
        if i%10==0: return PolicyConstraintProfile(pid,(ConstraintObservation('H',True),))
        if i%3==0: return PolicyConstraintProfile(pid,(ConstraintObservation('C',True,True,True,True),))
        return PolicyConstraintProfile(pid,(ConstraintObservation('S',True),))
def run(n):
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',0)); r.register_action(ActionDefinition('steady','steady',())); r.register_action(ActionDefinition('a','a',('G',)))
    r.register_constraint_rule(ConstraintRuleDefinition('H','hard'));r.register_constraint_rule(ConstraintRuleDefinition('C','conditional','prudence'));r.register_constraint_rule(ConstraintRuleDefinition('S','soft'))
    rt=PVPPRuntime(r,W()); cs=tuple(CandidatePolicySet(f'p{i}',('a',)) for i in range(n)); st=WorldState(0,{})
    vals=[]
    for _ in range(5):
        t=time.perf_counter(); a=rt.evaluate_constraint_system(st,cs,regime='Survival',governing_domain_ids=('G',)); vals.append((time.perf_counter()-t)*1000)
    return statistics.median(vals),len(a.feasible_policy_ids)
if __name__=='__main__':
    for n in (100,1000,5000,10000,50000):
        ms,k=run(n); print(n,f'{ms:.3f} ms',k)
