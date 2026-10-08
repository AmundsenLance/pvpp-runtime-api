from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
from dataclasses import replace
from datetime import datetime, timezone
import pytest

from pvpp_runtime import ExecutionBindingIdentity
from pvpp_runtime.execution import ExecutionBindingRegistry
from pvpp_runtime.supervision import CanonicalResolutionError, CanonicalRuntimeBridge, ConfigurationConflict
from r22_real_cycle_fixture import new_runtime_and_license


def now(): return datetime.now(timezone.utc).isoformat()

def setup(tmp_path, fn=lambda ctx: "ok", configuration_id="cfg-A"):
    rt,lic=new_runtime_and_license(); bridge=CanonicalRuntimeBridge(rt)
    action_id=lic.action_ids[0]
    reg=ExecutionBindingRegistry(tuple(rt.registry.actions)); reg.register(ExecutionBindingIdentity('b',action_id,'1'), fn)
    ep=bridge.instantiate_execution('ep-1',lic,entry_sufficient=True,max_steps=2).episode
    auth=bridge.issue_native_execution_authorization(ep,action_id,reg,decision_cycle_id='cycle-1',configuration_id=configuration_id)
    db=tmp_path/'supervisor.db'; store=trusted_store(db)
    return rt,bridge,reg,ep,auth,store


def test_fabricated_or_copied_authorization_cannot_resolve(tmp_path):
    _,bridge,_,_,auth,store=setup(tmp_path)
    try:
        copied=replace(auth)
        assert copied == auth and copied is not auth
        with pytest.raises(CanonicalResolutionError, match='canonical_resolution_failed'):
            bridge.resolve_canonical_execution(copied,configuration_id='cfg-A')
    finally: store.close()


def test_cross_configuration_lineage_rejected(tmp_path):
    _,bridge,_,_,auth,store=setup(tmp_path)
    try:
        with pytest.raises(ConfigurationConflict, match='configuration_conflict'):
            bridge.resolve_canonical_execution(auth,configuration_id='cfg-B')
    finally: store.close()


def test_stale_invalidated_lineage_cannot_resolve(tmp_path):
    rt,bridge,_,ep,auth,store=setup(tmp_path)
    try:
        rt.invalidate_native_execution_authorizations(episode_id=ep.episode_id,reason='test stale')
        with pytest.raises(CanonicalResolutionError, match='status is invalidated'):
            bridge.resolve_canonical_execution(auth,configuration_id='cfg-A')
    finally: store.close()


def test_active_execution_registration_is_durable_and_unique(tmp_path):
    rt,bridge,_,_,auth,store=setup(tmp_path)
    try:
        handle=bridge.resolve_canonical_execution(auth,configuration_id='cfg-A')
        execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id)
        rec=bridge.register_active_execution(store,handle,execution_id=execution_id,registered_at=now())
        assert store.get_active_execution(rec.active_execution_id) == rec
        with pytest.raises(Exception):
            bridge.register_active_execution(store,handle,execution_id=execution_id,registered_at=now())
    finally: store.close()


def test_pre_entry_registration_required_before_governed_invoke(tmp_path):
    calls=[]
    rt,bridge,reg,_,auth,store=setup(tmp_path,lambda ctx: calls.append(ctx.execution_id) or 'ok')
    try:
        with pytest.raises(CanonicalResolutionError, match='pre_entry_registration_required'):
            bridge.invoke_registered_native(store,'missing',auth,reg,configuration_id='cfg-A')
        assert calls == []
        handle=bridge.resolve_canonical_execution(auth,configuration_id='cfg-A')
        rec=bridge.register_active_execution(store,handle,execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id),registered_at=now())
        result=bridge.invoke_registered_native(store,rec.active_execution_id,auth,reg,configuration_id='cfg-A')
        assert result.status == 'succeeded' and len(calls) == 1
    finally: store.close()


def test_handle_itself_is_not_native_execution_authority(tmp_path):
    _,bridge,reg,_,auth,store=setup(tmp_path)
    try:
        handle=bridge.resolve_canonical_execution(auth,configuration_id='cfg-A')
        with pytest.raises(CanonicalResolutionError):
            bridge.invoke_authorized_native(handle,reg,configuration_id='cfg-A')
    finally: store.close()
