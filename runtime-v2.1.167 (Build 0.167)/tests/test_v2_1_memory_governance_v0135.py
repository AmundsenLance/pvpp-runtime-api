from pvpp_runtime import (
    InformationTemporalProvenance, InformationGovernanceMetadata,
    RetrievalQualityMetadata, MemoryStateReference, MemoryRetrievalRequest,
    MemoryRetrievalPackage, ActualPersistentStateEnvelope, PVPPRegistry, PVPPRuntime,
    ActionDefinition,
)

class W: pass

def rt():
    r=PVPPRegistry(); r.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(r, W())

def req():
    m=MemoryStateReference('a','m1',10.0,{})
    return MemoryRetrievalRequest('a',m,current_time=11.0)

def pkg(gov=None, quality=None):
    return MemoryRetrievalPackage('a','r1','m1',11.0,{'fact':'x'},quality or RetrievalQualityMetadata(), governance=gov)

def actual(): return ActualPersistentStateEnvelope('a','s1',11.0,{}, {}, {}, {})

def test_current_disposition_can_be_current_positive_evidence():
    a=rt().validate_information_governance_metadata(InformationGovernanceMetadata(disposition='current'))
    assert a.valid and a.usable_as_current_positive_evidence

def test_rejected_disposition_is_preserved_not_resurrected():
    a=rt().validate_information_governance_metadata(InformationGovernanceMetadata(disposition='rejected'))
    assert a.valid and not a.usable_as_current_positive_evidence

def test_superseded_disposition_is_preserved_not_resurrected():
    a=rt().validate_information_governance_metadata(InformationGovernanceMetadata(disposition='superseded'))
    assert a.valid and not a.usable_as_current_positive_evidence

def test_prohibited_disposition_is_preserved_not_resurrected():
    a=rt().validate_information_governance_metadata(InformationGovernanceMetadata(disposition='prohibited_for_use'))
    assert a.valid and not a.usable_as_current_positive_evidence

def test_historically_valid_noncurrent_is_distinct():
    a=rt().validate_information_governance_metadata(InformationGovernanceMetadata(disposition='historically_valid_noncurrent'))
    assert a.valid and a.disposition=='historically_valid_noncurrent' and not a.usable_as_current_positive_evidence

def test_unresolved_and_contradicted_remain_noncurrent_positive():
    for d in ('unresolved','contradicted','defective'):
        a=rt().validate_information_governance_metadata(InformationGovernanceMetadata(disposition=d))
        assert a.valid and not a.usable_as_current_positive_evidence

def test_unknown_disposition_fails_validation():
    a=rt().validate_information_governance_metadata(InformationGovernanceMetadata(disposition='trusted'))
    assert not a.valid

def test_quality_does_not_create_authority():
    g=InformationGovernanceMetadata(disposition='current',source_authority=None)
    p=pkg(g, RetrievalQualityMetadata(confidence=1.0, corroboration='strong', relevance_scope='objective-x'))
    assert rt().validate_memory_retrieval_package(req(),p,actual()) == ()
    assert p.governance.source_authority is None

def test_relevance_does_not_create_permitted_use():
    g=InformationGovernanceMetadata(disposition='current',permitted_use_scope=None)
    p=pkg(g, RetrievalQualityMetadata(relevance_scope='highly-relevant'))
    assert rt().validate_memory_retrieval_package(req(),p,actual()) == ()
    assert p.governance.permitted_use_scope is None

def test_authority_and_permitted_use_are_independent_fields():
    g=InformationGovernanceMetadata(source_authority='policy-owner', permitted_use_scope=('audit',), disposition='current')
    assert g.source_authority=='policy-owner' and g.permitted_use_scope==('audit',)

def test_permitted_use_can_differ_by_scope_without_changing_content():
    g1=InformationGovernanceMetadata(permitted_use_scope=('objective-a',),disposition='current')
    g2=InformationGovernanceMetadata(permitted_use_scope=('objective-b',),disposition='current')
    p1=pkg(g1); p2=pkg(g2)
    assert p1.content == p2.content and p1.governance.permitted_use_scope != p2.governance.permitted_use_scope

def test_temporal_provenance_preserves_valid_and_knowledge_time():
    tp=InformationTemporalProvenance(valid_time=5.0,record_or_knowledge_time=9.0)
    g=InformationGovernanceMetadata(disposition='historically_valid_noncurrent',temporal_provenance=tp)
    assert g.temporal_provenance.valid_time==5.0 and g.temporal_provenance.record_or_knowledge_time==9.0

def test_temporal_provenance_not_mandatory_when_immaterial():
    a=rt().validate_information_governance_metadata(InformationGovernanceMetadata(disposition='current'))
    assert a.valid

def test_authorized_surfaces_must_be_explicit_nonempty_strings():
    a=rt().validate_information_governance_metadata(InformationGovernanceMetadata(authorized_surfaces=('perception',''), disposition='current'))
    assert not a.valid

def test_legacy_retrieval_without_governance_remains_compatible():
    assert rt().validate_memory_retrieval_package(req(),pkg(None),actual()) == ()

def test_governance_is_carried_with_retrieval_package():
    g=InformationGovernanceMetadata(source_authority='owner', applicability_scope='case-1', permitted_use_scope='perception', disposition='current', source_version='v7', provenance='src')
    p=pkg(g)
    assert p.governance is g
    assert rt().validate_memory_retrieval_package(req(),p,actual()) == ()
