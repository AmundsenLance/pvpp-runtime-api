from pvpp_runtime import EvidenceSourceAuthorityState, GovernanceEvidenceDependency, assess_evidence_dependency_authority

def dep(**kw):
    d=dict(dependency_id="d1", fact_id="f1", observation_id="o1", source_id="sensor:a", source_provenance_id="prov:a", dependency_role="primary")
    d.update(kw); return GovernanceEvidenceDependency(**d)

def src(**kw):
    d=dict(source_id="sensor:a", provenance_id="prov:a", assessed_at=10.0, authority_state="trusted", control_state="independent")
    d.update(kw); return EvidenceSourceAuthorityState(**d)

def test_trusted_independent_source_retains_authority():
    a=assess_evidence_dependency_authority(dep(),src()); assert a.valid and a.retains_epistemic_authority and a.loss_reason is None

def test_compromised_source_loses_authority():
    a=assess_evidence_dependency_authority(dep(),src(authority_state="compromised")); assert a.valid and not a.retains_epistemic_authority and a.loss_reason=="source_compromised"

def test_governed_agent_control_loses_authority():
    a=assess_evidence_dependency_authority(dep(),src(control_state="governed_agent")); assert a.loss_reason=="source_controlled_by_governed_agent"

def test_descendant_control_loses_authority():
    a=assess_evidence_dependency_authority(dep(),src(control_state="descendant")); assert a.loss_reason=="source_controlled_by_descendant"

def test_expired_source_loses_authority_as_of_time():
    a=assess_evidence_dependency_authority(dep(),src(valid_until=20.0),as_of=21.0); assert a.loss_reason=="source_expired"

def test_degraded_or_unknown_is_unresolved_not_trusted():
    assert assess_evidence_dependency_authority(dep(),src(authority_state="degraded")).loss_reason=="source_authority_unresolved"
    assert assess_evidence_dependency_authority(dep(),src(control_state="unknown")).loss_reason=="source_authority_unresolved"

def test_identity_or_provenance_mismatch_is_invalid():
    a=assess_evidence_dependency_authority(dep(),src(source_id="sensor:b")); assert not a.valid and not a.retains_epistemic_authority
    b=assess_evidence_dependency_authority(dep(),src(provenance_id="prov:b")); assert not b.valid

def test_assessment_is_stage_neutral_and_non_authorizing():
    a=assess_evidence_dependency_authority(dep(),src(authority_state="revoked")); assert not hasattr(a,"stage") and not hasattr(a,"reentry_plan") and not hasattr(a,"execution_license")
