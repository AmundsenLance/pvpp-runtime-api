from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
import pytest
from pvpp_runtime.supervision import *

def reg(**kw):
 d=dict(source_registration_id='sr1',source_id='s1',evidence_roles=('observation',),fact_kinds=('reachability',),subject_scope=('net',),configuration_scope=('cfg',),permitted_uses=('governance',),attestation_method='test',valid_from='2026-01-01',valid_until=None,status='current',registration_authority='test',version=1); d.update(kw); return SourceRegistration(**d)
def obs(**kw):
 d=dict(observation_id='o1',source_id='s1',fact_kind='reachability',fact_id='route',subject_id='net',configuration_id='cfg',value=True,confidence=1.0,effective_at='2026-10-01T10:00:00',observed_at='2026-10-01T10:00:01',received_at='2026-10-01T10:00:02',payload={}); d.update(kw); return ExternalObservation(**d)
def svc(): return ObservationService(trusted_store(':memory:'))
def test_unregistered_high_confidence_retained_not_admitted():
 s=svc(); o=obs(); s.submit_observation(o); a=s.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00'); assert not a.authoritative and a.disposition=='retained_noncurrent'; assert s.commit_admission_change(o,a,committed_at='2026-10-02T10:00:00+00:00') is None
def test_scope_and_revocation_fail_closed():
 s=svc(); register_test_source(s, reg(subject_scope=('other',))); o=obs(); s.submit_observation(o); assert not s.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00').applicable
 s2=svc(); register_test_source(s2, reg(status='revoked')); o=obs(); s2.submit_observation(o); assert not s2.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00').authoritative
def test_exact_redelivery_idempotent_and_conflicting_reuse_rejected():
 s=svc(); o=obs(); s.submit_observation(o); s.submit_observation(o); assert s.observation_count()==1
 with pytest.raises(ConcurrencyConflict): s.submit_observation(obs(value=False))
def test_admission_creates_current_view_and_change():
 s=svc(); register_test_source(s, reg()); o=obs(); s.submit_observation(o); a=s.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00'); ch=s.commit_admission_change(o,a,committed_at='2026-10-02T10:00:00+00:00'); assert ch.new_view_version==1; assert s.read_current_fact_view(configuration_id='cfg',subject_id='net',fact_kind='reachability',fact_id='route').value is True
def test_older_effective_time_arriving_later_does_not_win():
 s=svc(); register_test_source(s, reg()); o=obs(); a=s.assess_observation(s.submit_observation(o),assessed_at='2026-10-02T10:00:00+00:00'); s.commit_admission_change(o,a,committed_at='2026-10-02T10:00:00+00:00')
 old=obs(observation_id='o2',value=False,effective_at='2026-09-30T10:00:00',received_at='2026-10-01T11:00:00'); s.submit_observation(old); a2=s.assess_observation(old,assessed_at='2026-10-02T10:00:00+00:00'); assert s.commit_admission_change(old,a2,committed_at='2026-10-02T10:00:00+00:00') is None; assert s.read_current_fact_view(configuration_id='cfg',subject_id='net',fact_kind='reachability',fact_id='route').value is True
def test_equal_time_contradiction_becomes_unresolved():
 s=svc(); register_test_source(s, reg()); o=obs(); s.submit_observation(o); s.commit_admission_change(o,s.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00'),committed_at='2026-10-02T10:00:00+00:00')
 c=obs(observation_id='o2',value=False); s.submit_observation(c); ch=s.commit_admission_change(c,s.assess_observation(c,assessed_at='2026-10-02T10:00:00+00:00'),committed_at='2026-10-02T10:00:00+00:00'); v=s.read_current_fact_view(configuration_id='cfg',subject_id='net',fact_kind='reachability',fact_id='route'); assert ch and v.state=='unresolved' and v.value is None
def test_abort_payload_cannot_become_governance_posture():
 s=svc(); register_test_source(s, reg()); o=obs(payload={'instruction':'abort now'}); s.submit_observation(o); ch=s.commit_admission_change(o,s.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00'),committed_at='2026-10-02T10:00:00+00:00'); assert not hasattr(ch,'continuation_posture') and not hasattr(ch,'abort')
def test_source_registration_fact_kind_and_use_enforced():
 s=svc(); register_test_source(s, reg(fact_kinds=('capability',),permitted_uses=('audit',))); o=obs(); s.submit_observation(o); a=s.assess_observation(o,assessed_at='2026-10-02T10:00:00+00:00'); assert not a.applicable and not a.permitted
