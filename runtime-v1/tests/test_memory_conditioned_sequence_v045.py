
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class RetrievalSvc:
    def __init__(self): self.requests=[]
    def retrieve(self,request):
        self.requests.append(request)
        quality=RetrievalQualityMetadata(confidence='bounded',source_basis=('memory',))
        return MemoryRetrievalPackage(
            request.actor_id,f"r-{request.memory_state.memory_state_id}-{request.query}",
            request.memory_state.memory_state_id,request.current_time,
            {'query':request.query,'memory':request.memory_state.memory_state_id},
            quality,query_trace=request.query
        )

class UpdateSvc:
    def __init__(self): self.requests=[]
    def update(self,req):
        self.requests.append(req)
        m=MemoryStateReference(req.actor_id,req.prior_memory_state.memory_state_id+'-u',
                               req.next_actual_time,{'from':req.execution_status})
        prior=req.prior_expectation_state
        kid='k-u' if prior is None else prior.expectation_state_id+'-u'
        k=ExpectationStateReference(req.actor_id,kid,req.next_actual_time,
                                    {'from':req.execution_status})
        return PostExecutionEpistemicUpdateResult(
            req.actor_id,req.episode_id,m,k,True,True
        )

class World:
    def __init__(self): self.perception_seen=[]
    def represented_state_from_perception_inputs(self,actual,retrieval,expectation):
        self.perception_seen.append((actual.state_id,retrieval.retrieval_id,
                                     expectation.expectation_state_id if expectation else None))
        return WorldState(actual.time,{'G':10.0},
                          {'state_id':actual.state_id,'retrieval_id':retrieval.retrieval_id})
    def perceive(self,s): return s
    def domain_value(self,s,d): return float(s.powers[d])
    def project(self,s,a):
        if a.id=='steady':
            return ActionProjection(a.id,WorldState(s.time+1,{'G':9.0},dict(s.metadata)),True)
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

class TransitionSvc:
    def __init__(self): self.calls=0
    def transition(self,s,h):
        self.calls+=1
        nxt=ActualPersistentStateEnvelope(
            s.actor_id,f"s{int(s.time)+1}",s.time+1,s.pp,s.spv,s.avs,s.context
        )
        return Layer1TransitionResult(
            h.episode_id,h.selected_policy_id,s.state_id,nxt,True,{'ok':True}
        )

def build(*,update=True):
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
    w=World(); retrieval=RetrievalSvc(); transition=TransitionSvc(); upd=UpdateSvc() if update else None
    rt=PVPPRuntime(r,w,layer1_transition_service=transition,
                   memory_retrieval_service=retrieval,epistemic_update_service=upd)
    return rt,w,retrieval,transition,upd

def req():
    return CanonicalDecisionCycleRequest(
        PreliminaryPreservationObject('p','preserve continuity'),
        DomainFrame((DomainFrameTarget('G','continuity'),)),
        ('continuation',),(),('continuation',)
    )

def actual():
    return ActualPersistentStateEnvelope('actor','s0',0.0,{}, {}, {}, {})

def memory():
    return MemoryStateReference('actor','m0',0.0,{'opaque':'history'})

def expectation():
    return ExpectationStateReference('actor','k0',0.0,{'opaque':'forecast'})

def completed(label,idx,query):
    return MemoryConditionedCycleDirective(
        req(),query=query,execute=True,update_epistemic_state=True,
        episode_id=f'ep-{idx}',max_execution_steps=1,
        execution_observations=(ExecutionObservation(f'obs-{idx}',completed=True,
                                                     information={'cycle':idx}),),
        label=label
    )

def test_three_cycle_chain_retrieves_then_updates_then_retrieves_again():
    rt,w,retrieval,transition,upd=build()
    ds=(completed('c0',0,'q0'),completed('c1',1,'q1'),completed('c2',2,'q2'))
    out=rt.evaluate_memory_conditioned_cycle_sequence(actual(),memory(),ds,expectation())
    assert out.status=='memory_sequence_completed'
    assert out.completed_cycle_count==3
    assert out.final_actual_state.state_id=='s3'
    assert out.final_memory_state.memory_state_id=='m0-u-u-u'
    assert out.final_expectation_state.expectation_state_id=='k0-u-u-u'
    assert transition.calls==3 and len(upd.requests)==3 and len(retrieval.requests)==3
    # Each next retrieval must see the memory state returned by the prior update.
    assert [x.memory_state.memory_state_id for x in retrieval.requests]==['m0','m0-u','m0-u-u']
    assert [x.query for x in retrieval.requests]==['q0','q1','q2']

def test_memory_update_result_is_not_retrieved_until_next_explicit_directive():
    rt,w,retrieval,transition,upd=build()
    out=rt.evaluate_memory_conditioned_cycle_sequence(
        actual(),memory(),(completed('once',0,'first'),),expectation()
    )
    assert out.final_memory_state.memory_state_id=='m0-u'
    assert len(retrieval.requests)==1
    assert retrieval.requests[0].memory_state.memory_state_id=='m0'

def test_no_epistemic_update_preserves_m_and_k_across_transition():
    rt,w,retrieval,transition,upd=build()
    d=MemoryConditionedCycleDirective(
        req(),query='q',execute=True,update_epistemic_state=False,
        execution_observations=(ExecutionObservation('o',completed=True),)
    )
    out=rt.evaluate_memory_conditioned_cycle_sequence(actual(),memory(),(d,),expectation())
    assert out.status=='memory_sequence_completed'
    assert out.final_actual_state.state_id=='s1'
    assert out.final_memory_state.memory_state_id=='m0'
    assert out.final_expectation_state.expectation_state_id=='k0'
    assert len(upd.requests)==0

def test_update_requested_without_execution_fails_closed():
    rt,w,retrieval,transition,upd=build()
    d=MemoryConditionedCycleDirective(req(),query='q',execute=False,update_epistemic_state=True)
    try:
        rt.evaluate_memory_conditioned_cycle_sequence(actual(),memory(),(d,),expectation())
        assert False
    except ValueError as e:
        assert 'requires explicit execution' in str(e)
    assert transition.calls==0 and len(upd.requests)==0

def test_active_epsilon_stops_sequence_and_does_not_update_memory():
    rt,w,retrieval,transition,upd=build()
    d0=MemoryConditionedCycleDirective(
        req(),query='q0',execute=True,update_epistemic_state=False,
        max_execution_steps=3,
        execution_observations=(ExecutionObservation('stage',staged=True),)
    )
    d1=completed('must not run',1,'q1')
    out=rt.evaluate_memory_conditioned_cycle_sequence(actual(),memory(),(d0,d1),expectation())
    assert out.status=='memory_sequence_stopped_at_active_epsilon'
    assert out.completed_cycle_count==1
    assert len(retrieval.requests)==1
    assert transition.calls==0 and len(upd.requests)==0
    assert out.final_memory_state.memory_state_id=='m0'

def test_expected_state_guards_cover_actual_memory_and_expectation_identity():
    rt,w,retrieval,transition,upd=build()
    d=MemoryConditionedCycleDirective(
        req(),expected_actual_state_id='s0',expected_memory_state_id='m0',
        expected_expectation_state_id='k0'
    )
    out=rt.evaluate_memory_conditioned_cycle_sequence(actual(),memory(),(d,),expectation())
    assert out.status=='memory_sequence_completed'

    bad=MemoryConditionedCycleDirective(req(),expected_memory_state_id='wrong')
    try:
        rt.evaluate_memory_conditioned_cycle_sequence(actual(),memory(),(bad,),expectation())
        assert False
    except ValueError as e:
        assert 'expected memory state wrong, got m0' in str(e)

def test_ledger_captures_retrieval_decision_transition_and_updates():
    rt,w,retrieval,transition,upd=build()
    out=rt.evaluate_memory_conditioned_cycle_sequence(
        actual(),memory(),(completed('trace',0,'cue'),),expectation()
    )
    row=out.ledger[0]
    assert row.retrieval_id=='r-m0-cue'
    assert row.selected_policy_id=='graph:cont'
    assert row.epsilon_status=='completed'
    assert row.transition_applied and row.memory_updated and row.expectation_updated
    assert row.actual_state_id_after=='s1'
    assert row.memory_state_id_after=='m0-u'
    assert row.expectation_state_id_after=='k0-u'

def test_missing_update_service_is_visible_when_update_requested():
    rt,w,retrieval,transition,upd=build(update=False)
    d=completed('x',0,'q')
    try:
        rt.evaluate_memory_conditioned_cycle_sequence(actual(),memory(),(d,),expectation())
        assert False
    except ValueError as e:
        assert 'no EpistemicUpdateService' in str(e)
    assert transition.calls==1

def test_empty_memory_conditioned_sequence_is_noop():
    rt,w,retrieval,transition,upd=build()
    out=rt.evaluate_memory_conditioned_cycle_sequence(actual(),memory(),(),expectation())
    assert out.status=='memory_sequence_completed'
    assert out.completed_cycle_count==0
    assert out.final_actual_state.state_id=='s0'
    assert out.final_memory_state.memory_state_id=='m0'
    assert out.final_expectation_state.expectation_state_id=='k0'
    assert not retrieval.requests and transition.calls==0 and not upd.requests
