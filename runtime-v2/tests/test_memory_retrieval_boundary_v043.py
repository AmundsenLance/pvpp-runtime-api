
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class Retrieval:
    def __init__(self):
        self.requests=[]
    def retrieve(self,request):
        self.requests.append(request)
        content={'recalled':request.query,'memory_token':request.memory_state.payload['token']}
        quality=RetrievalQualityMetadata(
            confidence='medium',source_basis=('episode-7',),completeness='partial',
            distortion_risk='nonzero',freshness='current-query',
            corroboration='uncorroborated',relevance_scope=request.query
        )
        return MemoryRetrievalPackage(
            request.actor_id,f"r-{request.query}",request.memory_state.memory_state_id,
            request.current_time,content,quality,query_trace=request.query,
            source_trace={'memory_state_id':request.memory_state.memory_state_id}
        )

class W:
    def __init__(self):
        self.perception_inputs=[]
    def represented_state_from_perception_inputs(self,actual,retrieval,expectation):
        # Deliberately only retrieval + K are accepted here; no MemoryStateReference.
        assert isinstance(retrieval,MemoryRetrievalPackage)
        assert not isinstance(retrieval,MemoryStateReference)
        self.perception_inputs.append((retrieval,expectation))
        g=10.0 if retrieval.content['recalled']=='calm' else 8.0
        return WorldState(actual.time,{'G':g},{'state_id':actual.state_id,'retrieval_id':retrieval.retrieval_id})
    def perceive(self,s): return s
    def domain_value(self,s,d): return float(s.powers[d])
    def project(self,s,a):
        if a.id=='steady':
            return ActionProjection(a.id,WorldState(s.time+1,{'G':s.powers['G']-1},dict(s.metadata)),True)
        return ActionProjection(a.id,s,True)
    def pressure_factors(self,s,d,drift): return PressureFactors(d,s.powers[d]-5.0,drift)
    def pressure_value(self,d,f): return 1.0/max(f.margin,0.1)
    def expected_deterioration(self,s,d,drift,p,f): return drift
    def constraint_profile(self,s,pid,a,r,g):
        return PolicyConstraintProfile(pid,(ConstraintObservation('soft',False),))
    def project_policy_record(self,s,pid,a):
        return PolicyProjectionRecord(
            pid,True,s,{'G':20.0},
            (RecoveryCorridorProjection('G','continuity',True,True,True,1.0,20.0),),
            projection_horizon=30.0
        )

def build():
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',5.0))
    for a in ('steady','continue'): r.register_action(ActionDefinition(a,a,('G',)))
    r.register_governing_configuration(GoverningConfiguration(0.0))
    r.register_regime_configuration(RegimeConfiguration(1,2,4,100,50,10))
    r.register_constraint_rule(ConstraintRuleDefinition('soft','soft'))
    r.register_graph_instance(GraphInstanceDefinition('i','system',('G',),'active'))
    r.register_graph_transformation(GraphTransformationDefinition(
        'cont','i','i','continuation',('G',),'reachable','continue',('continuation',)
    ))
    r.register_sigma_order(SigmaOrderDefinition('graph:cont',1))
    w=W(); m=Retrieval()
    return PVPPRuntime(r,w,memory_retrieval_service=m),w,m

def req():
    return CanonicalDecisionCycleRequest(
        PreliminaryPreservationObject('p','preserve continuity'),
        DomainFrame((DomainFrameTarget('G','continuity'),)),
        ('continuation',),(),('continuation',)
    )

def actual(t=5.0):
    return ActualPersistentStateEnvelope('actor','s5',t,{}, {}, {}, {})

def memory(t=3.0):
    return MemoryStateReference('actor','m3',t,{'token':'opaque-retained-history'})

def test_same_retained_memory_can_yield_different_retrieval_under_different_cues():
    rt,w,m=build()
    a=rt.prepare_memory_conditioned_cycle_snapshot(actual(),memory(),query='calm')
    b=rt.prepare_memory_conditioned_cycle_snapshot(actual(),memory(),query='threat')
    assert a.memory_state.memory_state_id==b.memory_state.memory_state_id=='m3'
    assert a.retrieval.retrieval_id != b.retrieval.retrieval_id
    assert a.retrieval.content != b.retrieval.content
    assert a.represented_state.powers['G']==10.0
    assert b.represented_state.powers['G']==8.0
    assert len(m.requests)==2

def test_raw_memory_is_not_passed_to_perception_or_decision_stack():
    rt,w,m=build()
    snap,decision=rt.evaluate_memory_conditioned_decision_cycle(
        actual(),memory(),req(),query='calm'
    )
    assert decision.stopped_at=='Sigma'
    assert len(w.perception_inputs)==1
    retrieval,k=w.perception_inputs[0]
    assert isinstance(retrieval,MemoryRetrievalPackage)
    assert k is None
    # The retained payload remains reachable only through the retrieval service request.
    assert m.requests[0].memory_state.payload['token']=='opaque-retained-history'

def test_retrieval_quality_metadata_is_preserved_without_becoming_truth_scalar():
    rt,w,m=build()
    snap=rt.prepare_memory_conditioned_cycle_snapshot(actual(),memory(),query='calm')
    q=snap.retrieval.quality
    assert q.confidence=='medium'
    assert q.completeness=='partial'
    assert q.distortion_risk=='nonzero'
    assert q.source_basis==('episode-7',)
    assert q.relevance_scope=='calm'

def test_expectation_state_is_distinct_from_memory_and_retrieval():
    rt,w,m=build()
    k=ExpectationStateReference('actor','k2',4.0,{'forecast':'opaque'})
    snap=rt.prepare_memory_conditioned_cycle_snapshot(
        actual(),memory(),query='calm',expectation_state=k
    )
    assert snap.expectation_state is k
    retrieval,seen_k=w.perception_inputs[0]
    assert seen_k is k
    assert retrieval.memory_state_id=='m3'
    assert k.expectation_state_id=='k2'

def test_future_dated_memory_fails_closed():
    rt,w,m=build()
    try:
        rt.prepare_memory_conditioned_cycle_snapshot(actual(5.0),memory(6.0),query='calm')
        assert False
    except ValueError as e:
        assert 'future' in str(e)
    assert not m.requests

def test_future_dated_expectation_state_fails_closed():
    rt,w,m=build()
    k=ExpectationStateReference('actor','kfuture',6.0,{})
    try:
        rt.prepare_memory_conditioned_cycle_snapshot(
            actual(5.0),memory(3.0),query='calm',expectation_state=k
        )
        assert False
    except ValueError as e:
        assert 'future' in str(e)
    assert not m.requests

def test_retrieval_identity_mismatch_fails_before_perception():
    rt,w,m=build()
    class Bad:
        def retrieve(self,request):
            return MemoryRetrievalPackage(
                request.actor_id,'r','wrong-memory',request.current_time,{},RetrievalQualityMetadata()
            )
    rt.memory_retrieval_service=Bad()
    try:
        rt.prepare_memory_conditioned_cycle_snapshot(actual(),memory(),query='calm')
        assert False
    except ValueError as e:
        assert 'memory_state_id' in str(e)
    assert not w.perception_inputs

def test_retrieval_must_carry_quality_metadata():
    rt,w,m=build()
    class Bad:
        def retrieve(self,request):
            # intentionally bypass constructor typing with a compatible object shape
            class X:
                actor_id=request.actor_id
                retrieval_id='r'
                memory_state_id=request.memory_state.memory_state_id
                time=request.current_time
                content={}
                quality=None
            return X()
    rt.memory_retrieval_service=Bad()
    try:
        rt.prepare_memory_conditioned_cycle_snapshot(actual(),memory(),query='calm')
        assert False
    except ValueError as e:
        assert 'MemoryRetrievalPackage' in str(e) or 'RetrievalQualityMetadata' in str(e)

def test_retrieval_time_must_align_to_current_cycle():
    rt,w,m=build()
    class Bad:
        def retrieve(self,request):
            return MemoryRetrievalPackage(
                request.actor_id,'r',request.memory_state.memory_state_id,
                request.current_time-1,{},RetrievalQualityMetadata()
            )
    rt.memory_retrieval_service=Bad()
    try:
        rt.prepare_memory_conditioned_cycle_snapshot(actual(),memory(),query='calm')
        assert False
    except ValueError as e:
        assert 'time must align' in str(e)

def test_no_memory_update_or_persistence_is_created_by_retrieval():
    rt,w,m=build()
    mem=memory()
    snap=rt.prepare_memory_conditioned_cycle_snapshot(actual(),mem,query='calm')
    assert snap.memory_state is mem
    assert mem.payload=={'token':'opaque-retained-history'}
    assert not hasattr(rt,'memory_store')
