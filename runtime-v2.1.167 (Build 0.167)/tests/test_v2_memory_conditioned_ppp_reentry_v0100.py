import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_v2_ppp_reentry_v099 import setup_case as setup_v99

class Retrieval:
    def __init__(self): self.requests=[]
    def retrieve(self, request):
        self.requests.append(request)
        return MemoryRetrievalPackage(request.actor_id,'r100',request.memory_state.memory_state_id,request.current_time,
            {'cue':request.query},RetrievalQualityMetadata(confidence='licensed'),query_trace=request.query)

def setup_case():
    rt,w,ts,st,a,req,o,p,b,ba,_,hi,g,ri,gi,pi,calls=setup_v99()
    retrieval=Retrieval(); rt.memory_retrieval_service=retrieval
    memory=MemoryStateReference(a.actor_id,'m100',a.time-1,{'secret':'raw-memory'})
    k=ExpectationStateReference(a.actor_id,'k100',a.time-0.5,{'opaque':'expectation'})
    seen=[]
    def mapper(actual,retrieved,expectation):
        assert not isinstance(retrieved,MemoryStateReference)
        seen.append((actual.state_id,retrieved.retrieval_id,expectation.expectation_state_id if expectation else None))
        fresh=WorldState(st.time,dict(st.powers),{**dict(st.metadata),'memory_conditioned':retrieved.content['cue']})
        return PerceivedDecisionState(actual.actor_id,actual.state_id,actual.time,fresh,ppp={'fresh':'memory'},retrieval=retrieved,expectation_state=expectation)
    w.perceived_decision_state_from_perception_inputs=mapper
    inputs=MemoryConditionedPPPReentryInputs(a,memory,query='threat',context={'mode':'test'},governing_concerns=('G',),expectation_state=k,request_trace={'trace':'100'})
    return rt,w,ts,st,a,req,o,p,b,ba,inputs,hi,g,ri,gi,pi,retrieval,seen

def test_v0100_memory_conditioned_ppp_reentry_runs_through_standard_sigma():
    rt,w,ts,st,a,req,o,p,b,ba,mi,hi,g,ri,gi,pi,r,seen=setup_case()
    x=execute_memory_conditioned_ppp_reentry(rt,p,b,ba,req,mi,hi,g,ri,gi,pi)
    assert x.valid and x.status=='reentry_pass_completed'
    assert x.recomputed_stage_ids[:3]==('PPP','Phi','H')
    assert x.decision.selection.selected_policy_id==o.selection.selected_policy_id
    assert len(ts.handoffs)==0

def test_v0100_raw_memory_visible_only_to_retrieval_service():
    rt,w,ts,st,a,req,o,p,b,ba,mi,hi,g,ri,gi,pi,r,seen=setup_case()
    x=execute_memory_conditioned_ppp_reentry(rt,p,b,ba,req,mi,hi,g,ri,gi,pi)
    assert x.valid and len(r.requests)==1 and r.requests[0].memory_state is mi.memory_state
    assert seen==[(a.state_id,'r100','k100')]

def test_v0100_query_context_governing_concerns_and_trace_reach_retrieval_request():
    rt,w,ts,st,a,req,o,p,b,ba,mi,hi,g,ri,gi,pi,r,seen=setup_case()
    x=execute_memory_conditioned_ppp_reentry(rt,p,b,ba,req,mi,hi,g,ri,gi,pi)
    q=r.requests[0]
    assert x.valid and q.query=='threat' and q.context=={'mode':'test'} and q.governing_concerns==('G',) and q.request_trace=={'trace':'100'}

def test_v0100_actual_state_identity_mismatch_fails_before_retrieval():
    rt,w,ts,st,a,req,o,p,b,ba,mi,hi,g,ri,gi,pi,r,seen=setup_case()
    bad=ActualPersistentStateEnvelope(a.actor_id,'wrong',a.time,a.pp,a.spv,a.avs,a.context)
    badmi=MemoryConditionedPPPReentryInputs(bad,mi.memory_state,query='threat')
    x=execute_memory_conditioned_ppp_reentry(rt,p,b,ba,req,badmi,hi,g,ri,gi,pi)
    assert not x.valid and not r.requests and not seen

def test_v0100_invalid_or_future_memory_fails_closed_before_perception():
    rt,w,ts,st,a,req,o,p,b,ba,mi,hi,g,ri,gi,pi,r,seen=setup_case()
    fm=MemoryStateReference(a.actor_id,'future',a.time+1,{'secret':'x'})
    x=execute_memory_conditioned_ppp_reentry(rt,p,b,ba,req,MemoryConditionedPPPReentryInputs(a,fm),hi,g,ri,gi,pi)
    assert not x.valid and not r.requests and not seen

def test_v0100_wrong_boundary_or_invalid_bundle_fails_before_retrieval():
    rt,w,ts,st,a,req,o,p,b,ba,mi,hi,g,ri,gi,pi,r,seen=setup_case()
    badp=GovernanceReentryPlan(True,'Phi',(),p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids)
    assert not execute_memory_conditioned_ppp_reentry(rt,badp,b,ba,req,mi,hi,g,ri,gi,pi).valid
    badba=GovernanceReusableArtifactBundleAssessment(False,b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,(),('bad',),())
    assert not execute_memory_conditioned_ppp_reentry(rt,p,b,badba,req,mi,hi,g,ri,gi,pi).valid
    assert not r.requests and not seen

def test_v0100_invalid_retrieval_package_fails_closed():
    rt,w,ts,st,a,req,o,p,b,ba,mi,hi,g,ri,gi,pi,r,seen=setup_case()
    def bad(request):
        r.requests.append(request)
        return MemoryRetrievalPackage(request.actor_id,'bad','wrong-memory',request.current_time,{},RetrievalQualityMetadata())
    r.retrieve=bad
    x=execute_memory_conditioned_ppp_reentry(rt,p,b,ba,req,mi,hi,g,ri,gi,pi)
    assert not x.valid and len(r.requests)==1 and not seen

def test_v0100_no_epsilon_or_layer1_transition():
    rt,w,ts,st,a,req,o,p,b,ba,mi,hi,g,ri,gi,pi,r,seen=setup_case()
    x=execute_memory_conditioned_ppp_reentry(rt,p,b,ba,req,mi,hi,g,ri,gi,pi)
    assert x.valid and 'epsilon' not in x.recomputed_stage_ids and x.reused_stage_ids==() and len(ts.handoffs)==0
