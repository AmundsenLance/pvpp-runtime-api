from pvpp_runtime import SecurityEvidenceObservation, assess_security_evidence_observation

def obs(**kw):
    d=dict(observation_id='o1',fact_id='f1',value=True,source_id='sensor:A',provenance_id='p1',observed_at=1.0,authority_status='authoritative',confidence=.9,distortion_risk='low')
    d.update(kw); return SecurityEvidenceObservation(**d)

def test_authoritative_evidence_is_epistemically_usable():
    a=assess_security_evidence_observation(obs()); assert a.valid and a.usable_as_governance_evidence and not a.requires_independent_confirmation

def test_provisional_requires_confirmation_and_is_not_self_authorizing():
    a=assess_security_evidence_observation(obs(authority_status='provisional')); assert a.valid and not a.usable_as_governance_evidence and a.requires_independent_confirmation

def test_confirmation_ids_do_not_self_promote_provisional_evidence():
    a=assess_security_evidence_observation(obs(authority_status='provisional',independent_confirmation_ids=('o2',))); assert a.valid and not a.usable_as_governance_evidence and not a.requires_independent_confirmation

def test_disputed_and_untrusted_retained_but_not_usable():
    for s in ('disputed','untrusted'):
        a=assess_security_evidence_observation(obs(authority_status=s)); assert a.valid and not a.usable_as_governance_evidence

def test_confidence_and_distortion_are_validated():
    assert not assess_security_evidence_observation(obs(confidence=1.1)).valid
    assert not assess_security_evidence_observation(obs(distortion_risk='magic')).valid

def test_identity_and_provenance_required():
    assert not assess_security_evidence_observation(obs(source_id='')).valid
    assert not assess_security_evidence_observation(obs(provenance_id='')).valid

def test_confirmation_identity_must_be_unique_and_nonempty():
    assert not assess_security_evidence_observation(obs(independent_confirmation_ids=('x','x'))).valid
    assert not assess_security_evidence_observation(obs(independent_confirmation_ids=('',))).valid

def test_assessment_creates_no_governance_or_execution_authority():
    a=assess_security_evidence_observation(obs())
    for name in ('reentry_plan','sigma','epsilon','execution_license','layer1_transition'):
        assert not hasattr(a,name)
