from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
from datetime import datetime, timezone
import pytest
from pvpp_runtime import ExecutionBindingIdentity, ExecutionObservation
from pvpp_runtime.execution import ExecutionBindingRegistry
from pvpp_runtime.models import GovernanceInvalidationSignal
from pvpp_runtime.supervision import CanonicalRuntimeBridge
from r22_real_cycle_fixture import new_runtime_and_license
from pvpp_runtime.supervision.observation import ObservationService, SourceRegistration, ExternalObservation
from pvpp_runtime.supervision.dependency import DependencyService
from pvpp_runtime.supervision.continuation import ContinuationService
from pvpp_runtime.supervision.store import ConcurrencyConflict


def setup(tmp_path):
    rt,lic=new_runtime_and_license(); bridge=CanonicalRuntimeBridge(rt)
    action_id=lic.action_ids[0]
    reg=ExecutionBindingRegistry(tuple(rt.registry.actions)); reg.register(ExecutionBindingIdentity('b',action_id,'1'),lambda ctx:'ok')
    ep=bridge.instantiate_execution('ep',lic,entry_sufficient=True,max_steps=5).episode
    auth=bridge.issue_native_execution_authorization(ep,action_id,reg,decision_cycle_id='cy',configuration_id='cfg')
    store=trusted_store(tmp_path/'s.db'); handle=bridge.resolve_canonical_execution(auth,configuration_id='cfg')
    rec=bridge.register_active_execution(store,handle,execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id),registered_at='2026-10-02T10:00:00+00:00')
    obs=ObservationService(store); dep=DependencyService(store); cont=ContinuationService(store,dep,bridge)
    src=SourceRegistration('sr','src',('observation',),('reachability',),('sub',),('cfg',),('governance',),'att',None,None,'current','admin',1); register_test_source(obs, src)
    o=ExternalObservation('o1','src','reachability','net','sub','cfg','up',None,'2026-10-02T10:00:00','x','x',{}); obs.submit_observation(o); a=obs.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00'); obs.commit_admission_change(o,a,committed_at='2026-10-02T10:00:00+00:00')
    dep.register_dependency_binding(active_execution_id=rec.active_execution_id,configuration_id='cfg',fact_kind='reachability',fact_id='net',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00')
    return rt,bridge,store,obs,dep,cont,rec

def test_active_epsilon_maps_to_continue(tmp_path):
    *_,dep,cont,rec=setup(tmp_path); snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    a=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('e1'),trigger_ids=('tr',),assessed_at='2026-10-02T10:00:00+00:00')
    assert a.continuation_posture=='continue' and a.epsilon_status=='active'

def test_continuation_failure_maps_canonical_abort_return(tmp_path):
    *_,dep,cont,rec=setup(tmp_path); snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    a=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('e1',continuation_sufficient=False),assessed_at='2026-10-02T10:00:00+00:00')
    assert a.continuation_posture=='abort_return' and a.authority_fence_required and a.epsilon_status=='aborted_return'

def test_emergency_maps_canonical_emergency_return(tmp_path):
    *_,dep,cont,rec=setup(tmp_path); snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    a=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('e1',emergency=True),assessed_at='2026-10-02T10:00:00+00:00')
    assert a.continuation_posture=='emergency_return' and a.authority_fence_required

def test_explicit_invalidation_uses_canonical_reentry_plan_without_epsilon_step(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path); snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    sig=GovernanceInvalidationSignal('s1','Adequacy','changed','dependency_change:reachability',('ev',),('art',),rec.execution_id,'cfg')
    a=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,invalidation_signals=(sig,),assessed_at='2026-10-02T10:00:00+00:00')
    assert a.continuation_posture=='reauthorization_required' and 'Adequacy' in a.reentry_plan_ref
    assert bridge.current_episode('ep').step_count==0

def test_stale_snapshot_rejected_before_canonical_mutation(tmp_path):
    rt,bridge,store,obs,dep,cont,rec=setup(tmp_path); snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    o=ExternalObservation('o2','src','reachability','net','sub','cfg','down',None,'2026-10-02T11:00:00','y','y',{}); obs.submit_observation(o); aa=obs.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00'); obs.commit_admission_change(o,aa,committed_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ConcurrencyConflict): cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('e1'),assessed_at='2026-10-02T10:00:00+00:00')
    assert bridge.current_episode('ep').step_count==0

def test_checkpoint_captures_fresh_snapshot_internally(tmp_path):
    *_,dep,cont,rec=setup(tmp_path)
    a=cont.checkpoint(active_execution_id=rec.active_execution_id,observation=ExecutionObservation('e1',staged=True),trigger_ids=('cp',),checkpoint_at='2026-10-02T10:00:00+00:00')
    assert a.input_snapshot_id==a.committed_snapshot_id and a.continuation_posture=='continue'

def test_caller_cannot_supply_continuation_posture(tmp_path):
    *_,dep,cont,rec=setup(tmp_path); snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ValueError,match='not authoritative'): cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('e1'),requested_posture='abort_return',assessed_at='2026-10-02T10:00:00+00:00')

def test_snapshot_execution_scope_cannot_be_laundered(tmp_path):
    *_,dep,cont,rec=setup(tmp_path); snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    with pytest.raises(ConcurrencyConflict): cont.evaluate_continuation(active_execution_id='other',snapshot=snap,observation=ExecutionObservation('e1'),assessed_at='2026-10-02T10:00:00+00:00')
