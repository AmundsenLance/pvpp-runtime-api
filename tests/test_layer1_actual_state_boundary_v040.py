import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass

class T:
    def __init__(self): self.calls=0
    def transition(self,current,handoff):
        self.calls += 1
        return Layer1TransitionResult(
            handoff.episode_id,handoff.selected_policy_id,current.state_id,
            ActualPersistentStateEnvelope(
                current.actor_id,'s1',current.time+1,
                {'energy':9}, {'cash':100}, {'viable':True}, {'weather':'clear'}
            ),True,{'outer_consistency':True}
        )

def runtime(service=None):
    r=PVPPRegistry(); r.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(r,W(),layer1_transition_service=service)

def state():
    return ActualPersistentStateEnvelope('actor','s0',0.0,
        {'energy':10},{'cash':90},{'viable':True},{'weather':'clear'})

def handoff():
    return Layer1TransitionHandoff('ep','p','completed',('e1',),({'cash':10},),(),False)

def test_outer_state_validation_accepts_opaque_structured_components():
    a=runtime().validate_actual_persistent_state(state())
    assert a.valid
    assert a.violations==()


def test_outer_state_validation_rejects_absent_component_without_interpreting_contents():
    s=ActualPersistentStateEnvelope('actor','s0',0.0,{},None,object(),{'x':1})
    a=runtime().validate_actual_persistent_state(s)
    assert not a.valid
    assert 'SPV component is absent' in a.violations


def test_explicit_layer1_transition_service_is_called_only_by_explicit_bridge():
    service=T(); rt=runtime(service)
    result=rt.apply_layer1_transition(state(),handoff())
    assert service.calls==1
    assert result.next_state.state_id=='s1'
    assert result.next_state.spv=={'cash':100}


def test_no_transition_service_fails_closed():
    try:
        runtime().apply_layer1_transition(state(),handoff())
        assert False
    except ValueError as e:
        assert 'Layer1TransitionService' in str(e)


def test_transition_result_cannot_change_actor_identity():
    class Bad:
        def transition(self,current,h):
            return Layer1TransitionResult(h.episode_id,h.selected_policy_id,current.state_id,
                ActualPersistentStateEnvelope('other','s1',1,{}, {}, {}, {}),True,{'ok':True})
    try:
        runtime(Bad()).apply_layer1_transition(state(),handoff())
        assert False
    except ValueError as e:
        assert 'actor identity' in str(e)


def test_transition_result_requires_new_state_identity():
    class Bad:
        def transition(self,current,h):
            return Layer1TransitionResult(h.episode_id,h.selected_policy_id,current.state_id,
                ActualPersistentStateEnvelope(current.actor_id,current.state_id,1,{}, {}, {}, {}),True,{'ok':True})
    try:
        runtime(Bad()).apply_layer1_transition(state(),handoff())
        assert False
    except ValueError as e:
        assert 'new state_id' in str(e)


def test_transition_time_may_not_move_backward():
    class Bad:
        def transition(self,current,h):
            return Layer1TransitionResult(h.episode_id,h.selected_policy_id,current.state_id,
                ActualPersistentStateEnvelope(current.actor_id,'s1',-1,{}, {}, {}, {}),True,{'ok':True})
    try:
        runtime(Bad()).apply_layer1_transition(state(),handoff())
        assert False
    except ValueError as e:
        assert 'move backward' in str(e)


def test_failed_host_invariant_check_blocks_transition_result():
    class Bad:
        def transition(self,current,h):
            return Layer1TransitionResult(h.episode_id,h.selected_policy_id,current.state_id,
                ActualPersistentStateEnvelope(current.actor_id,'s1',1,{}, {}, {}, {}),True,{'conservation':False})
    try:
        runtime(Bad()).apply_layer1_transition(state(),handoff())
        assert False
    except ValueError as e:
        assert 'invariant checks failed' in str(e)


def test_legacy_worldstate_remains_available_for_existing_runtime_paths():
    ws=WorldState(0.0,{})
    assert ws.time==0.0

def test_epsilon_and_decision_methods_do_not_implicitly_call_layer1_service():
    service=T(); rt=runtime(service)
    lic=ExecutionLicenseEnvelope('p',('steady',),(),(),True,True,True,True)
    start=rt.instantiate_execution('ep',lic,entry_sufficient=True,max_steps=1)
    done=rt.advance_execution(start.episode,ExecutionObservation('ev',completed=True))
    assert done.terminal
    assert service.calls==0
    h=rt.build_layer1_transition_handoff(done)
    assert service.calls==0
    rt.apply_layer1_transition(state(),h)
    assert service.calls==1
