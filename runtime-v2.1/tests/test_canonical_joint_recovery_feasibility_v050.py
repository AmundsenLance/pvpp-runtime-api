import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import *
from test_canonical_decision_cycle_v032 import build, req, state

def attach_m4_corridors(rt):
    for aid in ('crop_maintain','crop_harvest','teach_complete'):
        rt.registry.register_action(ActionDefinition(aid,aid,('G',),{'capacity_demands':{'skilled_labor_session':1}}))
    rt.active_corridors={
        'crop_cycle':ActiveRecoveryCorridor('crop_cycle','G','crop_cycle_continuity',('crop_maintain','crop_harvest'),1.0),
        'k_transfer':ActiveRecoveryCorridor('k_transfer','G','cultivation_technique_continuity',('teach_complete',),1.0),
    }
    return rt

def scarce(): return CapacityCalendar({0:{'skilled_labor_session':1},1:{'skilled_labor_session':1}})
def sufficient(): return CapacityCalendar({0:{'skilled_labor_session':2},1:{'skilled_labor_session':1}})

def test_m4_joint_conflict_blocks_before_adequacy_and_sigma():
    rt,w=build(); attach_m4_corridors(rt)
    a=rt.evaluate_canonical_decision_cycle(state(),req(joint_recovery_capacity_calendar=scarce(),joint_recovery_diagnostic_mode='all_minimal'))
    assert a.status=='joint_recovery_feasibility_failed'; assert a.stopped_at=='Joint Recovery Feasibility'
    assert a.adequacy is None and a.selection is None and w.q_calls==[]
    j=a.joint_recovery_feasibility
    assert j.runtime_verified and j.jointly_feasible is False
    assert j.report.infeasible_corridor_sets==( ('crop_cycle','k_transfer'), )
    assert j.report.bottleneck_resources[('crop_cycle','k_transfer')]==('skilled_labor_session',)
    assert 'Sigma' not in a.pipeline_trace

def test_m4_sufficient_capacity_allows_same_cycle_to_proceed_normally():
    rt,w=build(); attach_m4_corridors(rt)
    a=rt.evaluate_canonical_decision_cycle(state(),req(joint_recovery_capacity_calendar=sufficient()))
    assert a.status=='sigma_standard_policy_selected'; assert a.stopped_at=='Sigma'
    assert a.selection.selected_policy_id=='graph:adj'
    j=a.joint_recovery_feasibility
    assert j.runtime_verified and j.jointly_feasible is True and len(j.report.schedule)==3
    assert {s.corridor_id for s in j.report.schedule}=={'crop_cycle','k_transfer'}
    assert a.pipeline_trace.index('Joint Recovery Feasibility') < a.pipeline_trace.index('Adequacy')

def test_single_active_corridor_is_feasible_under_same_scarce_calendar():
    rt,w=build(); attach_m4_corridors(rt); rt.active_corridors.pop('k_transfer')
    a=rt.evaluate_canonical_decision_cycle(state(),req(joint_recovery_capacity_calendar=scarce()))
    assert a.status=='sigma_standard_policy_selected'
    assert a.joint_recovery_feasibility.jointly_feasible is True
    assert {s.corridor_id for s in a.joint_recovery_feasibility.report.schedule}=={'crop_cycle'}

def test_capacity_bearing_active_corridors_require_capacity_authority():
    rt,w=build(); attach_m4_corridors(rt)
    a=rt.evaluate_canonical_decision_cycle(state(),req())
    assert a.status=='joint_recovery_capacity_authority_required'; assert a.stopped_at=='Joint Recovery Feasibility'
    assert a.selection is None and a.adequacy is None and w.q_calls==[]
    j=a.joint_recovery_feasibility
    assert not j.capacity_authority_supplied and not j.runtime_verified and j.jointly_feasible is None

def test_host_projection_true_cannot_override_runtime_joint_infeasibility():
    rt,w=build(); attach_m4_corridors(rt)
    a=rt.evaluate_canonical_decision_cycle(state(),req(joint_recovery_capacity_calendar=scarce()))
    assert a.status=='joint_recovery_feasibility_failed'; assert w.q_calls==[]

def test_no_sacrifice_or_priority_is_embedded_when_joint_set_conflicts():
    rt,w=build(); attach_m4_corridors(rt)
    a=rt.evaluate_canonical_decision_cycle(state(),req(joint_recovery_capacity_calendar=scarce()))
    assert a.selection is None and a.joint_recovery_feasibility.report.schedule==()
    assert any('no priority' in n for n in a.joint_recovery_feasibility.report.notes)
    assert any('sacrifice' in n for n in a.notes)

def test_non_capacity_active_corridor_does_not_force_calendar():
    rt,w=build(); rt.registry.register_action(ActionDefinition('noop_recovery','noop',('G',)))
    rt.active_corridors={'plain':ActiveRecoveryCorridor('plain','G','continuity',('noop_recovery',),1.0)}
    a=rt.evaluate_canonical_decision_cycle(state(),req())
    assert a.status=='sigma_standard_policy_selected'
    j=a.joint_recovery_feasibility
    assert j.status=='active_corridors_have_no_represented_capacity_demands' and j.runtime_verified and j.jointly_feasible is True

def test_no_active_corridor_requires_no_capacity_authority():
    rt,w=build(); a=rt.evaluate_canonical_decision_cycle(state(),req())
    assert a.status=='sigma_standard_policy_selected'
    j=a.joint_recovery_feasibility
    assert j.status=='no_active_recovery_corridors' and j.runtime_verified and j.jointly_feasible is True

def test_integrated_cycle_propagates_joint_failure_without_execution():
    rt,w=build(); attach_m4_corridors(rt); w.represented_state_from_actual=lambda actual: state()
    actual=ActualPersistentStateEnvelope('agent','s0',0.0,{}, {}, {}, {})
    out=rt.evaluate_integrated_canonical_cycle(actual,req(joint_recovery_capacity_calendar=scarce()),execute=True,episode_id='m4-integrated')
    assert out.decision.status=='joint_recovery_feasibility_failed'; assert out.decision.selection is None
    assert out.epsilon_result is None and out.transition_result is None and out.final_actual_state==actual

def test_default_witness_mode_keeps_conflict_diagnostics_bounded():
    rt,w=build(); attach_m4_corridors(rt)
    a=rt.evaluate_canonical_decision_cycle(state(),req(joint_recovery_capacity_calendar=scarce()))
    rep=a.joint_recovery_feasibility.report
    assert rep.infeasible_sets_complete is False and rep.infeasible_corridor_sets==( ('crop_cycle','k_transfer'), )
