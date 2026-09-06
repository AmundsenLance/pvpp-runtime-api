import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import *
from test_integrated_canonical_cycle_v041 import build as build_integrated, actual as actual_integrated, req as req_integrated
from test_memory_conditioned_sequence_v045 import build as build_memory, actual as actual_memory, memory, expectation, req as req_memory


def explicit_pds(actual, represented, **kwargs):
    return PerceivedDecisionState(
        actual.actor_id,actual.state_id,actual.time,represented,
        ppp=kwargs.pop('ppp',{'capability':'perceived'}),
        spv_hat=kwargs.pop('spv_hat',{'cash':'perceived'}),
        pvs=kwargs.pop('pvs',{'viable':True}),
        x_hat=kwargs.pop('x_hat',{'market':'open'}),
        confidence=kwargs.pop('confidence',{'capability':'bounded'}),
        uncertainty=kwargs.pop('uncertainty',{'market':'partial'}),
        **kwargs
    )


def test_typed_perceived_decision_state_exposes_components_without_collapsing_into_ppp():
    rt,w,t=build_integrated()
    def mapper(a):
        represented=WorldState(a.time,{'G':10.0},{'state_id':a.state_id})
        return explicit_pds(a,represented)
    w.perceived_decision_state_from_actual=mapper
    snap=rt.prepare_canonical_cycle_snapshot(actual_integrated())
    p=snap.perceived_decision_state
    assert p.ppp=={'capability':'perceived'}
    assert p.spv_hat=={'cash':'perceived'}
    assert p.pvs=={'viable':True}
    assert p.x_hat=={'market':'open'}
    assert p.confidence=={'capability':'bounded'}
    assert p.uncertainty=={'market':'partial'}
    assert p.represented_state is snap.represented_state


def test_integrated_cycle_prefers_typed_pds_hook_over_legacy_worldstate_hook():
    rt,w,t=build_integrated()
    typed_calls=[]
    def typed(a):
        typed_calls.append(a.state_id)
        return explicit_pds(a,WorldState(a.time,{'G':10.0},{'state_id':a.state_id}))
    w.perceived_decision_state_from_actual=typed
    # If the legacy hook were called this test would fail.
    w.represented_state_from_actual=lambda a: (_ for _ in ()).throw(AssertionError('legacy hook called'))
    out=rt.evaluate_integrated_canonical_cycle(actual_integrated(),req_integrated())
    assert out.status=='integrated_cycle_selected_not_executed'
    assert typed_calls==['s0']


def test_legacy_adapter_is_wrapped_without_inventing_spvhat_pvs_or_xhat():
    rt,w,t=build_integrated()
    snap=rt.prepare_canonical_cycle_snapshot(actual_integrated())
    p=snap.perceived_decision_state
    assert p.metadata['compatibility_mode']=='legacy_world_state_as_ppp_interface'
    assert p.spv_hat is None and p.pvs is None and p.x_hat is None
    assert p.ppp is snap.represented_state


def test_typed_pds_requires_explicit_ppp_and_projection_compatible_payload():
    rt,w,t=build_integrated()
    a=actual_integrated()
    bad=PerceivedDecisionState(a.actor_id,a.state_id,a.time,'not-worldstate',ppp=None)
    v=rt.validate_perceived_decision_state(bad,a)
    assert not v.valid
    assert 'explicit PPP' in ' '.join(v.violations)
    assert 'projection-compatible WorldState' in ' '.join(v.violations)


def test_typed_pds_identity_and_time_are_attributed_to_actual_snapshot():
    rt,w,t=build_integrated()
    a=actual_integrated()
    represented=WorldState(a.time,{'G':10.0},{'state_id':a.state_id})
    bad=PerceivedDecisionState('other','wrong',a.time+1,represented,ppp={})
    v=rt.validate_perceived_decision_state(bad,a)
    assert not v.valid
    joined=' '.join(v.violations)
    assert 'actor_id mismatch' in joined and 'state_id mismatch' in joined and 'time mismatch' in joined


def test_nonmemory_pds_cannot_smuggle_retrieval_or_expectation_into_stack():
    rt,w,t=build_integrated()
    a=actual_integrated()
    represented=WorldState(a.time,{'G':10.0},{'state_id':a.state_id})
    ret=MemoryRetrievalPackage(a.actor_id,'r','m',a.time,{},RetrievalQualityMetadata())
    k=ExpectationStateReference(a.actor_id,'k',a.time,{})
    bad=explicit_pds(a,represented,retrieval=ret,expectation_state=k)
    v=rt.validate_perceived_decision_state(bad,a)
    assert not v.valid
    assert any('inject retrieval' in x for x in v.violations)
    assert any('inject expectation' in x for x in v.violations)


def test_memory_conditioned_typed_pds_preserves_licensed_retrieval_and_k_as_distinct_interfaces():
    rt,w,retrieval_svc,transition,upd=build_memory()
    seen=[]
    def typed(a,retrieval,k):
        seen.append((retrieval.retrieval_id,k.expectation_state_id if k else None))
        represented=WorldState(a.time,{'G':10.0},{'state_id':a.state_id,'retrieval_id':retrieval.retrieval_id})
        return explicit_pds(a,represented,retrieval=retrieval,expectation_state=k,
                            ppp={'G':'perceived-capability'},spv_hat={'stored':'perceived'})
    w.perceived_decision_state_from_perception_inputs=typed
    # Make legacy route fatal so typed route is proven.
    w.represented_state_from_perception_inputs=lambda *args: (_ for _ in ()).throw(AssertionError('legacy memory mapper called'))
    snap,decision=rt.evaluate_memory_conditioned_decision_cycle(
        actual_memory(),memory(),req_memory(),query='q',expectation_state=expectation()
    )
    assert decision.stopped_at=='Sigma'
    assert snap.perceived_decision_state.retrieval is snap.retrieval
    assert snap.perceived_decision_state.expectation_state.expectation_state_id=='k0'
    assert seen==[(snap.retrieval.retrieval_id,'k0')]


def test_memory_conditioned_typed_pds_rejects_wrong_retrieval_or_k_attribution():
    rt,w,retrieval_svc,transition,upd=build_memory()
    def bad(a,retrieval,k):
        represented=WorldState(a.time,{'G':10.0},{'state_id':a.state_id})
        wrong_ret=MemoryRetrievalPackage(a.actor_id,'wrong',retrieval.memory_state_id,a.time,{},retrieval.quality)
        wrong_k=ExpectationStateReference(a.actor_id,'wrong-k',a.time,{})
        return explicit_pds(a,represented,retrieval=wrong_ret,expectation_state=wrong_k)
    w.perceived_decision_state_from_perception_inputs=bad
    try:
        rt.prepare_memory_conditioned_cycle_snapshot(
            actual_memory(),memory(),query='q',expectation_state=expectation()
        )
        assert False
    except ValueError as e:
        s=str(e)
        assert 'retrieval does not match' in s and 'expectation-state mismatch' in s


def test_runtime_does_not_derive_perceived_components_from_actual_pp_spv_avs_x():
    rt,w,t=build_integrated()
    a=actual_integrated()
    # Legacy wrapper proves the runtime leaves all new perceived fields unset rather
    # than copying actual SPV/AVS/context into them.
    snap=rt.prepare_canonical_cycle_snapshot(a)
    p=snap.perceived_decision_state
    assert p.spv_hat is None and p.pvs is None and p.x_hat is None
    assert p.spv_hat != a.spv and p.pvs != a.avs and p.x_hat != a.context
