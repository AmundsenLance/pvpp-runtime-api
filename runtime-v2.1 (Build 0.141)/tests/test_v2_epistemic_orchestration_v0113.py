from pvpp_runtime import (
    EvidenceSourceAuthorityState, GovernanceEvidenceDependency,
    EvidenceCanonicalArtifactDependency, orchestrate_epistemic_invalidation_reentry,
)

def src(authority="compromised", control="independent", prov="prov:s", valid_until=None):
    return EvidenceSourceAuthorityState("sensor:1",prov,100.0,authority,control,valid_until,{},())
def ed(i="ed:1", fact="fact:t", source="sensor:1", prov="prov:s"):
    return GovernanceEvidenceDependency(i,fact,"obs:1",source,prov,"primary",())
def cad(i="cad:1", e="ed:1", fact="fact:t", stage="Phi", artifact="phi:1"):
    return EvidenceCanonicalArtifactDependency(i,e,fact,artifact,stage,("prov:cad",),())

def test_compromised_source_runs_complete_declared_chain_to_plan():
    x=orchestrate_epistemic_invalidation_reentry(src(),(ed(),),(cad(),))
    assert x.valid and len(x.authority_assessments)==1
    assert not x.authority_assessments[0].retains_epistemic_authority
    assert x.governance_invalidation.plan.recompute_from_stage=="Phi"

def test_trusted_source_preserves_chain_but_creates_no_invalidation():
    x=orchestrate_epistemic_invalidation_reentry(src("trusted"),(ed(),),(cad(),))
    assert x.valid and x.authority_assessments[0].retains_epistemic_authority
    assert not x.governance_invalidation.invalidation_signals

def test_only_dependencies_for_exact_source_and_provenance_are_evaluated():
    x=orchestrate_epistemic_invalidation_reentry(src(),(ed(),ed("ed:2",source="sensor:2"),ed("ed:3",prov="prov:old")),(cad(),))
    assert x.valid and x.evidence_dependency_ids==("ed:1",)
    assert len(x.authority_assessments)==1

def test_multiple_artifacts_choose_earliest_declared_stage():
    deps=(cad("cad:s","ed:1",stage="Sigma",artifact="sigma:1"),cad("cad:g","ed:1",stage="G",artifact="g:1"))
    x=orchestrate_epistemic_invalidation_reentry(src(),(ed(),),deps)
    assert x.governance_invalidation.plan.recompute_from_stage=="G"

def test_expiration_is_evaluated_at_explicit_as_of_time():
    x=orchestrate_epistemic_invalidation_reentry(src("trusted",valid_until=110.0),(ed(),),(cad(),),as_of=120.0)
    assert x.valid and x.authority_assessments[0].loss_reason=="source_expired"

def test_duplicate_evidence_dependency_identity_fails_closed():
    x=orchestrate_epistemic_invalidation_reentry(src(),(ed(),ed()),(cad(),))
    assert not x.valid and x.governance_invalidation is None

def test_invalid_artifact_dependency_is_preserved_as_failed_downstream_assessment():
    x=orchestrate_epistemic_invalidation_reentry(src(),(ed(),),(cad(stage="NoStage"),))
    assert not x.valid and x.governance_invalidation is not None
    assert not x.governance_invalidation.valid

def test_orchestration_stops_before_recomputation_and_execution():
    x=orchestrate_epistemic_invalidation_reentry(src(),(ed(),),(cad(),))
    assert x.governance_invalidation.plan.execute_reentry is False
    assert not hasattr(x,"execution_license") and not hasattr(x,"epsilon")
