from pvpp_runtime import (
    AdapterIdentity, RuntimeConfigurationProvenance, PVPPRegistry, PVPPRuntime,
    DomainDefinition, ActionDefinition,
)

class W:
    def execute(self, state, action_id): raise NotImplementedError


def runtime():
    r=PVPPRegistry(); r.register_domain(DomainDefinition('d',0,0,1,1))
    r.register_action(ActionDefinition('steady',('d',),{},{}))
    return PVPPRuntime(r,W())


def aid(i, role): return AdapterIdentity(i, role, '1.0', ('source:a',))


def test_configuration_provenance_accepts_separated_adapter_roles():
    rec=RuntimeConfigurationProvenance('cfg','PV-PP V2','0.74',1.0,(
        aid('state','state_measurement'), aid('actions','action_structure'),
        aid('projection','projection_world_model'), aid('evidence','constraint_evidence'),
        aid('transition','execution_transition')),('control-doc',))
    a=runtime().validate_runtime_configuration_provenance(rec)
    assert a.valid
    assert 'does not confer canonical operator authority' in a.notes[0]


def test_configuration_rejects_duplicate_adapter_identity():
    x=aid('same','state_measurement')
    rec=RuntimeConfigurationProvenance('cfg','V2','0.74',0,(x,x))
    a=runtime().validate_runtime_configuration_provenance(rec)
    assert not a.valid and any('identities must be unique' in v for v in a.violations)


def test_configuration_rejects_duplicate_role_to_avoid_implicit_override():
    rec=RuntimeConfigurationProvenance('cfg','V2','0.74',0,(aid('a','state_measurement'),aid('b','state_measurement')))
    a=runtime().validate_runtime_configuration_provenance(rec)
    assert not a.valid and any('roles must be unique' in v for v in a.violations)


def test_configuration_rejects_unknown_adapter_role():
    rec=RuntimeConfigurationProvenance('cfg','V2','0.74',0,(aid('x','selector'),))
    a=runtime().validate_runtime_configuration_provenance(rec)
    assert not a.valid and any('unsupported adapter_role' in v for v in a.violations)


def test_configuration_requires_framework_runtime_and_configuration_identity():
    rec=RuntimeConfigurationProvenance('','','',0)
    a=runtime().validate_runtime_configuration_provenance(rec)
    assert not a.valid and len(a.violations)==3


def test_configuration_rejects_duplicate_source_ids():
    rec=RuntimeConfigurationProvenance('cfg','V2','0.74',0,(),('s','s'))
    a=runtime().validate_runtime_configuration_provenance(rec)
    assert not a.valid and any('source_ids' in v for v in a.violations)
