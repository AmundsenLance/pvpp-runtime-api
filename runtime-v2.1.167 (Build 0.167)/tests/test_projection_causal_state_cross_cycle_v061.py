import sys
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import *
from test_projection_causal_input_licensing_v060 import item
from test_projection_state_and_consistency_v059 import EchoService
from test_projection_service_v036 import build as build_projection, req as projection_req
from test_integrated_canonical_cycle_v041 import actual as integrated_actual


def perceived(t, inputs):
    s=WorldState(t,{'G':ProductivePowerState('G',10.0)},{'state_id':f's{t}'})
    return PerceivedDecisionState('a',f's{t}',t,s,ppp={'G':'perceived'},projection_causal_inputs=tuple(inputs))


def ci(i,v,t,kind='estimate'):
    return ProjectionCausalStateInput(i,kind,v,'host/domain projection contract',t,('source',))


def test_timestamped_value_change_is_legitimate_information_update():
    a=perceived(0,(ci('commitment:x','active',0),))
    b=perceived(1,(ci('commitment:x','released',1),))
    x=compare_projection_causal_state_across_cycles(a,b)
    assert x.status=='consistent_progression_with_updates'
    assert x.updated_input_ids==('commitment:x',)
    assert not x.violations


def test_input_may_appear_or_disappear_between_host_invoked_cycles():
    a=perceived(0,(ci('estimate:rain','possible',0),))
    b=perceived(1,(ci('institution:permit','open',1),))
    x=compare_projection_causal_state_across_cycles(a,b)
    assert x.appeared_input_ids==('institution:permit',)
    assert x.disappeared_input_ids==('estimate:rain',)
    assert x.status=='consistent_progression_with_updates'


def test_represented_timestamp_regression_is_mechanically_visible():
    a=perceived(1,(ci('estimate:x','new',1),))
    b=perceived(2,(ci('estimate:x','older-copy',0),))
    x=compare_projection_causal_state_across_cycles(a,b)
    assert x.representation_time_regression_ids==('estimate:x',)
    assert 'representation_time_regression' in x.status


def test_same_identity_same_time_different_value_is_visible_without_semantic_arbitration():
    a=perceived(0,(ci('estimate:x',{'state':'open'},0),))
    b=perceived(1,(ci('estimate:x',{'state':'closed'},0),))
    x=compare_projection_causal_state_across_cycles(a,b)
    assert x.same_time_value_change_ids==('estimate:x',)
    assert 'same_timestamp_value_change' in x.status


def test_staleness_is_only_host_declared_not_inferred_from_age():
    old=ci('commitment:old','active',0)
    a=perceived(0,(old,))
    b=perceived(100,(old,))
    plain=compare_projection_causal_state_across_cycles(a,b)
    assert plain.status=='consistent_progression'
    d=ProjectionCausalStateConsistencyDeclaration(stale_input_ids=('commitment:old',))
    flagged=compare_projection_causal_state_across_cycles(a,b,declaration=d)
    assert flagged.host_declared_stale_present_ids==('commitment:old',)
    assert 'host_declared_stale_inputs_present' in flagged.status


def test_contradiction_is_only_host_declared_not_inferred_from_opaque_values():
    inputs=(ci('weather:dry',True,1),ci('weather:flooded',True,1))
    a=perceived(0,())
    b=perceived(1,inputs)
    plain=compare_projection_causal_state_across_cycles(a,b)
    assert plain.contradiction_groups_present==()
    d=ProjectionCausalStateConsistencyDeclaration(contradiction_groups=(('weather:dry','weather:flooded'),))
    flagged=compare_projection_causal_state_across_cycles(a,b,declaration=d)
    assert flagged.contradiction_groups_present==(('weather:dry','weather:flooded'),)
    assert 'host_declared_contradiction_present' in flagged.status


def test_cross_cycle_diagnostic_does_not_mutate_or_feed_runtime_state():
    a=perceived(0,(ci('x',1,0),))
    b=perceived(1,(ci('x',2,1),))
    before=(repr(a),repr(b))
    x=compare_projection_causal_state_across_cycles(a,b)
    assert (repr(a),repr(b))==before
    assert 'no result from this assessment is fed into Graph' in x.notes[-1]


def test_integrated_projection_uses_current_cycle_causal_state_not_cached_prior_cycle():
    svc=EchoService(); rt,w=build_projection(svc)
    def mapper(actual):
        state=WorldState(actual.time,{'G':10.0},{'state_id':actual.state_id})
        status='active' if actual.time < 1 else 'released'
        inp=ProjectionCausalStateInput('commitment:crop','active_commitment',{'status':status},'host/domain',actual.time,('ledger',))
        return PerceivedDecisionState(actual.actor_id,actual.state_id,actual.time,state,ppp={},projection_causal_inputs=(inp,))
    w.perceived_decision_state_from_actual=mapper
    rq=replace(projection_req(),projection_required_causal_input_ids=('commitment:crop',))
    a0=integrated_actual()
    rt.evaluate_integrated_canonical_cycle(a0,rq)
    first=svc.calls[-1].perceived_decision_state.projection_causal_inputs[0]
    a1=replace(a0,state_id='s1',time=1.0)
    rt.evaluate_integrated_canonical_cycle(a1,rq)
    second=svc.calls[-1].perceived_decision_state.projection_causal_inputs[0]
    assert first.value=={'status':'active'}
    assert second.value=={'status':'released'}
    assert second.represented_time==1.0
