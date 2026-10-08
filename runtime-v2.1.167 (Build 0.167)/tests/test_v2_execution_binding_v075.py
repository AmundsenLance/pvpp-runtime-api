import pytest

from pvpp_runtime import ActionDefinition, ExecutionBindingIdentity, ExecutionBindingRegistry


def registry():
    return ExecutionBindingRegistry(("steady", "repair"))


def identity(binding_id="repair-local", action_id="repair"):
    return ExecutionBindingIdentity(binding_id, action_id, "1.0", ("prov-1",))


def test_binding_registration_does_not_invoke_callable():
    calls=[]
    r=registry()
    r.register(identity(), lambda *a, **k: calls.append((a,k)))
    assert calls == []
    assert r.identity_for_action("repair").binding_id == "repair-local"


def test_unknown_action_fails_closed():
    r=registry()
    with pytest.raises(ValueError):
        r.register(identity(action_id="invented"), lambda: None)


def test_one_binding_per_action_and_binding_id():
    r=registry(); r.register(identity(), lambda: None)
    with pytest.raises(ValueError): r.register(ExecutionBindingIdentity("repair-other","repair","1"), lambda: None)
    with pytest.raises(ValueError): r.register(ExecutionBindingIdentity("repair-local","steady","1"), lambda: None)


def test_target_must_be_callable():
    with pytest.raises(TypeError): registry().register(identity(), object())


def test_context_has_unique_execution_identity_and_correlation_fields():
    r=registry(); r.register(identity(), lambda: None)
    a=r.create_context(action_id="repair", decision_cycle_id="cycle-7", correlation_id="corr-1", configuration_id="cfg-2")
    b=r.create_context(action_id="repair", decision_cycle_id="cycle-7", attempt=2)
    assert a.execution_id != b.execution_id
    assert a.binding_id == "repair-local" and a.action_id == "repair"
    assert a.correlation_id == "corr-1" and a.configuration_id == "cfg-2"
    assert b.attempt == 2


def test_context_requires_registered_binding_and_cycle_identity():
    r=registry()
    with pytest.raises(KeyError): r.create_context(action_id="repair", decision_cycle_id="c")
    r.register(identity(), lambda: None)
    with pytest.raises(ValueError): r.create_context(action_id="repair", decision_cycle_id="")
    with pytest.raises(ValueError): r.create_context(action_id="repair", decision_cycle_id="c", attempt=0)


def test_duplicate_provenance_is_invalid():
    r=registry()
    bad=ExecutionBindingIdentity("b","repair","1",("p","p"))
    assessment=r.assess_identity(bad)
    assert not assessment.valid
    assert "duplicate_provenance_identity" in assessment.violations
