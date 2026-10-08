from pvpp_runtime import (
    EvidenceDependencyAuthorityAssessment, EvidenceCanonicalArtifactDependency,
    derive_evidence_authority_governance_invalidations,
)

def auth(dep="ed:1", fact="fact:temp", retain=False, reason="source_compromised", prov="prov:source"):
    return EvidenceDependencyAuthorityAssessment(True,dep,fact,"sensor:1",prov,retain,None if retain else reason,(),())

def art(i="cad:1", ed="ed:1", fact="fact:temp", artifact="phi:1", stage="Phi", prov=("prov:artifact",)):
    return EvidenceCanonicalArtifactDependency(i,ed,fact,artifact,stage,prov,())

def test_lost_authority_invalidates_explicit_artifact_and_stage():
    x=derive_evidence_authority_governance_invalidations((auth(),),(art(),))
    assert x.valid and len(x.invalidation_signals)==1
    assert x.reentry.recompute_from_stage=="Phi"
    assert x.plan.recompute_from_stage=="Phi"
    assert x.invalidation_signals[0].artifact_ids==("phi:1",)

def test_retained_authority_creates_no_invalidation():
    x=derive_evidence_authority_governance_invalidations((auth(retain=True),),(art(),))
    assert x.valid and not x.invalidation_signals and not x.reentry.return_to_governance
    assert x.plan.recompute_from_stage is None

def test_unmatched_fact_or_dependency_does_not_infer_stage():
    x=derive_evidence_authority_governance_invalidations((auth(),),(art(ed="ed:other"),))
    assert x.valid and not x.invalidation_signals and not x.matched_artifact_dependency_ids

def test_multiple_explicit_dependencies_choose_earliest_stage_only_by_declared_stages():
    deps=(art("cad:sigma",artifact="sigma:1",stage="Sigma"),art("cad:g",artifact="g:1",stage="G"))
    x=derive_evidence_authority_governance_invalidations((auth(),),deps)
    assert x.reentry.recompute_from_stage=="G"
    assert set(x.plan.invalidated_artifact_ids)=={"sigma:1","g:1"}

def test_provenance_is_carried_into_invalidation_evidence():
    x=derive_evidence_authority_governance_invalidations((auth(prov="prov:src"),),(art(prov=("prov:decl",)),))
    assert x.invalidation_signals[0].evidence_ids==("prov:src","prov:decl")

def test_invalid_authority_assessment_fails_closed():
    bad=EvidenceDependencyAuthorityAssessment(False,"ed:1","fact:temp","sensor:1","prov",False,"bad",("bad",),())
    x=derive_evidence_authority_governance_invalidations((bad,),(art(),))
    assert not x.valid and not x.invalidation_signals and x.plan is None

def test_invalid_stage_fails_closed():
    x=derive_evidence_authority_governance_invalidations((auth(),),(art(stage="NotAStage"),))
    assert not x.valid and not x.invalidation_signals

def test_mapping_creates_no_execution_authority():
    x=derive_evidence_authority_governance_invalidations((auth(),),(art(),))
    assert x.plan.execute_reentry is False
    assert x.invalidation_signals[0].source_kind=="evidence_source_authority_loss"
    assert not hasattr(x,"execution_license") and not hasattr(x,"epsilon")
