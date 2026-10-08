from pvpp_runtime import PVPPRuntime, PVPPRegistry, RecoveryResourceState, QualifiedUnitState, ActionDefinition
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self, state): return state
    def domain_value(self, state, domain_id): return 0.0
    def project(self, state, action): return ActionProjection(action.id, state, True)

def runtime():
    registry = PVPPRegistry()
    registry.register_action(ActionDefinition("steady", "steady", ()))
    return PVPPRuntime(registry, W())


def test_reserve_does_not_imply_recovery_capability_or_reachability():
    state = RecoveryResourceState("r1", 1.0, reserve={"fuel": 10})
    a = runtime().validate_recovery_resource_state(state)
    assert a.valid
    assert state.recovery_capable is None
    assert state.currently_reachable is None


def test_recovery_capability_does_not_imply_current_reachability():
    state = RecoveryResourceState("r1", 1.0, recovery_capable=True, currently_reachable=False)
    assert runtime().validate_recovery_resource_state(state).valid
    assert state.recovery_capable is True and state.currently_reachable is False


def test_reachability_can_be_true_with_no_reserve_claim():
    state = RecoveryResourceState("r1", 1.0, currently_reachable=True, evidence_ids=("e1",))
    assert runtime().validate_recovery_resource_state(state).valid
    assert state.reserve is None


def test_recovery_validation_rejects_duplicate_prerequisites():
    state = RecoveryResourceState("r1", 1.0, prerequisite_ids=("p", "p"))
    a = runtime().validate_recovery_resource_state(state)
    assert not a.valid
    assert any("unique" in v for v in a.violations)


def test_nested_unit_is_neutral_by_default():
    state = QualifiedUnitState("team", "collective", member_ids=("a", "b"), parent_unit_id="org")
    a = runtime().validate_qualified_unit_state(state)
    assert a.valid
    assert state.productive_role_qualified is False


def test_productive_role_qualification_requires_explicit_evidence():
    state = QualifiedUnitState("team", "collective", productive_role_qualified=True)
    a = runtime().validate_qualified_unit_state(state)
    assert not a.valid
    assert any("explicit evidence" in v for v in a.violations)


def test_productive_role_qualification_with_evidence_is_representable():
    state = QualifiedUnitState("team", "collective", productive_role_qualified=True,
                               qualification_evidence_ids=("prq:team:1",))
    assert runtime().validate_qualified_unit_state(state).valid


def test_unit_cannot_be_its_own_member_or_parent():
    state = QualifiedUnitState("u", "component", member_ids=("u",), parent_unit_id="u")
    a = runtime().validate_qualified_unit_state(state)
    assert not a.valid
    assert len(a.violations) == 2
