import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_concurrent_recovery_execution_binding_v055 import build,state,request


def setup_case():
    rt,w,ts=build(); original=rt.evaluate_canonical_decision_cycle(state(),request())
    sig=GovernanceInvalidationSignal('jr90','Joint Recovery Feasibility','capacity changed','capacity')
    plan=apply_executable_dependency_scope(plan_governance_reentry(assess_governance_reentry((sig,)),(sig,)))
    arts={
      'PPP':original.pressure_field,'Phi':original.pressure_field,'H':original.horizon_assessment,
      'G':original.governing_assessment,'R':original.regime_assessment,'Graph/Seed':original.graph_assessment,
      'Pi':original.pi_before_joint_recovery_binding,'Pi Completeness':original.pi_completeness,
    }
    b=GovernanceReusableArtifactBundle('b90','c90','s90','cfg90',tuple((s,arts[s]) for s in plan.reusable_upstream_stages))
    ba=validate_reusable_artifact_bundle(plan,b,expected_cycle_id='c90',expected_initial_state_id='s90',expected_configuration_id='cfg90')
    return rt,w,ts,original,plan,b,ba

def test_v090_joint_recovery_reentry_recomputes_bound_downstream_lineage_only():
    rt,w,ts,o,p,b,ba=setup_case(); c0=len(w.constraint_calls); q0=len(w.q_calls)
    x=execute_joint_recovery_reentry(rt,p,b,ba,state(),request())
    assert x.valid and x.status=='reentry_pass_completed'
    assert x.recomputed_stage_ids==('Joint Recovery Feasibility','Constraints','Domain Framing','Adequacy','Sigma')
    assert x.decision.selection.selected_policy_id==o.selection.selected_policy_id
    assert len(w.constraint_calls)>c0 and len(w.q_calls)>q0 and len(ts.handoffs)==0

def test_v090_uses_preserved_prebinding_pi_then_rebinds_mandatory_actions():
    rt,w,ts,o,p,b,ba=setup_case(); x=execute_joint_recovery_reentry(rt,p,b,ba,state(),request())
    assert x.decision.pi_before_joint_recovery_binding is o.pi_before_joint_recovery_binding
    assert x.decision.joint_recovery_execution_binding.mandatory_action_ids==('crop_maintain','teach_complete')
    for c in x.decision.pi_construction.policy_space.candidates:
        assert 'crop_maintain' in c.action_ids and 'teach_complete' in c.action_ids

def test_v090_stops_before_epsilon_and_layer1():
    rt,w,ts,o,p,b,ba=setup_case(); x=execute_joint_recovery_reentry(rt,p,b,ba,state(),request())
    assert 'epsilon' not in x.recomputed_stage_ids and len(ts.handoffs)==0

def test_v090_wrong_boundary_fails_before_world_work():
    rt,w,ts,o,p,b,ba=setup_case(); bad=GovernanceReentryPlan(True,'Sigma',p.reusable_upstream_stages,p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids)
    c=len(w.constraint_calls); q=len(w.q_calls)
    x=execute_joint_recovery_reentry(rt,bad,b,ba,state(),request())
    assert not x.valid and (len(w.constraint_calls),len(w.q_calls))==(c,q)

def test_v090_invalid_bundle_assessment_fails_closed():
    rt,w,ts,o,p,b,ba=setup_case(); bad=GovernanceReusableArtifactBundleAssessment(False,b.bundle_id,'c90','s90','cfg90',p.reusable_upstream_stages,('bad',))
    x=execute_joint_recovery_reentry(rt,p,b,bad,state(),request()); assert not x.valid

def test_v090_missing_prebinding_pi_fails_closed():
    rt,w,ts,o,p,b,ba=setup_case(); arts=tuple((s,a) for s,a in b.stage_artifacts if s!='Pi')
    b2=GovernanceReusableArtifactBundle('b2','c90','s90','cfg90',arts)
    # deliberately pair with original valid assessment to exercise executor completeness guard
    x=execute_joint_recovery_reentry(rt,p,b2,ba,state(),request()); assert not x.valid
