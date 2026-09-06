import statistics,time
from pvpp_runtime import *

class ManyActionWorld:
    def perceive(self,state): return state
    def domain_value(self,state,domain_id): return state.power_value(domain_id)
    def project(self,state,action):
        a=state.power_value('A'); b=state.power_value('B')
        if action.id=='steady': a-=1; b-=1
        elif action.id=='dominator': a+=2; b+=2
        else:
            i=int(action.metadata['i'])
            if i%2: a+=1
            else: b+=1
        return ActionProjection(action.id,WorldState(state.time+1,{
            'A':ProductivePowerState('A',a),'B':ProductivePowerState('B',b)}),True)
    def execute(self,state,action_id): raise NotImplementedError

def build(n,dominator=False):
    r=PVPPRegistry()
    for d in ('A','B'):
        r.register_domain(DomainDefinition(d,d,0,5)); r.register_power(ProductivePowerDefinition(d,d,d))
    r.register_action(ActionDefinition('steady','',('A','B')))
    for i in range(n): r.register_action(ActionDefinition(f'a{i}','',('A','B'),{'i':i}))
    if dominator: r.register_action(ActionDefinition('dominator','',('A','B')))
    return PVPPRuntime(r,ManyActionWorld())

def run(n,dominator,repeats):
    rt=build(n,dominator)
    s=WorldState(0,{'A':ProductivePowerState('A',5),'B':ProductivePowerState('B',5)})
    xs=[]; result=None
    for _ in range(repeats):
        t=time.perf_counter(); result=rt.decide(s); xs.append((time.perf_counter()-t)*1000)
    return statistics.median(xs),result

if __name__=='__main__':
    print('PV-PP v0.18 ordinary single-action assessment/selection benchmark')
    print('Includes projection + domain reassessment for all registered actions; selection itself is linear in actions x governing domains.')
    for n,repeats in ((100,40),(1000,12),(5000,4)):
        for dom in (False,True):
            ms,a=run(n,dom,repeats)
            print(f'{n:5d} discretionary actions dominator={str(dom):5s}: median {ms:.3f} ms; selected={a.selected_action}')
