
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))

from pvpp_runtime import *
from test_canonical_decision_cycle_v032 import build, req, state


def attach_m4_corridors(rt):
    for aid in ('crop_maintain','crop_harvest','teach_complete'):
        if aid not in rt.registry.actions:
            rt.registry.register_action(ActionDefinition(
                aid,aid,('G',),{'capacity_demands':{'skilled_labor_session':1}}
            ))
    rt.active_corridors={
        'crop_cycle':ActiveRecoveryCorridor(
            'crop_cycle','G','crop_cycle_continuity',
            ('crop_maintain','crop_harvest'),1.0
        ),
        'k_transfer':ActiveRecoveryCorridor(
            'k_transfer','G','cultivation_technique_continuity',
            ('teach_complete',),1.0
        ),
    }


class ContextCapacityService:
    """Host test service: interprets host-specific actual-state context."""
    def __init__(self):
        self.calls=[]
    def derive(self, actual_state, request):
        self.calls.append((actual_state,request))
        # Small-economy-like semantics remain wholly host-owned here.
        people=actual_state.context['people']
        commitments=actual_state.context.get('commitments',{})
        capacities={}
        for period in range(2):
            available=0
            for person in people:
                if not person['alive']:
                    continue
                if 'cultivation' not in person['skills']:
                    continue
                seasonal_remaining=person['seasonal_labor'].get(period,0)
                reserved=commitments.get((person['id'],period),0)
                available += max(0, seasonal_remaining-reserved)
            capacities[period]={'skilled_labor_session':float(available)}
        return CapacityAuthorityEnvelope(
            actual_state.actor_id,actual_state.state_id,actual_state.time,
            CapacityCalendar(capacities),
            source_id='small_economy_people_capacity',
            notes=('derived from living skilled people, seasonal labor, and commitments',)
        )


def make_integrated(capacity_service=None, people=None, commitments=None):
    rt,w=build()
    attach_m4_corridors(rt)
    rt.capacity_authority_service=capacity_service
    w.represented_state_from_actual=lambda actual: state()
    actual=ActualPersistentStateEnvelope(
        'agent','s0',0.0,{}, {}, {},
        {
            'people': people or [
                {'id':'p1','alive':True,'skills':('cultivation',),'seasonal_labor':{0:1,1:1}},
            ],
            'commitments':commitments or {}
        }
    )
    return rt,w,actual


def test_integrated_cycle_derives_scarce_calendar_from_actual_state_and_fails_closed():
    service=ContextCapacityService()
    rt,w,actual=make_integrated(service)
    out=rt.evaluate_integrated_canonical_cycle(actual,req(),execute=False)
    assert out.decision.status=='joint_recovery_feasibility_failed'
    assert out.decision.stopped_at=='Joint Recovery Feasibility'
    assert len(service.calls)==1
    request=service.calls[0][1]
    assert request.active_corridor_ids==('crop_cycle','k_transfer')
    assert request.remaining_action_ids==('crop_maintain','crop_harvest','teach_complete')
    assert request.demanded_resource_ids==('skilled_labor_session',)
    assert request.latest_deadline==1.0
    assert out.decision.joint_recovery_feasibility.report.infeasible_corridor_sets==( ('crop_cycle','k_transfer'), )


def test_integrated_cycle_derives_sufficient_calendar_and_reaches_sigma():
    service=ContextCapacityService()
    people=[
        {'id':'p1','alive':True,'skills':('cultivation',),'seasonal_labor':{0:1,1:1}},
        {'id':'p2','alive':True,'skills':('cultivation',),'seasonal_labor':{0:1,1:0}},
    ]
    rt,w,actual=make_integrated(service,people=people)
    out=rt.evaluate_integrated_canonical_cycle(actual,req(),execute=False)
    assert out.decision.status=='sigma_standard_policy_selected'
    assert out.decision.joint_recovery_feasibility.jointly_feasible is True
    schedule=out.decision.joint_recovery_feasibility.report.schedule
    assert len(schedule)==3
    assert len(service.calls)==1
    assert any('CapacityAuthorityService' in n for n in out.notes)


def test_dead_person_does_not_contribute_capacity_because_host_service_decides_semantics():
    service=ContextCapacityService()
    people=[
        {'id':'p1','alive':True,'skills':('cultivation',),'seasonal_labor':{0:1,1:1}},
        {'id':'p2','alive':False,'skills':('cultivation',),'seasonal_labor':{0:100,1:100}},
    ]
    rt,w,actual=make_integrated(service,people=people)
    out=rt.evaluate_integrated_canonical_cycle(actual,req(),execute=False)
    assert out.decision.status=='joint_recovery_feasibility_failed'


def test_existing_commitment_reduces_capacity_in_host_derivation():
    service=ContextCapacityService()
    people=[
        {'id':'p1','alive':True,'skills':('cultivation',),'seasonal_labor':{0:1,1:1}},
        {'id':'p2','alive':True,'skills':('cultivation',),'seasonal_labor':{0:1,1:0}},
    ]
    rt,w,actual=make_integrated(
        service,people=people,commitments={('p2',0):1}
    )
    out=rt.evaluate_integrated_canonical_cycle(actual,req(),execute=False)
    assert out.decision.status=='joint_recovery_feasibility_failed'


def test_explicit_request_calendar_is_not_overridden_by_derivation_service():
    service=ContextCapacityService()
    rt,w,actual=make_integrated(service)
    explicit=CapacityCalendar({
        0:{'skilled_labor_session':2},
        1:{'skilled_labor_session':1},
    })
    out=rt.evaluate_integrated_canonical_cycle(
        actual,req(joint_recovery_capacity_calendar=explicit),execute=False
    )
    assert out.decision.status=='sigma_standard_policy_selected'
    assert service.calls==[]


def test_missing_service_preserves_v050_fail_closed_behavior():
    rt,w,actual=make_integrated(None)
    out=rt.evaluate_integrated_canonical_cycle(actual,req(),execute=False)
    assert out.decision.status=='joint_recovery_capacity_authority_required'


def test_runtime_does_not_open_actual_state_to_derive_semantics_itself():
    service=ContextCapacityService()
    rt,w,actual=make_integrated(service)
    built=rt.build_capacity_authority_request(actual)
    # Structural request contains only runtime-known demand context, not people/skills.
    assert not hasattr(built,'people')
    assert not hasattr(built,'skills')
    assert not hasattr(built,'commitments')
    assert built.actor_id=='agent' and built.state_id=='s0'


def test_capacity_envelope_identity_mismatch_is_rejected():
    class Bad:
        def derive(self,actual,request):
            return CapacityAuthorityEnvelope(
                actual.actor_id,'wrong',actual.time,
                CapacityCalendar({0:{'skilled_labor_session':2},1:{'skilled_labor_session':1}})
            )
    rt,w,actual=make_integrated(Bad())
    try:
        rt.evaluate_integrated_canonical_cycle(actual,req(),execute=False)
        assert False
    except ValueError as e:
        assert 'state_id mismatch' in str(e)


def test_negative_or_nonfinite_derived_capacity_is_rejected():
    class Bad:
        def derive(self,actual,request):
            return CapacityAuthorityEnvelope(
                actual.actor_id,actual.state_id,actual.time,
                CapacityCalendar({0:{'skilled_labor_session':-1}})
            )
    rt,w,actual=make_integrated(Bad())
    try:
        rt.evaluate_integrated_canonical_cycle(actual,req(),execute=False)
        assert False
    except ValueError as e:
        assert 'finite and nonnegative' in str(e)


def test_direct_worldstate_cycle_does_not_call_capacity_service():
    service=ContextCapacityService()
    rt,w,actual=make_integrated(service)
    a=rt.evaluate_canonical_decision_cycle(state(),req())
    assert a.status=='joint_recovery_capacity_authority_required'
    assert service.calls==[]
