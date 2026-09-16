from pvpp_runtime import (
    AccessOperabilityState, ProductiveConfigurationState, PVPPRegistry, PVPPRuntime,
    ActionDefinition, ActualPersistentStateEnvelope, PerceivedDecisionState, WorldState,
)

class World: pass

def runtime():
    r=PVPPRegistry(); r.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(r,World())

def test_access_dimensions_are_independent_and_not_collapsed_into_usability():
    rt=runtime()
    s=AccessOperabilityState('tool',1.0,possessed=True,available=True,permitted=False,controlled=True,operable=True)
    a=rt.validate_access_operability_state(s)
    assert a.valid
    assert s.possessed and s.operable and not s.permitted
    assert any('independent' in n for n in a.notes)

def test_unknown_access_dimension_is_representable_without_runtime_inference():
    rt=runtime()
    s=AccessOperabilityState('remote-service',2.0,available=True,permitted=None,operable=None)
    assert rt.validate_access_operability_state(s).valid
    assert s.permitted is None and s.operable is None

def test_access_validation_rejects_bad_identity_time_and_nonboolean_dimension():
    rt=runtime()
    s=AccessOperabilityState('',float('nan'),possessed='yes')
    a=rt.validate_access_operability_state(s)
    assert not a.valid
    assert 'resource_id is required' in a.violations
    assert 'observed_time must be finite' in a.violations
    assert 'possessed must be bool or None' in a.violations

def test_configuration_is_structured_and_joint_feasibility_is_domain_supplied():
    rt=runtime()
    s=ProductiveConfigurationState('cfg',('agent','tool'),('network',),jointly_feasible=False,evidence_ids=('obs-1',))
    a=rt.validate_productive_configuration_state(s)
    assert a.valid
    assert s.component_ids==('agent','tool')
    assert s.jointly_feasible is False
    assert not hasattr(s,'aggregate_pp') and not hasattr(s,'score')

def test_configuration_rejects_duplicate_or_missing_component_identity():
    rt=runtime()
    a=rt.validate_productive_configuration_state(ProductiveConfigurationState('cfg',('x','x')))
    assert not a.valid and 'component_ids must be unique' in a.violations
    b=rt.validate_productive_configuration_state(ProductiveConfigurationState('cfg',()))
    assert not b.valid and 'at least one component_id is required' in b.violations

def test_existing_v2_actual_state_crosswalk_remains_pp_component_not_complete_state():
    rt=runtime()
    s=ActualPersistentStateEnvelope('actor','s0',0.0,{'skill':1},{'reserve':2},{'viable':True},{'env':'x'})
    assert rt.validate_actual_persistent_state(s).valid
    assert s.pp != s and s.spv is not None and s.avs is not None and s.context is not None

def test_existing_v2_perceived_state_keeps_ppp_distinct_from_other_surfaces():
    rt=runtime(); actual=ActualPersistentStateEnvelope('actor','s0',0.0,{}, {}, {}, {})
    represented=WorldState(0.0,{}, {'state_id':'s0'})
    p=PerceivedDecisionState('actor','s0',0.0,represented,ppp={'cap':1},spv_hat={'reserve':2},pvs={'v':1},x_hat={'x':1})
    a=rt.validate_perceived_decision_state(p,actual)
    assert a.valid
    assert p.ppp is not p.spv_hat and p.ppp is not p.pvs and p.ppp is not p.x_hat
