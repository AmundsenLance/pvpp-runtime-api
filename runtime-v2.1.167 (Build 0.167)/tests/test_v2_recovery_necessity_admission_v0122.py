from dataclasses import replace
from pvpp_runtime import (
    PVPPRegistry, DomainDefinition, RecoveryNecessityDefinition,
    RecoveryNecessityAdmissionRequest, admit_recovery_necessity_and_plan_reentry,
)

def reg():
    r=PVPPRegistry()
    r.register_domain(DomainDefinition('service','Service','u',0.2))
    r.register_domain(DomainDefinition('control','Control','u',0.2))
    return r

def req(r, **kw):
    x=RecoveryNecessityAdmissionRequest('rn-admit-1',r.governing_substrate_identity(),RecoveryNecessityDefinition('rn1','control','service'),'cfg-122','host','prov','new observed recovery dependency',{'ticket':'e1'})
    return replace(x,**kw)

def test_admits_explicit_relation_and_changes_governing_identity():
    r=reg(); before=r.governing_substrate_identity(); a=r.admit_recovery_necessity(req(r))
    assert a.status=='ADMITTED' and a.prior_governing_substrate_identity==before
    assert a.resulting_governing_substrate_identity!=before and 'rn1' in r.recovery_necessities
    assert any('provenance_id=prov'==n for n in r.recovery_necessities['rn1'].notes)

def test_success_plans_g_reentry():
    r=reg(); t=admit_recovery_necessity_and_plan_reentry(r,req(r))
    assert t.valid and t.invalidation_signal.invalidated_stage=='G' and t.reentry_plan.recompute_from_stage=='G'

def test_stale_governing_identity_rejected_without_mutation():
    r=reg(); a=r.admit_recovery_necessity(req(r,expected_governing_substrate_identity='stale'))
    assert a.status=='REJECTED' and not r.recovery_necessities

def test_unknown_support_domain_rejected_atomically():
    r=reg(); bad=RecoveryNecessityDefinition('rn1','missing','service')
    a=r.admit_recovery_necessity(req(r,relation=bad))
    assert a.status=='REJECTED' and not r.recovery_necessities

def test_self_dependency_rejected():
    r=reg(); bad=RecoveryNecessityDefinition('rn1','service','service')
    assert r.admit_recovery_necessity(req(r,relation=bad)).status=='REJECTED'

def test_duplicate_relation_rejected_without_second_change():
    r=reg(); assert r.admit_recovery_necessity(req(r)).status=='ADMITTED'; ident=r.governing_substrate_identity()
    second=req(r,admission_id='rn-admit-2')
    a=r.admit_recovery_necessity(second)
    assert a.status=='REJECTED' and r.governing_substrate_identity()==ident

def test_missing_provenance_rejected():
    r=reg(); assert r.admit_recovery_necessity(req(r,provenance_id='')).status=='REJECTED'

def test_rejected_admission_creates_no_reentry_or_execution_authority():
    r=reg(); t=admit_recovery_necessity_and_plan_reentry(r,req(r,provenance_id=''))
    assert not t.valid and t.invalidation_signal is None and t.reentry_plan is None
    assert not hasattr(t,'epsilon') and not hasattr(t,'execution_result')
