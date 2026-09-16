import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from pvpp_runtime import *

class TwoDomainWorld:
    def perceive(self,state): return state
    def domain_value(self,state,domain_id): return state.power_value(domain_id)
    def project(self,state,action):
        vals={k:v.value for k,v in state.powers.items()}
        if action.id=='favor_A': vals.update(A=vals['A']+1.0,B=vals['B'])
        elif action.id=='favor_B': vals.update(A=vals['A'],B=vals['B']+1.0)
        elif action.id=='dominate': vals.update(A=vals['A']+2.0,B=vals['B']+2.0)
        elif action.id=='steady': vals.update(A=vals['A']-1.0,B=vals['B']-1.0)
        powers={k:ProductivePowerState(k,v) for k,v in vals.items()}
        return ActionProjection(action.id,WorldState(state.time+1,powers),True)
    def execute(self,state,action_id):
        return ExecutionResult(action_id,self.project(state,ActionDefinition(action_id,'',( 'A','B'))).next_state)

def runtime(order=('favor_A','favor_B')):
    r=PVPPRegistry()
    for d in ('A','B'):
        r.register_domain(DomainDefinition(d,d,0,5))
        r.register_power(ProductivePowerDefinition(d,d,d))
    r.register_action(ActionDefinition('steady','',('A','B')))
    for aid in order:
        r.register_action(ActionDefinition(aid,'',('A','B')))
    return PVPPRuntime(r,TwoDomainWorld())

def state():
    return WorldState(0,{'A':ProductivePowerState('A',5),'B':ProductivePowerState('B',5)})

def test_crossing_adequate_actions_remain_unselected_without_lexicographic_domain_priority():
    a=runtime().decide(state())
    assert a.selected_action is None
    assert a.selected_policy is None

def test_action_registration_order_cannot_change_unresolved_result():
    a=runtime(('favor_A','favor_B')).decide(state())
    b=runtime(('favor_B','favor_A')).decide(state())
    assert a.selected_action is b.selected_action is None

def test_unique_componentwise_dominator_can_still_be_selected():
    rt=runtime()
    rt.registry.register_action(ActionDefinition('dominate','',('A','B')))
    a=rt.decide(state())
    assert a.selected_action == 'dominate'
