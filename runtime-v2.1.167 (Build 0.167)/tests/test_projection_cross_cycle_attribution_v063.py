import sys
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_projection_model_authority_v062 import AuthorityEchoService, authority, request_with_authority
from test_projection_service_v036 import build as build_projection, state as projection_state


def perceived(t=0.0, state_id='s0', inputs=()):
    s=WorldState(t,{'G':10.0},{'state_id':state_id})
    return PerceivedDecisionState('a',state_id,t,s,ppp={'G':'perceived'},projection_causal_inputs=tuple(inputs))


def run(perceived_state, *, a=None, request_mutator=None, service=None):
    svc=service or AuthorityEchoService(); rt,w=build_projection(svc)
    w.perceived_decision_state_from_actual=lambda actual: perceived_state
    rq=request_with_authority(a or authority())
    if request_mutator: rq=request_mutator(rq)
    # Direct canonical cycle deliberately receives the exact represented state used by P_i(t).
    out=rt.evaluate_canonical_decision_cycle(perceived_state.represented_state,rq,perceived_decision_state=perceived_state)
    return capture_projection_attribution_snapshot(perceived_state,out),out


def test_identical_authoritative_inputs_and_q_are_unchanged():
    p=perceived()
    a,_=run(p); b,_=run(p)
    x=compare_projection_attribution_across_cycles(a,b)
    assert x.status=='projection_and_observed_authoritative_inputs_unchanged'
    assert not x.determinism_anomaly


def test_changed_represented_state_is_attributed_without_causal_claim():
    p0=perceived()
    p1=replace(perceived(1.0,'s1'), represented_state=WorldState(1.0,{'G':9.0},{'state_id':'s1'}))
    a,_=run(p0); b,_=run(p1)
    x=compare_projection_attribution_across_cycles(a,b)
    assert x.represented_state_changed
    assert 'represented_state' in x.changed_input_classes
    assert not x.determinism_anomaly
    assert 'not inferred causes' in x.notes[0]


def test_changed_causal_inputs_are_separately_visible():
    c0=ProjectionCausalStateInput('commit:x','commitment','active','host',0.0,('ledger',))
    c1=replace(c0,value='released',represented_time=1.0)
    a,_=run(perceived(0,'s0',(c0,)))
    b,_=run(perceived(1,'s1',(c1,)))
    x=compare_projection_attribution_across_cycles(a,b)
    assert x.causal_inputs_changed
    assert 'projection_causal_inputs' in x.changed_input_classes


def test_changed_model_authority_and_horizon_are_distinct_classes():
    p=perceived()
    a,_=run(p,a=authority(30.0,'v3'))
    p1=perceived(1,'s1')
    b,_=run(p1,a=authority(40.0,'v4'))
    x=compare_projection_attribution_across_cycles(a,b)
    assert x.predictive_model_authority_changed
    assert x.projection_horizon_changed
    assert 'predictive_model_authority' in x.changed_input_classes
    assert 'projection_horizon' in x.changed_input_classes


def test_changed_graph_context_is_visible_even_if_q_content_does_not_change():
    p=perceived()
    a,out=run(p)
    changed_graph=replace(out.graph_assessment,represented_families=out.graph_assessment.represented_families+('diagnostic_family',))
    b=capture_projection_attribution_snapshot(p,replace(out,graph_assessment=changed_graph))
    x=compare_projection_attribution_across_cycles(a,b)
    assert x.graph_context_changed
    assert not x.projection_changed
    assert x.status=='projection_unchanged_with_observed_authoritative_input_change'


def test_candidate_policy_set_change_is_an_authoritative_input_change():
    p=perceived(); a,out=run(p)
    # Diagnostic construction: remove one already-produced record to model a different supplied candidate set.
    altered=replace(out,projection_records=out.projection_records[:1])
    b=capture_projection_attribution_snapshot(p,altered)
    x=compare_projection_attribution_across_cycles(a,b)
    assert x.candidate_policy_set_changed
    assert x.projection_changed
    assert not x.determinism_anomaly


def test_q_change_without_observed_input_change_flags_determinism_anomaly_only():
    p=perceived(); a,out=run(p)
    first=out.projection_records[0]
    mutated=replace(first,projected_domain_trajectories={'G':(10.0,8.5)})
    altered=replace(out,projection_records=(mutated,)+out.projection_records[1:])
    b=capture_projection_attribution_snapshot(p,altered)
    x=compare_projection_attribution_across_cycles(a,b)
    assert x.projection_changed
    assert x.determinism_anomaly
    assert x.status=='projection_changed_without_observed_authoritative_input_change'


def test_attribution_assessment_never_enters_decision_cycle():
    p=perceived(); a,out=run(p); b,_=run(p)
    x=compare_projection_attribution_across_cycles(a,b)
    assert out.selection is not None
    assert 'not fed into Graph' in x.notes[-1]
