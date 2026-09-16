import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'examples'/'tiny_crossing_policy_world'))

from pvpp_runtime import *
from run_crossing_choice import build_runtime, state

def one_policy_space():
    return CandidatePolicySpace((
        CandidatePolicySet('food_policy',('favor_food',),policy_class_ids=('local',)),
    ),('local',))

def frame():
    return DomainFrame((
        DomainFrameTarget('F','F_viability'),
        DomainFrameTarget('M','M_viability'),
    ))

def selected_runtime_and_license():
    rt=build_runtime()
    original=rt.world.project_policy
    def q(st,pid,ids):
        pr=original(st,ids)
        corridors=(
            RecoveryCorridorProjection('F','F_viability',True,True,True,2.0,20.0),
            RecoveryCorridorProjection('M','M_viability',True,True,True,2.0,20.0),
        )
        return PolicyProjectionRecord(pid,True,pr.next_state,{'F':4.5,'M':4.0,'K':float('inf')},corridors)
    rt.world.project_policy_record=q
    sel=rt.evaluate_recovery_policy_space(state(),one_policy_space(),frame())
    assert sel.selected_policy_id=='food_policy'
    return rt,rt.build_execution_license(sel,frame())

def test_epsilon_accepts_only_upstream_licensed_selected_policy():
    rt,lic=selected_runtime_and_license()
    start=rt.instantiate_execution('ep1',lic,entry_sufficient=True,max_steps=5)
    assert start.status=='active'
    assert start.terminal is False
    assert start.episode.license.selected_policy_id=='food_policy'

def test_entry_failure_returns_upstream_without_execution():
    rt,lic=selected_runtime_and_license()
    start=rt.instantiate_execution('ep1',lic,entry_sufficient=False,max_steps=5)
    assert start.status=='aborted_return'
    assert start.return_upstream is True
    assert start.episode.step_count==0

def test_unlicensed_envelope_cannot_be_laundered_by_epsilon():
    rt,lic=selected_runtime_and_license()
    bad=ExecutionLicenseEnvelope(
        lic.selected_policy_id,lic.action_ids,lic.governing_domain_ids,
        lic.framed_function_ids,False,True,True,True)
    start=rt.instantiate_execution('ep1',bad,entry_sufficient=True,max_steps=5)
    assert start.status=='aborted_return'
    assert start.episode.active is False

def test_completion_status_and_realized_outputs_are_auditable_and_distinct():
    rt,lic=selected_runtime_and_license()
    ep=rt.instantiate_execution('ep1',lic,entry_sufficient=True,max_steps=5).episode
    r=rt.advance_execution(ep,ExecutionObservation(
        'finish',completed=True,completion_sufficient=True,
        realized_pv_bundle={'service':2},information={'observed':'ok'}))
    assert r.status=='completed'
    assert r.terminal is True
    assert r.return_upstream is False
    assert r.execution_path==('finish',)
    assert r.realized_pv_bundles==({'service':2},)
    assert r.information_events==({'observed':'ok'},)

def test_staged_completion_is_status_not_new_selection():
    rt,lic=selected_runtime_and_license()
    ep=rt.instantiate_execution('ep1',lic,entry_sufficient=True,max_steps=5).episode
    mid=rt.advance_execution(ep,ExecutionObservation('stage1',staged=True))
    assert mid.status=='active'
    assert mid.episode.license.selected_policy_id=='food_policy'
    done=rt.advance_execution(mid.episode,ExecutionObservation(
        'stage2',completed=True,staged=True,realized_pv_bundle={'service':1}))
    assert done.status=='completed_staged'
    assert done.execution_path==('stage1','stage2')

def test_material_policy_class_change_requires_return_upstream():
    rt,lic=selected_runtime_and_license()
    ep=rt.instantiate_execution('ep1',lic,entry_sufficient=True,max_steps=5).episode
    r=rt.advance_execution(ep,ExecutionObservation(
        'new_path_needed',material_policy_class_change_required=True))
    assert r.status=='aborted_return'
    assert r.return_upstream is True
    assert r.episode.license.selected_policy_id=='food_policy'

def test_continuation_failure_with_partial_bundle_reports_partial_realization():
    rt,lic=selected_runtime_and_license()
    ep=rt.instantiate_execution('ep1',lic,entry_sufficient=True,max_steps=5).episode
    r=rt.advance_execution(ep,ExecutionObservation(
        'partial',continuation_sufficient=False,realized_pv_bundle={'work':0.4}))
    assert r.status=='partial_realization'
    assert r.return_upstream is True
    assert r.realized_pv_bundles==({'work':0.4},)

def test_emergency_and_failed_statuses_are_distinct():
    rt,lic=selected_runtime_and_license()
    ep=rt.instantiate_execution('ep1',lic,entry_sufficient=True,max_steps=5).episode
    emergency=rt.advance_execution(ep,ExecutionObservation('hazard',emergency=True))
    assert emergency.status=='emergency_return'
    ep2=rt.instantiate_execution('ep2',lic,entry_sufficient=True,max_steps=5).episode
    failed=rt.advance_execution(ep2,ExecutionObservation('tool_break',failed=True))
    assert failed.status=='failed'

def test_bounded_step_limit_forces_return():
    rt,lic=selected_runtime_and_license()
    ep=rt.instantiate_execution('ep1',lic,entry_sufficient=True,max_steps=2).episode
    a=rt.advance_execution(ep,ExecutionObservation('one'))
    assert a.status=='active'
    b=rt.advance_execution(a.episode,ExecutionObservation('two'))
    assert b.status=='aborted_return'
    assert b.return_upstream is True
    assert b.execution_path==('one','two')

def test_epsilon_does_not_call_host_execute_or_reproject():
    rt,lic=selected_runtime_and_license()
    def forbidden(*args,**kwargs):
        raise AssertionError('epsilon must not perform Layer 1 transition or projection')
    rt.world.execute=forbidden
    rt.world.project=forbidden
    rt.world.project_policy=forbidden
    ep=rt.instantiate_execution('ep1',lic,entry_sufficient=True,max_steps=3).episode
    r=rt.advance_execution(ep,ExecutionObservation('finish',completed=True))
    assert r.status=='completed'

def test_sigma_without_explicit_stage3_order_cannot_enter_epsilon():
    rt=build_runtime()
    space=CandidatePolicySpace((
        CandidatePolicySet('food_policy',('favor_food',),policy_class_ids=('local',)),
        CandidatePolicySet('material_policy',('favor_material',),policy_class_ids=('shift',)),
    ),('local','shift'))
    original=rt.world.project_policy
    def q(st,pid,ids):
        pr=original(st,ids)
        hs={'F':4.5,'M':4.0,'K':float('inf')} if pid=='food_policy' else {'F':4.0,'M':4.5,'K':float('inf')}
        corridors=(
            RecoveryCorridorProjection('F','F_viability',True,True,True,2.0,20.0),
            RecoveryCorridorProjection('M','M_viability',True,True,True,2.0,20.0),
        )
        return PolicyProjectionRecord(pid,True,pr.next_state,hs,corridors)
    rt.world.project_policy_record=q
    try:
        rt.evaluate_recovery_policy_space(state(),space,frame())
        assert False
    except ValueError as e:
        assert 'OrderIndex' in str(e)
