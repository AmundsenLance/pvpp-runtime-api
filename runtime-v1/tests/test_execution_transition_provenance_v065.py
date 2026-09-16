import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import *
from test_integrated_canonical_cycle_v041 import build, req, actual


def completed(rt, state=None, *, episode='ep', prior=None):
    return rt.evaluate_integrated_canonical_cycle(
        state or actual(), req(), execute=True, episode_id=episode,
        max_execution_steps=2,
        execution_observations=(ExecutionObservation('ev',completed=True,realized_pv_bundle={'pv':1}),),
        prior_transition_provenance=prior,
    )


def test_validated_transition_emits_explicit_execution_transition_provenance():
    rt,_,_=build()
    out=completed(rt)
    p=out.transition_provenance
    assert p is not None
    assert p.actor_id=='actor' and p.episode_id=='ep'
    assert p.selected_policy_id==out.handoff.selected_policy_id
    assert p.licensed_action_ids==out.handoff.licensed_action_ids
    assert p.execution_status=='completed'
    assert p.prior_state_id=='s0' and p.next_state_id=='s0-next'
    assert p.prior_state_time==0.0 and p.next_state_time==1.0
    assert p.transition_applied is True


def test_provenance_validates_exact_next_actual_state_identity():
    rt,_,_=build()
    out=completed(rt)
    a=rt.validate_execution_transition_provenance(out.transition_provenance,out.final_actual_state)
    assert a.valid and a.violations==()


def test_stale_provenance_rejected_for_different_state_id():
    rt,_,_=build()
    out=completed(rt)
    wrong=ActualPersistentStateEnvelope('actor','other',1.0,{}, {}, {}, {})
    a=rt.validate_execution_transition_provenance(out.transition_provenance,wrong)
    assert not a.valid
    assert any('state_id' in x for x in a.violations)


def test_provenance_rejects_actor_or_time_mismatch():
    rt,_,_=build()
    out=completed(rt)
    wrong=ActualPersistentStateEnvelope('other','s0-next',2.0,{}, {}, {}, {})
    a=rt.validate_execution_transition_provenance(out.transition_provenance,wrong)
    assert not a.valid
    assert any('actor_id' in x for x in a.violations)
    assert any('time' in x for x in a.violations)


def test_provenance_requires_mandatory_actions_inside_licensed_authority():
    rt,_,_=build()
    p=ExecutionTransitionProvenance(
        'actor','ep','p',('a',),('missing',),'completed',('a',),'s0',0.0,'s1',1.0,True
    )
    current=ActualPersistentStateEnvelope('actor','s1',1.0,{}, {}, {}, {})
    a=rt.validate_execution_transition_provenance(p,current)
    assert not a.valid
    assert any('mandatory recovery actions' in x for x in a.violations)


def test_next_integrated_cycle_can_explicitly_crosscheck_prior_transition_provenance():
    rt,w,_=build()
    first=completed(rt)
    second=rt.evaluate_integrated_canonical_cycle(
        first.final_actual_state,req(),prior_transition_provenance=first.transition_provenance
    )
    assert second.status=='integrated_cycle_selected_not_executed'
    assert any('cross-checked' in x for x in second.notes)
    assert w.map_calls==2


def test_next_integrated_cycle_fails_before_perception_on_stale_provenance():
    rt,w,_=build()
    first=completed(rt)
    calls_before=w.map_calls
    wrong=ActualPersistentStateEnvelope('actor','wrong',1.0,{}, {}, {}, {})
    try:
        rt.evaluate_integrated_canonical_cycle(wrong,req(),prior_transition_provenance=first.transition_provenance)
        assert False
    except ValueError as e:
        assert 'prior execution-transition provenance' in str(e)
    assert w.map_calls==calls_before


def test_finite_host_sequence_threads_provenance_without_persistence_or_autonomy():
    rt,_,t=build()
    d1=CanonicalCycleDirective(req(),execute=True,episode_id='e1',execution_observations=(ExecutionObservation('o1',completed=True),))
    d2=CanonicalCycleDirective(req(),execute=True,episode_id='e2',execution_observations=(ExecutionObservation('o2',completed=True),))
    out=rt.evaluate_canonical_cycle_sequence(actual(),(d1,d2))
    assert out.status=='sequence_completed'
    assert out.final_actual_state.state_id=='s0-next-next'
    assert t.calls==2
