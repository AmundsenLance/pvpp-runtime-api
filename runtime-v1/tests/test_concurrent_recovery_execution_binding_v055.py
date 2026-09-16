import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class M7World:
    def __init__(self):
        self.constraint_calls=[]
        self.q_calls=[]
    def perceive(self,s): return s
    def domain_value(self,s,d): return float(s.powers.get(d,10.0))
    def project(self,s,a):
        if a.id=='steady':
            return ActionProjection(a.id,WorldState(s.time+1,{**s.powers,'G':self.domain_value(s,'G')-1}),True)
        return ActionProjection(a.id,s,True)
    def pressure_factors(self,state,did,baseline_drift):
        return PressureFactors(did,self.domain_value(state,did)-5.0,baseline_drift)
    def pressure_value(self,did,factors): return 1.0/max(factors.margin,0.1)
    def expected_deterioration(self,state,did,baseline_drift,pressure_value,pressure_factors): return baseline_drift
    def constraint_profile(self,state,pid,action_ids,regime,governing):
        self.constraint_calls.append((pid,tuple(action_ids)))
        return PolicyConstraintProfile(pid,(ConstraintObservation('soft',False),))
    def project_policy_record(self,state,pid,action_ids):
        self.q_calls.append((pid,tuple(action_ids)))
        return PolicyProjectionRecord(
            pid,True,state,{'G':20.0},
            (RecoveryCorridorProjection('G','continuity',True,True,True,1.0,20.0),),
            projection_horizon=30.0
        )
    def represented_state_from_actual(self,actual): return state()

class Transition:
    def __init__(self): self.handoffs=[]
    def transition(self,current,handoff):
        self.handoffs.append(handoff)
        nxt=ActualPersistentStateEnvelope(current.actor_id,'s1',current.time+1,{}, {}, {}, {})
        return Layer1TransitionResult(handoff.episode_id,handoff.selected_policy_id,current.state_id,nxt,True,{},())

def build():
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',5.0))
    for aid in ('steady','crop_maintain','crop_harvest','teach_complete','gather'):
        md={'capacity_demands':{'skilled_labor_session':1}} if aid in ('crop_maintain','crop_harvest','teach_complete') else {}
        r.register_action(ActionDefinition(aid,aid,('G',),md))
    r.register_governing_configuration(GoverningConfiguration(0.0))
    r.register_regime_configuration(RegimeConfiguration(1,2,4,100,50,10))
    r.register_constraint_rule(ConstraintRuleDefinition('soft','soft'))
    r.register_graph_instance(GraphInstanceDefinition('i','system',('G',),'active'))
    r.register_graph_transformation(GraphTransformationDefinition('crop','i','i','maintenance_local_adjustment',('G',),'reachable','crop_maintain',('crop_maintenance',)))
    r.register_graph_transformation(GraphTransformationDefinition('teach','i','i','maintenance_local_adjustment',('G',),'reachable','teach_complete',('knowledge_transfer',)))
    r.register_graph_transformation(GraphTransformationDefinition('gather','i','i','continuation',('G',),'reachable','gather',('continuation',)))
    r.register_sigma_order(SigmaOrderDefinition('graph:teach',10))
    r.register_sigma_order(SigmaOrderDefinition('graph:crop',20))
    r.register_sigma_order(SigmaOrderDefinition('graph:gather',30))
    r.register_recovery_plan(RecoveryPlanDefinition('crop_cycle','G','crop_cycle_continuity','crop_maintain',('crop_harvest',),1.0))
    r.register_recovery_plan(RecoveryPlanDefinition('k_transfer','G','cultivation_technique_continuity','teach_complete',(),1.0))
    w=M7World(); ts=Transition(); rt=PVPPRuntime(r,w,layer1_transition_service=ts)
    rt.active_corridors={
        'crop_cycle':ActiveRecoveryCorridor('crop_cycle','G','crop_cycle_continuity',('crop_maintain','crop_harvest'),1.0),
        'k_transfer':ActiveRecoveryCorridor('k_transfer','G','cultivation_technique_continuity',('teach_complete',),1.0),
    }
    return rt,w,ts

def state(): return WorldState(0,{'G':10.0})
def request():
    return CanonicalDecisionCycleRequest(
        preservation_object=PreliminaryPreservationObject('p','preserve continuity'),
        domain_frame=DomainFrame((DomainFrameTarget('G','continuity'),)),
        required_graph_family_ids=('continuation','maintenance_local_adjustment'),
        materially_required_policy_class_ids=('continuation','crop_maintenance','knowledge_transfer'),
        joint_recovery_capacity_calendar=CapacityCalendar({
            0:{'skilled_labor_session':2},
            1:{'skilled_labor_session':1},
        })
    )

def test_m7_verified_schedule_binds_both_current_actions_before_constraints_and_q():
    rt,w,ts=build(); a=rt.evaluate_canonical_decision_cycle(state(),request())
    assert a.status=='sigma_standard_policy_selected'
    assert a.joint_recovery_execution_binding.status=='current_period_joint_recovery_bound'
    assert a.joint_recovery_execution_binding.mandatory_action_ids==('crop_maintain','teach_complete')
    for pid,actions in w.constraint_calls:
        assert 'crop_maintain' in actions and 'teach_complete' in actions
    for pid,actions in w.q_calls:
        assert 'crop_maintain' in actions and 'teach_complete' in actions

def test_m7_sigma_identity_may_be_teach_but_selected_candidate_is_the_bound_policy_set():
    rt,w,ts=build(); a=rt.evaluate_canonical_decision_cycle(state(),request())
    assert a.selection.selected_policy_id=='graph:teach'
    c=next(c for c in a.pi_construction.policy_space.candidates if c.id=='graph:teach')
    assert c.action_ids==('crop_maintain','teach_complete')
    assert c.required_action_ids==('crop_maintain','teach_complete')

def test_m7_epsilon_license_preserves_full_mandatory_current_period_set():
    rt,w,ts=build(); a=rt.evaluate_canonical_decision_cycle(state(),request())
    lic=rt.build_execution_license_from_cycle(a,request().domain_frame)
    assert lic.selected_policy_id=='graph:teach'
    assert lic.selected_candidate_action_ids==('teach_complete',)
    assert lic.mandatory_recovery_action_ids==('crop_maintain','teach_complete')
    assert lic.action_ids==('crop_maintain','teach_complete')

def test_m7_layer1_handoff_explicitly_carries_full_licensed_action_set():
    rt,w,ts=build(); a=rt.evaluate_canonical_decision_cycle(state(),request())
    lic=rt.build_execution_license_from_cycle(a,request().domain_frame)
    entry=rt.instantiate_execution('m7',lic,entry_sufficient=True,max_steps=1)
    eps=rt.advance_execution(entry.episode,ExecutionObservation('host-completed-bundle',completed=True))
    h=rt.build_layer1_transition_handoff(eps)
    assert h.licensed_action_ids==('crop_maintain','teach_complete')
    assert h.mandatory_recovery_action_ids==('crop_maintain','teach_complete')

def test_m7_integrated_host_can_obey_handoff_without_reading_scheduler_side_channel():
    rt,w,ts=build()
    actual=ActualPersistentStateEnvelope('agent','s0',0.0,{}, {}, {}, {})
    out=rt.evaluate_integrated_canonical_cycle(
        actual,request(),execute=True,episode_id='m7',
        execution_observations=(ExecutionObservation('host-completed-bundle',completed=True),)
    )
    assert out.status=='integrated_cycle_transition_applied'
    assert out.execution_license.action_ids==('crop_maintain','teach_complete')
    assert out.handoff.licensed_action_ids==('crop_maintain','teach_complete')
    assert ts.handoffs[0].licensed_action_ids==('crop_maintain','teach_complete')

def test_only_earliest_period_is_bound_not_future_crop_harvest():
    rt,w,ts=build(); a=rt.evaluate_canonical_decision_cycle(state(),request())
    assert 'crop_harvest' not in a.joint_recovery_execution_binding.mandatory_action_ids
    for c in a.pi_construction.policy_space.candidates:
        assert 'crop_harvest' not in c.action_ids

def test_no_hidden_order_or_sacrifice_rule_added():
    rt,w,ts=build(); a=rt.evaluate_canonical_decision_cycle(state(),request())
    b=a.joint_recovery_execution_binding
    assert set(b.mandatory_action_ids)=={'crop_maintain','teach_complete'}
    assert any('no execution priority' in n for n in b.notes)
    assert not hasattr(b,'preferred_action_id')
    assert not hasattr(b,'sacrificed_corridor_id')

def test_no_active_corridors_does_not_rewrite_normal_candidates():
    rt,w,ts=build(); rt.active_corridors={}
    a=rt.evaluate_canonical_decision_cycle(state(),CanonicalDecisionCycleRequest(
        preservation_object=PreliminaryPreservationObject('p','preserve continuity'),
        domain_frame=DomainFrame((DomainFrameTarget('G','continuity'),)),
        required_graph_family_ids=('continuation','maintenance_local_adjustment'),
        materially_required_policy_class_ids=('continuation','crop_maintenance','knowledge_transfer'),
    ))
    assert a.joint_recovery_execution_binding.status=='no_current_period_joint_recovery_binding'
    by={c.id:c.action_ids for c in a.pi_construction.policy_space.candidates}
    assert by['graph:teach']==('teach_complete',)
    assert by['graph:crop']==('crop_maintain',)
