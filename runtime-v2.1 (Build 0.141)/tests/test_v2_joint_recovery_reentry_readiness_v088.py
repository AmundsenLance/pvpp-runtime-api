import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_concurrent_recovery_execution_binding_v055 import build,state,request


def jr_plan():
    sig=GovernanceInvalidationSignal('jr-change','Joint Recovery Feasibility','capacity authority changed','capacity',(),('jr-artifact',))
    a=assess_governance_reentry((sig,))
    return plan_governance_reentry(a,(sig,))


def test_v088_cycle_preserves_pre_binding_pi_before_joint_recovery_action_binding():
    rt,w,ts=build(); out=rt.evaluate_canonical_decision_cycle(state(),request())
    pre=out.pi_before_joint_recovery_binding
    assert pre is not None and pre.policy_space is not None
    before={c.id:c.action_ids for c in pre.policy_space.candidates}
    after={c.id:c.action_ids for c in out.pi_construction.policy_space.candidates}
    assert before['graph:teach']==('teach_complete',)
    assert after['graph:teach']==('crop_maintain','teach_complete')


def test_v088_pre_binding_pi_is_not_mutated_by_binding():
    rt,w,ts=build(); out=rt.evaluate_canonical_decision_cycle(state(),request())
    assert out.pi_before_joint_recovery_binding is not out.pi_construction
    assert all('joint_recovery_bound' not in c.metadata for c in out.pi_before_joint_recovery_binding.policy_space.candidates)


def test_v088_current_joint_recovery_plan_is_not_ready_because_constraints_are_marked_reusable():
    rt,w,ts=build(); out=rt.evaluate_canonical_decision_cycle(state(),request())
    p=jr_plan(); a=assess_joint_recovery_reentry_readiness(p,out)
    assert not a.ready
    assert a.preserved_pre_binding_pi
    assert not a.dependency_scope_sufficient
    assert any('Constraints' in v for v in a.violations)


def test_v088_readiness_audit_executes_no_world_or_transition_work():
    rt,w,ts=build(); out=rt.evaluate_canonical_decision_cycle(state(),request())
    cc=len(w.constraint_calls); qc=len(w.q_calls); hc=len(ts.handoffs)
    assess_joint_recovery_reentry_readiness(jr_plan(),out)
    assert (len(w.constraint_calls),len(w.q_calls),len(ts.handoffs))==(cc,qc,hc)


def test_v088_wrong_boundary_fails_readiness():
    rt,w,ts=build(); out=rt.evaluate_canonical_decision_cycle(state(),request())
    sig=GovernanceInvalidationSignal('s','Sigma','selection changed','selection')
    p=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    a=assess_joint_recovery_reentry_readiness(p,out)
    assert not a.ready and any('boundary' in v for v in a.violations)


def test_v088_missing_prebinding_artifact_fails_closed():
    from dataclasses import replace
    rt,w,ts=build(); out=rt.evaluate_canonical_decision_cycle(state(),request())
    a=assess_joint_recovery_reentry_readiness(jr_plan(),replace(out,pi_before_joint_recovery_binding=None))
    assert not a.ready and not a.preserved_pre_binding_pi
