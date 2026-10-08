from pvpp_runtime import GovernanceArtifactDependency, GovernanceDependencyChange, derive_dependency_invalidations

def dep(i, artifact, stage, kind, facts):
    return GovernanceArtifactDependency(i, artifact, stage, kind, facts)
def ch(i, kind, facts, reason="changed"):
    return GovernanceDependencyChange(i, kind, facts, reason)

def test_explicit_match_derives_invalidation():
    a=derive_dependency_invalidations((dep("d1","a1","Constraints","evidence",("e1",)),),(ch("c1","evidence",("e1",)),))
    assert a.valid and len(a.invalidation_signals)==1 and a.reentry.recompute_from_stage=="Constraints"

def test_unregistered_change_does_not_infer_invalidation():
    a=derive_dependency_invalidations((dep("d1","a1","PPP","capability",("p1",)),),(ch("c1","capability",("other",)),))
    assert a.valid and not a.invalidation_signals and a.reentry.recompute_from_stage is None

def test_fact_kind_must_match_even_when_identity_text_matches():
    a=derive_dependency_invalidations((dep("d1","a1","PPP","capability",("x",)),),(ch("c1","evidence",("x",)),))
    assert not a.invalidation_signals

def test_multiple_matches_choose_earliest_stage():
    ds=(dep("d1","a1","Sigma","evidence",("x",)),dep("d2","a2","H","evidence",("x",)))
    a=derive_dependency_invalidations(ds,(ch("c1","evidence",("x",)),))
    assert a.reentry.recompute_from_stage=="H"

def test_change_provenance_flows_to_signal():
    c=GovernanceDependencyChange("c","execution","x" if False else ("x",),"feedback",("ev",),"exec","cfg")
    a=derive_dependency_invalidations((dep("d","art","epsilon","execution",("x",)),),(c,))
    s=a.invalidation_signals[0]
    assert s.execution_id=="exec" and s.configuration_id=="cfg" and s.evidence_ids==("ev",)

def test_unknown_dependency_stage_fails_closed():
    a=derive_dependency_invalidations((dep("d","a","Bogus","evidence",("x",)),),(ch("c","evidence",("x",)),))
    assert not a.valid

def test_duplicate_dependency_and_change_ids_fail_closed():
    d=dep("d","a","G","state",("x",)); c=ch("c","state",("x",))
    assert not derive_dependency_invalidations((d,d),(c,)).valid
    assert not derive_dependency_invalidations((d,),(c,c)).valid

def test_duplicate_fact_or_evidence_ids_fail_closed():
    assert not derive_dependency_invalidations((dep("d","a","G","state",("x","x")),),(ch("c","state",("x",)),)).valid
    c=GovernanceDependencyChange("c","state",("x",),"changed",("e","e"))
    assert not derive_dependency_invalidations((dep("d","a","G","state",("x",)),),(c,)).valid

def test_dependency_derivation_does_not_recompute_artifacts():
    a=derive_dependency_invalidations((dep("d","a","Pi","structure",("s",)),),(ch("c","structure",("s",)),))
    assert not hasattr(a,"recomputed_cycle") and not hasattr(a,"replacement_artifact")
