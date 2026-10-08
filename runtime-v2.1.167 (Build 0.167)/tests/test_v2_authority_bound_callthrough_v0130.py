from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import pytest
from pvpp_runtime import (PVPPRuntime, PVPPRegistry, ActionDefinition, ExecutionBindingRegistry,
    ExecutionBindingIdentity, ExecutionLicenseEnvelope, NativeExecutionAuthorization,
    CleanExecutionFailure, CompletedInvalidExecution)
from pvpp_runtime.models import ActionProjection

from test_mode_aware_epsilon_license_v037 import build as canonical_build, req as canonical_req, st as canonical_state

def setup(target=lambda c: "ok", *, mode="standard", config=None):
    rt=canonical_build(inadequate=(mode=="recovery_unavailable_fallback"), terminal=(mode=="terminal_infeasibility"))
    cycle=rt.evaluate_canonical_decision_cycle(canonical_state(),canonical_req())
    lic=rt.build_execution_license_from_cycle(cycle,canonical_req().domain_frame)
    br=ExecutionBindingRegistry(tuple(rt.registry.actions))
    for aid in lic.action_ids:
        br.register(ExecutionBindingIdentity("b-"+aid,aid,"1.0",("p",)),target)
    step=rt.instantiate_execution("ep1",lic,entry_sufficient=True,max_steps=2)
    return rt,br,step.episode

def auth(rt,br,ep,**kw):
    return rt.issue_native_execution_authorization(ep,ep.license.action_ids[0],br,decision_cycle_id="cy1",**kw)

def action(ep): return ep.license.action_ids[0]

def test_abct01_public_context_bypass_rejected():
    calls=[]; rt,br,ep=setup(lambda c: calls.append(1)); c=br.create_context(action_id=action(ep),decision_cycle_id="fake")
    with pytest.raises(RuntimeError,match="native execution authorization"): br.invoke(c)
    assert calls==[]

def test_abct02_standard_authorized_once():
    calls=[]; rt,br,ep=setup(lambda c: calls.append(c.execution_id) or "yes"); a=auth(rt,br,ep)
    r=rt.invoke_authorized_native(a,br); assert r.status=="succeeded" and len(calls)==1 and rt.native_execution_authorization_status(a.authorization_id)=="consumed"

def test_abct03_fallback_authorized():
    calls=[]; rt,br,ep=setup(lambda c: calls.append(1),mode="recovery_unavailable_fallback"); a=auth(rt,br,ep); assert rt.invoke_authorized_native(a,br).status=="succeeded" and calls==[1]

def test_abct04_terminal_cannot_issue():
    rt,br,ep=setup(mode="terminal_infeasibility"); assert not ep.active
    with pytest.raises(ValueError): auth(rt,br,ep)

def test_abct05_replay_rejected():
    calls=[]; rt,br,ep=setup(lambda c: calls.append(1)); a=auth(rt,br,ep); rt.invoke_authorized_native(a,br)
    with pytest.raises(RuntimeError,match="consumed"): rt.invoke_authorized_native(a,br)
    assert calls==[1]

def test_abct06_reconstructed_token_rejected():
    calls=[]; rt,br,ep=setup(lambda c: calls.append(1)); a=auth(rt,br,ep); fake=replace(a)
    assert fake==a and fake is not a
    with pytest.raises(ValueError,match="runtime-issued ledger record"): rt.invoke_authorized_native(fake,br)
    assert calls==[]

def test_abct07_post_effect_exception_consumed():
    calls=[]
    def f(c): calls.append(1); raise RuntimeError("deep boom")
    rt,br,ep=setup(f); a=auth(rt,br,ep); r=rt.invoke_authorized_native(a,br)
    assert r.status=="indeterminate" and r.error_message=="deep boom" and calls==[1] and rt.native_execution_authorization_status(a.authorization_id)=="consumed"

def test_abct08_clean_failure_consumed():
    rt,br,ep=setup(lambda c: (_ for _ in ()).throw(CleanExecutionFailure("no effect"))); a=auth(rt,br,ep); r=rt.invoke_authorized_native(a,br)
    assert r.status=="failed_cleanly" and not r.external_effect_possible and rt.native_execution_authorization_status(a.authorization_id)=="consumed"

def test_abct09_transport_failures_consumed():
    for exc in (TimeoutError("t"),ConnectionError("c")):
        rt,br,ep=setup(lambda c,e=exc: (_ for _ in ()).throw(e)); a=auth(rt,br,ep); r=rt.invoke_authorized_native(a,br)
        assert r.status=="indeterminate" and r.failure_stage=="transport" and rt.native_execution_authorization_status(a.authorization_id)=="consumed"

def test_abct10_completed_invalid_preserved():
    rt,br,ep=setup(lambda c: (_ for _ in ()).throw(CompletedInvalidExecution("bad transition"))); a=auth(rt,br,ep); r=rt.invoke_authorized_native(a,br)
    assert r.status=="completed_invalid" and r.completed and r.transition_valid is False

@pytest.mark.parametrize("state",["paused","aborted","reauthorization_required"])
def test_abct11_13_control_gate_invalidates_before_call(state):
    calls=[]; rt,br,ep=setup(lambda c: calls.append(1)); a=auth(rt,br,ep); eid=rt.native_execution_authorization_execution_id(a.authorization_id); br.set_control_state(eid,state,reason="test")
    with pytest.raises(RuntimeError,match="invalidated"): rt.invoke_authorized_native(a,br)
    assert calls==[] and rt.native_execution_authorization_status(a.authorization_id)=="invalidated"

def test_abct14_action_and_unknown_authority_fail_closed():
    calls=[]; rt,br,ep=setup(lambda c: calls.append(1)); a=auth(rt,br,ep); fake=replace(a,action_id="steady")
    with pytest.raises(ValueError): rt.invoke_authorized_native(fake,br)
    unknown=replace(a,authorization_id="missing")
    with pytest.raises(KeyError,match="native execution authorization"): rt.invoke_authorized_native(unknown,br)
    assert calls==[]

def test_abct15_binding_version_mismatch_fails_closed():
    rt,br,ep=setup(); a=auth(rt,br,ep); br._bindings_by_id[a.binding_id]=replace(br._bindings_by_id[a.binding_id],identity=replace(br.identity(a.binding_id),implementation_version="2.0"))
    with pytest.raises(ValueError,match="implementation version"): rt.invoke_authorized_native(a,br)

def test_abct16_configuration_bound_exactly():
    calls=[]; rt,br,ep=setup(lambda c: calls.append(1)); a=auth(rt,br,ep,configuration_id="cfg-X")
    with pytest.raises(ValueError,match="configuration mismatch"): rt.invoke_authorized_native(a,br)
    assert calls==[]; assert rt.invoke_authorized_native(a,br,configuration_id="cfg-X").status=="succeeded"

def test_abct17_metadata_smuggling_has_no_authority():
    calls=[]; rt,br,ep=setup(lambda c: calls.append(1)); c=br.create_context(action_id=action(ep),decision_cycle_id="fake",metadata={"AUTHORIZED":True,"SUPERUSER":True})
    with pytest.raises(RuntimeError): br.invoke(c)
    assert calls==[]

def test_abct18_attempt_is_bound_and_positive():
    rt,br,ep=setup();
    with pytest.raises(ValueError): auth(rt,br,ep,attempt=0)
    a=auth(rt,br,ep,attempt=1); fake=replace(a,attempt=2)
    with pytest.raises(ValueError): rt.invoke_authorized_native(fake,br)

def test_abct19_explicit_episode_invalidation():
    calls=[]; rt,br,ep=setup(lambda c: calls.append(1)); a=auth(rt,br,ep); ids=rt.invalidate_native_execution_authorizations(episode_id="ep1",reason="governance re-entry")
    assert ids==(a.authorization_id,)
    with pytest.raises(RuntimeError,match="invalidated"): rt.invoke_authorized_native(a,br)
    assert calls==[]

def test_abct20_audit_snapshots_are_non_authorizing():
    rt,br,ep=setup(); a=auth(rt,br,ep); snap=rt.native_execution_authorizations(episode_id="ep1")[0]
    assert snap==a and snap is not a
    with pytest.raises(ValueError,match="runtime-issued ledger record"): rt.invoke_authorized_native(snap,br)
    rt.invoke_authorized_native(a,br); assert rt.native_execution_authorizations()[0].status=="consumed" and a.status=="issued"

def test_abct21_concurrent_replay_race_at_most_one_call():
    calls=[]
    def f(c): calls.append(c.execution_id); return 1
    rt,br,ep=setup(f); a=auth(rt,br,ep)
    def go():
        try: return rt.invoke_authorized_native(a,br).status
        except RuntimeError: return "rejected"
    with ThreadPoolExecutor(max_workers=2) as ex: results=list(ex.map(lambda _:go(),range(2)))
    assert calls and len(calls)==1 and sorted(results)==["rejected","succeeded"]

def test_abct22_issuance_audit_sequence_monotonic():
    rt,br,ep=setup(); a1=auth(rt,br,ep,attempt=1); a2=auth(rt,br,ep,attempt=2)
    assert a2.issued_sequence==a1.issued_sequence+1 and [x.authorization_id for x in rt.native_execution_authorizations()]==[a1.authorization_id,a2.authorization_id]

def test_abct20_layer1_indeterminate_returns_upstream_conservatively():
    from pvpp_runtime import ExecutionContext
    marker=[]
    def f(c): marker.append("effect"); raise RuntimeError("after effect")
    rt,br,ep=setup(f); a=auth(rt,br,ep); r=rt.invoke_authorized_native(a,br)
    ctx=ExecutionContext(r.execution_id,a.action_id,a.binding_id,a.decision_cycle_id,a.attempt,configuration_id=a.configuration_id)
    h=br.build_layer1_handoff(ctx,r,selected_policy_id=a.selected_policy_id)
    assert marker==["effect"] and r.status=="indeterminate" and h.return_upstream is True
