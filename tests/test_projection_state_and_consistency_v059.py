import sys
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import *
from test_projection_service_v036 import build as build_projection, req as projection_req
from test_integrated_canonical_cycle_v041 import actual as integrated_actual
from test_memory_conditioned_sequence_v045 import build as build_memory, actual as memory_actual, memory, expectation, req as memory_req


class EchoService:
    def __init__(self): self.calls=[]
    def project(self,req):
        self.calls.append(req)
        return PolicyProjectionRecord(
            req.policy_id,False,req.represented_state,{'G':req.projection_horizon},
            (RecoveryCorridorProjection('G','continuity',True,True,True,1.0,None),),
            projection_horizon=req.projection_horizon,
            right_censored_domain_ids=('G',),
            state_id=req.state_id,state_time=req.represented_state.time,
            candidate_mode=req.candidate_mode,
            projected_domain_trajectories={'G':('projected',)},
            reachable_viable={'G':('i',)},
            information_quality_trace={'basis':'echo'},
            information_quality_claims=(ProjectionInformationQualityClaim(
                'reachability','G:continuity','represented predictive inputs','opaque-confidence'
            ),),
            model_version='echo-v1',projection_input_trace=dict(req.projection_input_trace)
        )


def typed_nonmemory_world():
    svc=EchoService(); rt,w=build_projection(svc)
    def mapper(a):
        s=WorldState(a.time,{'G':10.0},{'state_id':a.state_id})
        return PerceivedDecisionState(
            a.actor_id,a.state_id,a.time,s,
            ppp={'capability':'perceived'},spv_hat={'cash':'represented'},
            pvs={'continuity':True},x_hat={'market':'estimated'},
            confidence={'market':'bounded'},uncertainty={'market':'partial'}
        )
    w.perceived_decision_state_from_actual=mapper
    return rt,w,svc


def test_integrated_projection_request_receives_exact_typed_perceived_state():
    rt,w,svc=typed_nonmemory_world()
    out=rt.evaluate_integrated_canonical_cycle(integrated_actual(),projection_req())
    assert out.status=='integrated_cycle_selected_not_executed'
    assert len(svc.calls)==2
    pds=svc.calls[0].perceived_decision_state
    assert isinstance(pds,PerceivedDecisionState)
    assert pds.confidence=={'market':'bounded'}
    assert pds.uncertainty=={'market':'partial'}
    assert pds.spv_hat=={'cash':'represented'}
    assert all(c.perceived_decision_state is pds for c in svc.calls)


def test_projection_trace_records_perceived_input_provenance_without_semantic_scoring():
    rt,w,svc=typed_nonmemory_world()
    out=rt.evaluate_integrated_canonical_cycle(integrated_actual(),projection_req())
    tr=svc.calls[0].projection_input_trace
    assert tr['perceived_state_id']=='s0'
    assert tr['ppp_interface_present'] is True
    assert tr['spv_hat_interface_present'] is True
    assert tr['confidence_interface_present'] is True
    assert tr['uncertainty_interface_present'] is True
    assert tr['retrieval_id'] is None and tr['expectation_state_id'] is None
    for forbidden in ('confidence_score','uncertainty_weight','utility','rank'):
        assert forbidden not in tr


def test_memory_conditioned_projection_request_carries_licensed_retrieval_and_k():
    rt,w,retrieval,transition,upd=build_memory()
    svc=EchoService(); rt.projection_service=svc
    def typed(a,r,k):
        s=WorldState(a.time,{'G':10.0},{'state_id':a.state_id})
        return PerceivedDecisionState(
            a.actor_id,a.state_id,a.time,s,ppp={'G':'perceived'},retrieval=r,
            expectation_state=k,confidence={'forecast':'bounded'},uncertainty={'forecast':'open'}
        )
    w.perceived_decision_state_from_perception_inputs=typed
    rq=replace(memory_req(),projection_horizon=30.0,projection_input_trace={'host':'memory-cycle'})
    snap,decision=rt.evaluate_memory_conditioned_decision_cycle(
        memory_actual(),memory(),rq,query='q',expectation_state=expectation()
    )
    assert decision.stopped_at=='Sigma'
    call=svc.calls[0]
    assert call.perceived_decision_state.retrieval is snap.retrieval
    assert call.perceived_decision_state.expectation_state is snap.expectation_state
    assert call.projection_input_trace['retrieval_id']==snap.retrieval.retrieval_id
    assert call.projection_input_trace['expectation_state_id']=='k0'
    assert call.projection_input_trace['host']=='memory-cycle'


def test_projection_consistency_audit_records_same_policy_set_for_adequacy_and_sigma():
    rt,w,svc=typed_nonmemory_world()
    out=rt.evaluate_integrated_canonical_cycle(integrated_actual(),projection_req())
    audit=out.decision.projection_consistency_audit
    assert audit.unchanged_through_adequacy and audit.unchanged_through_sigma
    assert audit.policy_ids==audit.adequacy_consumed_policy_ids==audit.sigma_consumed_policy_ids
    assert audit.policy_ids==tuple(r.policy_id for r in out.decision.projection_records)


def test_adequacy_mutation_of_nested_q_record_fails_closed():
    rt,w,svc=typed_nonmemory_world()
    original=rt.evaluate_restoration_adequacy
    def mutating(frame,g,records):
        records[0].information_quality_trace['illegal_mutation']='adequacy'
        return original(frame,g,records)
    rt.evaluate_restoration_adequacy=mutating
    try:
        rt.evaluate_integrated_canonical_cycle(integrated_actual(),projection_req())
        assert False
    except ValueError as e:
        assert 'Adequacy mutated' in str(e)


def test_sigma_mutation_of_nested_q_record_fails_closed():
    rt,w,svc=typed_nonmemory_world()
    original=rt._standard_selection_from_cycle_records
    def mutating(*args,**kwargs):
        records=args[5]
        out=original(*args,**kwargs)
        next(iter(records.values())).reachable_viable['illegal']='sigma'
        return out
    rt._standard_selection_from_cycle_records=mutating
    try:
        rt.evaluate_integrated_canonical_cycle(integrated_actual(),projection_req())
        assert False
    except ValueError as e:
        assert 'Sigma mutated' in str(e)


def test_direct_worldstate_cycle_remains_supported_without_typed_projection_state():
    svc=EchoService(); rt,w=build_projection(svc)
    s=WorldState(0.0,{'G':10.0},{'state_id':'s0'})
    out=rt.evaluate_canonical_decision_cycle(s,projection_req())
    assert out.stopped_at=='Sigma'
    assert all(c.perceived_decision_state is None for c in svc.calls)
    assert out.projection_consistency_audit.unchanged_through_sigma


def test_projection_request_rejects_misaligned_typed_perceived_state():
    svc=EchoService(); rt,w=build_projection(svc)
    s=WorldState(0.0,{'G':10.0},{'state_id':'s0'})
    wrong=PerceivedDecisionState('actor','wrong',0.0,s,ppp={})
    try:
        rt.evaluate_canonical_decision_cycle(s,projection_req(),perceived_decision_state=wrong)
        assert False
    except ValueError as e:
        assert 'identity mismatch' in str(e) or 'does not wrap' in str(e)
