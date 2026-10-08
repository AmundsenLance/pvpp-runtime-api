
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def __init__(self):
        self.map_state_ids=[]
    def represented_state_from_actual(self,s):
        self.map_state_ids.append(s.state_id)
        return WorldState(s.time,{'G':10.0},{'state_id':s.state_id})
    def perceive(self,s): return s
    def domain_value(self,s,d): return float(s.powers.get(d,10.0))
    def project(self,s,a):
        if a.id=='steady':
            return ActionProjection(a.id,WorldState(s.time+1,{'G':9.0},dict(s.metadata)),True)
        return ActionProjection(a.id,s,True)
    def pressure_factors(self,s,d,drift): return PressureFactors(d,5.0,drift)
    def pressure_value(self,d,f): return 0.2
    def expected_deterioration(self,s,d,drift,p,f): return drift
    def constraint_profile(self,s,pid,a,r,g):
        return PolicyConstraintProfile(pid,(ConstraintObservation('soft',False),))
    def project_policy_record(self,s,pid,a):
        return PolicyProjectionRecord(
            pid,True,s,{'G':20.0},
            (RecoveryCorridorProjection('G','continuity',True,True,True,1.0,20.0),),
            projection_horizon=30.0
        )

class T:
    def __init__(self): self.calls=0
    def transition(self,s,h):
        self.calls+=1
        nxt=ActualPersistentStateEnvelope(
            s.actor_id,s.state_id+'-next',s.time+1,s.pp,s.spv,s.avs,s.context
        )
        return Layer1TransitionResult(
            h.episode_id,h.selected_policy_id,s.state_id,nxt,True,{'exclusive_transition':True}
        )

def build():
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',5.0))
    for a in ('steady','continue'):
        r.register_action(ActionDefinition(a,a,('G',)))
    r.register_governing_configuration(GoverningConfiguration(0.0))
    r.register_regime_configuration(RegimeConfiguration(1,2,4,100,50,10))
    r.register_constraint_rule(ConstraintRuleDefinition('soft','soft'))
    r.register_graph_instance(GraphInstanceDefinition('i','system',('G',),'active'))
    r.register_graph_transformation(GraphTransformationDefinition(
        'cont','i','i','continuation',('G',),'reachable','continue',('continuation',)
    ))
    r.register_sigma_order(SigmaOrderDefinition('graph:cont',1))
    w=W(); t=T()
    return PVPPRuntime(r,w,layer1_transition_service=t),w,t

def req(previous=None):
    return CanonicalDecisionCycleRequest(
        PreliminaryPreservationObject('p','preserve governing continuity'),
        DomainFrame((DomainFrameTarget('G','continuity'),)),
        ('continuation',),(),('continuation',),
        previous_regime=previous
    )

def actual():
    return ActualPersistentStateEnvelope('actor','s0',0.0,{}, {}, {}, {})

def completed(label,idx):
    return CanonicalCycleDirective(
        req(),True,f'ep-{idx}',2,(ExecutionObservation(f'ev-{idx}',completed=True),),
        label=label
    )

def test_three_explicit_cycles_thread_only_validated_layer1_state():
    rt,w,t=build()
    ds=(completed('c0',0),completed('c1',1),completed('c2',2))
    out=rt.evaluate_canonical_cycle_sequence(actual(),ds)
    assert out.status=='sequence_completed'
    assert out.requested_cycle_count==3 and out.completed_cycle_count==3
    assert out.final_actual_state.state_id=='s0-next-next-next'
    assert out.final_actual_state.time==3.0
    assert t.calls==3
    assert w.map_state_ids==['s0','s0-next','s0-next-next']
    assert [x.transition_applied for x in out.ledger]==[True,True,True]
    assert not out.invariant_violations

def test_abort_return_can_be_followed_only_by_explicit_later_directive():
    rt,w,t=build()
    d0=CanonicalCycleDirective(
        req(),True,'abort',2,(ExecutionObservation('fail',failed=True),),label='failed execution'
    )
    d1=completed('explicit reevaluation',1)
    out=rt.evaluate_canonical_cycle_sequence(actual(),(d0,d1))
    assert out.status=='sequence_completed'
    assert out.ledger[0].epsilon_status=='failed'
    assert out.ledger[0].return_upstream is True
    assert out.ledger[1].initial_state_id=='s0-next'
    assert w.map_state_ids==['s0','s0-next']
    assert t.calls==2

def test_active_epsilon_stops_sequence_before_hidden_reselection():
    rt,w,t=build()
    d0=CanonicalCycleDirective(
        req(),True,'active',3,(ExecutionObservation('stage',staged=True),),label='active stage'
    )
    d1=completed('must not run',1)
    out=rt.evaluate_canonical_cycle_sequence(actual(),(d0,d1))
    assert out.status=='sequence_stopped_at_active_epsilon'
    assert out.completed_cycle_count==1
    assert len(out.ledger)==1
    assert w.map_state_ids==['s0']
    assert t.calls==0

def test_sigma_only_cycles_do_not_mutate_or_advance_actual_state():
    rt,w,t=build()
    ds=tuple(CanonicalCycleDirective(req(),False,label=f'observe-{i}') for i in range(4))
    out=rt.evaluate_canonical_cycle_sequence(actual(),ds)
    assert out.status=='sequence_completed'
    assert out.final_actual_state.state_id=='s0'
    assert out.final_actual_state.time==0.0
    assert t.calls==0
    assert w.map_state_ids==['s0']*4
    assert all(not x.transition_applied for x in out.ledger)

def test_expected_initial_state_is_fail_closed_not_registration_or_order_inference():
    rt,w,t=build()
    d=CanonicalCycleDirective(req(),False,expected_initial_state_id='other')
    try:
        rt.evaluate_canonical_cycle_sequence(actual(),(d,))
        assert False
    except ValueError as e:
        assert 'expected initial state other, got s0' in str(e)
    assert w.map_state_ids==[] and t.calls==0

def test_previous_regime_is_not_hidden_runtime_memory():
    rt,w,t=build()
    explicit=PreviousRegimeState('Mission',10.0)
    d0=CanonicalCycleDirective(req(explicit),False,label='explicit hysteresis input')
    d1=CanonicalCycleDirective(req(None),False,label='no hysteresis input')
    out=rt.evaluate_canonical_cycle_sequence(actual(),(d0,d1))
    assert out.status=='sequence_completed'
    assert d0.request.previous_regime is explicit
    assert d1.request.previous_regime is None
    # Sequence execution does not mutate either directive/request.
    assert out.ledger[0].initial_state_id==out.ledger[1].initial_state_id=='s0'

def test_ledger_captures_operator_outcomes_without_becoming_selection_logic():
    rt,w,t=build()
    out=rt.evaluate_canonical_cycle_sequence(actual(),(completed('trace',0),))
    row=out.ledger[0]
    assert row.regime is not None
    assert row.governing_domain_ids==('G',)
    assert row.selected_policy_id=='graph:cont'
    assert row.selection_mode=='standard'
    assert row.epsilon_status=='completed'
    assert row.final_state_id=='s0-next'
    assert any('runtime did not derive the next directive' in n for n in row.notes)

def test_empty_sequence_is_finite_noop_not_heartbeat():
    rt,w,t=build()
    out=rt.evaluate_canonical_cycle_sequence(actual(),())
    assert out.status=='sequence_completed'
    assert out.completed_cycle_count==0
    assert out.final_actual_state.state_id=='s0'
    assert w.map_state_ids==[] and t.calls==0
