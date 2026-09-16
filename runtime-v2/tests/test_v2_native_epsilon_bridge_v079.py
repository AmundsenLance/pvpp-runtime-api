import pytest
from pvpp_runtime import ActionDefinition, DomainDefinition, ExecutionBindingIdentity, ExecutionLicenseEnvelope, PVPPRuntime, PVPPRegistry
from pvpp_runtime.execution import ExecutionBindingRegistry
from pvpp_runtime.models import NativeExecutionResult


def _instantiate_unit(rt, episode_id, license, **kwargs):
    # Downstream epsilon unit tests intentionally bypass canonical-cycle setup.
    # This test-only private injection supplies the upstream provenance precondition;
    # production callers have no public authority-minting equivalent.
    rt._canonical_execution_licenses[id(license)]=(license, -1, "issued")
    return rt.instantiate_execution(episode_id, license, **kwargs)


def setup():
    preg=PVPPRegistry(); preg.register_domain(DomainDefinition('d','D',0.0)); preg.register_action(ActionDefinition('steady','steady',('d',)))
    class World: pass
    rt=PVPPRuntime(preg,World())
    reg=ExecutionBindingRegistry({'steady'})
    reg.register(ExecutionBindingIdentity('b','steady','1'), lambda ctx: 'ok')
    ctx=reg.create_context(action_id='steady',decision_cycle_id='c1',execution_id='x1')
    lic=ExecutionLicenseEnvelope('p',('steady',),(),(),True,True,True,True)
    ep=_instantiate_unit(rt,'x1',lic,entry_sufficient=True,max_steps=2).episode
    return rt,reg,ctx,ep

def result(status, **kw):
    defaults=dict(execution_id='x1',action_id='steady',binding_id='b',status=status)
    defaults.update(kw); return NativeExecutionResult(**defaults)

def test_success_enters_existing_epsilon_trace_and_completes():
    rt,reg,ctx,ep=setup(); r=result('succeeded',completed=True,external_effect_possible=True)
    tel=reg.telemetry(ctx,r,telemetry_id='tel1'); obs=reg.epsilon_observation(ctx,r,telemetry=tel)
    step=rt.advance_execution(ep,obs)
    assert step.status=='completed' and step.execution_path==('tel1',)
    assert step.information_events[0]['execution_id']=='x1'

def test_clean_failure_maps_to_canonical_failed():
    rt,reg,ctx,ep=setup(); r=result('failed_cleanly',completed=False,external_effect_possible=False)
    step=rt.advance_execution(ep,reg.epsilon_observation(ctx,r))
    assert step.status=='failed' and step.return_upstream

def test_indeterminate_without_realized_bundle_is_not_known_failure():
    rt,reg,ctx,ep=setup(); r=result('indeterminate',completed=False,external_effect_possible=True)
    step=rt.advance_execution(ep,reg.epsilon_observation(ctx,r))
    assert step.status=='aborted_return' and step.return_upstream
    assert step.information_events[0]['external_effect_possible'] is True

def test_indeterminate_with_observed_effect_is_partial_realization():
    rt,reg,ctx,ep=setup(); r=result('indeterminate',completed=False,external_effect_possible=True)
    obs=reg.epsilon_observation(ctx,r,realized_pv_bundle={'observed':'effect'})
    step=rt.advance_execution(ep,obs)
    assert step.status=='partial_realization' and step.realized_pv_bundles==({'observed':'effect'},)

def test_completed_invalid_returns_upstream_via_completion_sufficiency():
    rt,reg,ctx,ep=setup(); r=result('completed_invalid',completed=True,external_effect_possible=True,transition_valid=False)
    step=rt.advance_execution(ep,reg.epsilon_observation(ctx,r))
    assert step.status=='aborted_return' and step.return_upstream

def test_bridge_rejects_telemetry_identity_mismatch():
    _,reg,ctx,_=setup(); r=result('succeeded',completed=True)
    tel=reg.telemetry(ctx,r)
    bad=type(tel)(tel.telemetry_id,'other',tel.action_id,tel.binding_id,tel.decision_cycle_id,tel.attempt,tel.status,tel.external_effect_possible,tel.completed,tel.failure_stage,tel.error_type,tel.error_message,tel.correlation_id,tel.configuration_id,tel.notes)
    with pytest.raises(ValueError): reg.epsilon_observation(ctx,r,telemetry=bad)

def test_bridge_rejects_status_mismatch():
    _,reg,ctx,_=setup(); r=result('succeeded',completed=True)
    tel=reg.telemetry(ctx,r)
    bad=type(tel)(tel.telemetry_id,tel.execution_id,tel.action_id,tel.binding_id,tel.decision_cycle_id,tel.attempt,'indeterminate',tel.external_effect_possible,tel.completed,tel.failure_stage,tel.error_type,tel.error_message,tel.correlation_id,tel.configuration_id,tel.notes)
    with pytest.raises(ValueError): reg.epsilon_observation(ctx,r,telemetry=bad)
