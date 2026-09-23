from dataclasses import replace
from pvpp_runtime import (
    PVPPRuntime, PVPPRegistry, DomainDefinition, ActionDefinition, ActualPersistentStateEnvelope,
    TransitionRelevantStateBasis, DecisionReplayPackage,
)


class W:
    def project(self,*a,**k): raise AssertionError("state-sufficiency validation must not project")

def runtime():
    r=PVPPRegistry()
    r.register_domain(DomainDefinition('d',0,0,1,1))
    r.register_action(ActionDefinition('steady',('d',),{},{}))
    return PVPPRuntime(r,W())


def state():
    return ActualPersistentStateEnvelope('a','s1',1.0,{'p':1},{'v':1},{'ok':True},{'x':1})


def basis(**kw):
    x=dict(basis_id='b1',actor_id='a',state_id='s1',modeled_purpose='forward-decision',
           admissible_context_id='ctx',material_state_surface_ids=('PP','SPV','AVS','X'),
           authoritative_reference_ids=(),source_version_ids=('spec-v2.1',),
           provenance_ids=('host',),host_validated_complete=True)
    x.update(kw); return TransitionRelevantStateBasis(**x)


def test_complete_declaration_validates():
    assert runtime().validate_transition_relevant_state_basis(state(),basis()).sufficient

def test_actor_mismatch_rejected():
    assert not runtime().validate_transition_relevant_state_basis(state(),basis(actor_id='b')).sufficient

def test_state_identity_mismatch_rejected():
    assert not runtime().validate_transition_relevant_state_basis(state(),basis(state_id='old')).sufficient

def test_modeled_purpose_required():
    assert not runtime().validate_transition_relevant_state_basis(state(),basis(modeled_purpose='')).sufficient

def test_admissible_context_required():
    assert not runtime().validate_transition_relevant_state_basis(state(),basis(admissible_context_id='')).sufficient

def test_host_must_explicitly_assert_completeness():
    a=runtime().validate_transition_relevant_state_basis(state(),basis(host_validated_complete=False))
    assert not a.sufficient and any('not declared' in v for v in a.violations)

def test_surfaces_or_authoritative_references_required():
    a=runtime().validate_transition_relevant_state_basis(state(),basis(material_state_surface_ids=(),authoritative_reference_ids=()))
    assert not a.sufficient

def test_authoritative_reference_can_carry_material_state():
    b=basis(material_state_surface_ids=(),authoritative_reference_ids=('institution-state:7',))
    assert runtime().validate_transition_relevant_state_basis(state(),b).sufficient

def test_duplicate_surface_ids_rejected():
    assert not runtime().validate_transition_relevant_state_basis(state(),basis(material_state_surface_ids=('PP','PP'))).sufficient

def test_same_complete_state_and_context_same_structure_is_consistent():
    a=basis(); b=replace(a,basis_id='b2')
    z=runtime().assess_transition_relevant_state_pair(a,b,left_transition_structure_id='R1',right_transition_structure_id='R1')
    assert z.consistent

def test_same_complete_state_and_context_different_structure_exposes_incompleteness():
    a=basis(); b=replace(a,basis_id='b2')
    z=runtime().assess_transition_relevant_state_pair(a,b,left_transition_structure_id='R1',right_transition_structure_id='R2')
    assert not z.consistent and z.violations

def test_different_admissible_context_may_have_different_structure():
    a=basis(); b=replace(a,basis_id='b2',admissible_context_id='ctx2')
    assert runtime().assess_transition_relevant_state_pair(a,b,left_transition_structure_id='R1',right_transition_structure_id='R2').consistent

def test_different_present_state_surface_may_have_different_structure():
    a=basis(); b=replace(a,basis_id='b2',material_state_surface_ids=('PP','SPV','AVS','X','K'))
    assert runtime().assess_transition_relevant_state_pair(a,b,left_transition_structure_id='R1',right_transition_structure_id='R2').consistent

def test_history_is_not_required_in_state_sufficiency_declaration():
    b=basis()
    assert not hasattr(b,'transfer_history') and not hasattr(b,'causal_history')
    assert runtime().validate_transition_relevant_state_basis(state(),b).sufficient

def test_state_sufficiency_does_not_mutate_actual_state():
    s=state(); before=repr(s)
    runtime().validate_transition_relevant_state_basis(s,basis())
    assert repr(s)==before

def test_replay_package_remains_separate_from_state_sufficiency_basis():
    b=basis()
    assert not hasattr(b,'replay_package')
    assert 'DecisionReplayPackage' not in type(b).__name__

def test_state_sufficiency_has_no_graph_or_execution_authority_fields():
    b=basis()
    for name in ('authorized','admitted','selected','execution_license','graph_admission','utility','rank'):
        assert not hasattr(b,name)

def test_actual_state_semantics_remain_opaque_to_runtime():
    s=ActualPersistentStateEnvelope('a','s1',1.0,object(),object(),object(),object())
    assert runtime().validate_transition_relevant_state_basis(s,basis()).sufficient
