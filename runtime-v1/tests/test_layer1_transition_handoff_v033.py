import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def __init__(self): self.execute_calls=0
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)
    def execute(self,state,action_id):
        self.execute_calls += 1
        raise AssertionError('epsilon-to-Layer1 handoff must never execute host mutation')

def rt_and_license():
    reg=PVPPRegistry(); reg.register_action(ActionDefinition('steady','steady',()))
    w=W(); rt=PVPPRuntime(reg,w)
    lic=ExecutionLicenseEnvelope('P',('steady',),('G',),('preserve_G',),True,True,True,True)
    return rt,w,lic

def terminal_result(*, completed=False, staged=False, failed=False, emergency=False,
                    continuation_sufficient=True, completion_sufficient=True,
                    material_policy_class_change_required=False,
                    bundle=None, info=None):
    rt,w,lic=rt_and_license()
    ep=rt.instantiate_execution('ep',lic,entry_sufficient=True,max_steps=3).episode
    result=rt.advance_execution(ep,ExecutionObservation(
        'e1',completed=completed,staged=staged,failed=failed,emergency=emergency,
        continuation_sufficient=continuation_sufficient,
        completion_sufficient=completion_sufficient,
        material_policy_class_change_required=material_policy_class_change_required,
        realized_pv_bundle=bundle or {},information=info or {}
    ))
    return rt,w,result

def test_completed_execution_builds_layer1_handoff_without_mutation():
    rt,w,r=terminal_result(completed=True,bundle={'service':2},info={'observed':'ok'})
    h=rt.build_layer1_transition_handoff(r)
    assert h.episode_id=='ep' and h.selected_policy_id=='P'
    assert h.execution_status=='completed'
    assert h.execution_path==('e1',)
    assert h.realized_pv_bundles==({'service':2},)
    assert h.execution_information==({'observed':'ok'},)
    assert h.return_upstream is False
    assert w.execute_calls==0
    assert not hasattr(h,'next_state')

def test_partial_realization_preserves_realized_bundle_and_requests_return():
    rt,w,r=terminal_result(continuation_sufficient=False,bundle={'work':0.4})
    h=rt.build_layer1_transition_handoff(r)
    assert h.execution_status=='partial_realization'
    assert h.realized_pv_bundles==({'work':0.4},)
    assert h.return_upstream is True
    assert w.execute_calls==0

def test_failure_without_bundle_still_produces_auditable_terminal_handoff():
    rt,w,r=terminal_result(failed=True,info={'fault':'tool'})
    h=rt.build_layer1_transition_handoff(r)
    assert h.execution_status=='failed'
    assert h.execution_path==('e1',)
    assert h.realized_pv_bundles==()
    assert h.execution_information==({'fault':'tool'},)
    assert h.return_upstream is True

def test_emergency_return_is_preserved_for_upstream_control():
    rt,w,r=terminal_result(emergency=True)
    h=rt.build_layer1_transition_handoff(r)
    assert h.execution_status=='emergency_return'
    assert h.return_upstream is True

def test_active_execution_cannot_be_handed_to_layer1_as_terminal_transition():
    rt,w,lic=rt_and_license()
    active=rt.instantiate_execution('ep',lic,entry_sufficient=True,max_steps=3)
    try:
        rt.build_layer1_transition_handoff(active); assert False
    except ValueError as e:
        assert 'terminal epsilon result' in str(e)

def test_entry_abort_can_be_represented_without_fabricating_state_change():
    rt,w,lic=rt_and_license()
    aborted=rt.instantiate_execution('ep',lic,entry_sufficient=False,max_steps=3)
    h=rt.build_layer1_transition_handoff(aborted)
    assert h.execution_status=='aborted_return'
    assert h.execution_path==()
    assert h.realized_pv_bundles==()
    assert h.return_upstream is True
    assert w.execute_calls==0

def test_handoff_is_immutable():
    rt,w,r=terminal_result(completed=True)
    h=rt.build_layer1_transition_handoff(r)
    try:
        h.execution_status='failed'; assert False
    except Exception:
        pass

def test_material_policy_change_returns_upstream_without_hidden_reselection():
    rt,w,r=terminal_result(material_policy_class_change_required=True,bundle={'partial':1})
    h=rt.build_layer1_transition_handoff(r)
    assert h.execution_status=='partial_realization'
    assert h.selected_policy_id=='P'
    assert h.return_upstream is True
