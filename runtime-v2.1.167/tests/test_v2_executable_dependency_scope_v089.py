import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_concurrent_recovery_execution_binding_v055 import build,state,request


def raw_jr_plan():
    sig=GovernanceInvalidationSignal('jr-change','Joint Recovery Feasibility','capacity authority changed','capacity',(),('jr-artifact',))
    return plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))


def test_v089_joint_recovery_scope_invalidates_constraints_lineage():
    p=apply_executable_dependency_scope(raw_jr_plan())
    assert p.recompute_from_stage=='Joint Recovery Feasibility'
    assert p.reusable_upstream_stages == ('PPP','Phi','H','G','R','Graph/Seed','Pi','Pi Completeness')
    assert p.nonreusable_stages == ('Joint Recovery Feasibility','Constraints','Domain Framing','Adequacy','Sigma','epsilon')


def test_v089_repaired_scope_passes_existing_joint_recovery_readiness_gate():
    rt,w,ts=build(); cycle=rt.evaluate_canonical_decision_cycle(state(),request())
    a=assess_joint_recovery_reentry_readiness(apply_executable_dependency_scope(raw_jr_plan()),cycle)
    assert a.ready and a.dependency_scope_sufficient and a.preserved_pre_binding_pi


def test_v089_repair_is_decision_only():
    rt,w,ts=build(); cycle=rt.evaluate_canonical_decision_cycle(state(),request())
    cc=len(w.constraint_calls); qc=len(w.q_calls); hc=len(ts.handoffs)
    p=apply_executable_dependency_scope(raw_jr_plan())
    assert not p.execute_reentry
    assert (len(w.constraint_calls),len(w.q_calls),len(ts.handoffs))==(cc,qc,hc)


def test_v089_non_joint_recovery_plan_is_unchanged():
    sig=GovernanceInvalidationSignal('s','Sigma','selection changed','selection')
    p=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    assert apply_executable_dependency_scope(p) is p


def test_v089_invalid_plan_is_not_upgraded():
    p=GovernanceReentryPlan(False,'Joint Recovery Feasibility',(),(),(),(),False,('bad',),())
    assert apply_executable_dependency_scope(p) is p


def test_v089_repair_preserves_signal_and_artifact_identity():
    p0=raw_jr_plan(); p=apply_executable_dependency_scope(p0)
    assert p.signal_ids==p0.signal_ids and p.invalidated_artifact_ids==p0.invalidated_artifact_ids


def test_v089_repair_does_not_claim_pi_itself_nonreusable():
    p=apply_executable_dependency_scope(raw_jr_plan())
    assert 'Pi' in p.reusable_upstream_stages
    assert 'Pi' not in p.nonreusable_stages
    assert any('binding can change Pi before Constraints' in n for n in p.notes)
