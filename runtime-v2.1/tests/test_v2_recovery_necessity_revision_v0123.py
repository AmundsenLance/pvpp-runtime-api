from dataclasses import replace
from pvpp_runtime import *

def reg():
 r=PVPPRegistry(); r.register_domain(DomainDefinition("a","A",.2)); r.register_domain(DomainDefinition("b","B",.2)); r.register_domain(DomainDefinition("c","C",.2)); r.register_recovery_necessity(RecoveryNecessityDefinition("rn","b","a","recovery support")); return r

def req(r, **kw):
 q=dict(revision_id="rev1",expected_governing_substrate_identity=r.governing_substrate_identity(),operation="replace",relation_id="rn",replacement=RecoveryNecessityDefinition("rn","c","a","replacement support"),configuration_version="cfg123",source_id="host",provenance_id="prov123",rationale="validated topology change")
 q.update(kw); return RecoveryNecessityRevisionRequest(**q)

def test_replace_is_provenance_bearing_and_changes_identity():
 r=reg(); before=r.governing_substrate_identity(); a=r.revise_recovery_necessity(req(r)); assert a.status=="REVISED"; assert a.resulting_governing_substrate_identity!=before; assert r.recovery_necessities["rn"].support_domain_id=="c"; assert any("prov123" in n for n in r.recovery_necessities["rn"].notes)

def test_remove_is_atomic_and_removes_relation():
 r=reg(); a=r.revise_recovery_necessity(req(r,operation="remove",replacement=None)); assert a.status=="REVISED"; assert "rn" not in r.recovery_necessities

def test_stale_identity_rejected_without_mutation():
 r=reg(); old=r.recovery_necessities["rn"]; a=r.revise_recovery_necessity(req(r,expected_governing_substrate_identity="stale")); assert a.status=="REJECTED"; assert r.recovery_necessities["rn"]==old

def test_replace_must_preserve_relation_identity():
 r=reg(); bad=RecoveryNecessityDefinition("other","c","a","x"); a=r.revise_recovery_necessity(req(r,replacement=bad)); assert a.status=="REJECTED"; assert "rn" in r.recovery_necessities and "other" not in r.recovery_necessities

def test_unknown_relation_rejected():
 r=reg(); a=r.revise_recovery_necessity(req(r,relation_id="missing",replacement=RecoveryNecessityDefinition("missing","c","a","x"))); assert a.status=="REJECTED"

def test_missing_provenance_rejected():
 r=reg(); a=r.revise_recovery_necessity(req(r,provenance_id="")); assert a.status=="REJECTED"

def test_successful_revision_plans_g_reentry():
 r=reg(); t=revise_recovery_necessity_and_plan_reentry(r,req(r)); assert t.valid; assert t.reentry_plan.recompute_from_stage=="G"; assert t.invalidation_signal.invalidated_stage=="G"

def test_rejected_revision_has_no_reentry_authority():
 r=reg(); t=revise_recovery_necessity_and_plan_reentry(r,req(r,expected_governing_substrate_identity="stale")); assert not t.valid; assert t.invalidation_signal is None; assert t.reentry_plan is None
