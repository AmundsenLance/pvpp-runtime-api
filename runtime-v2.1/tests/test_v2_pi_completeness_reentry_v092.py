import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_concurrent_recovery_execution_binding_v055 import build,state,request


def setup_case():
    rt,w,ts=build(); original=rt.evaluate_canonical_decision_cycle(state(),request())
    sig=GovernanceInvalidationSignal('pc92','Pi Completeness','coverage evidence changed','evidence')
    plan=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    arts={'PPP':original.pressure_field,'Phi':original.pressure_field,'H':original.horizon_assessment,'G':original.governing_assessment,'R':original.regime_assessment,'Graph/Seed':original.graph_assessment,'Pi':original.pi_before_joint_recovery_binding}
    b=GovernanceReusableArtifactBundle('b92','c92','s92','cfg92',tuple((s,arts[s]) for s in plan.reusable_upstream_stages))
    ba=validate_reusable_artifact_bundle(plan,b,expected_cycle_id='c92',expected_initial_state_id='s92',expected_configuration_id='cfg92')
    return rt,w,ts,original,plan,b,ba

def test_v092_completeness_is_validation_only_and_recomputes_downstream():
    rt,w,ts,o,p,b,ba=setup_case(); c0=len(w.constraint_calls); q0=len(w.q_calls)
    x=execute_pi_completeness_reentry(rt,p,b,ba,state(),request())
    assert x.valid and x.status=='reentry_pass_completed'
    assert x.recomputed_stage_ids==('Pi Completeness','Joint Recovery Feasibility','Constraints','Domain Framing','Adequacy','Sigma')
    assert x.decision.pi_before_joint_recovery_binding is o.pi_before_joint_recovery_binding
    assert x.decision.pi_completeness.candidate_ids==o.pi_completeness.candidate_ids
    assert len(w.constraint_calls)>c0 and len(w.q_calls)>q0 and len(ts.handoffs)==0

def test_v092_rebinds_joint_recovery_only_after_completeness_passes():
    rt,w,ts,o,p,b,ba=setup_case(); x=execute_pi_completeness_reentry(rt,p,b,ba,state(),request())
    assert x.decision.joint_recovery_execution_binding.mandatory_action_ids==('crop_maintain','teach_complete')
    for c in x.decision.pi_construction.policy_space.candidates:
        assert 'crop_maintain' in c.action_ids and 'teach_complete' in c.action_ids

def test_v092_standard_selection_matches_control_cycle():
    rt,w,ts,o,p,b,ba=setup_case(); x=execute_pi_completeness_reentry(rt,p,b,ba,state(),request())
    assert x.decision.selection.selected_policy_id==o.selection.selected_policy_id

def test_v092_wrong_boundary_fails_before_world_work():
    rt,w,ts,o,p,b,ba=setup_case(); bad=GovernanceReentryPlan(True,'Constraints',p.reusable_upstream_stages,p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids)
    c=len(w.constraint_calls); q=len(w.q_calls); x=execute_pi_completeness_reentry(rt,bad,b,ba,state(),request())
    assert not x.valid and (len(w.constraint_calls),len(w.q_calls))==(c,q)

def test_v092_invalid_bundle_assessment_fails_closed():
    rt,w,ts,o,p,b,ba=setup_case(); bad=GovernanceReusableArtifactBundleAssessment(False,b.bundle_id,'c92','s92','cfg92',p.reusable_upstream_stages,('bad',))
    assert not execute_pi_completeness_reentry(rt,p,b,bad,state(),request()).valid

def test_v092_wrong_pi_type_fails_closed():
    rt,w,ts,o,p,b,ba=setup_case(); arts=tuple((s,object() if s=='Pi' else a) for s,a in b.stage_artifacts); b2=GovernanceReusableArtifactBundle('b92','c92','s92','cfg92',arts)
    x=execute_pi_completeness_reentry(rt,p,b2,ba,state(),request()); assert not x.valid and any('Pi artifact has wrong type' in v for v in x.violations)

def test_v092_stops_before_epsilon_and_preserves_reuse_identity():
    rt,w,ts,o,p,b,ba=setup_case(); x=execute_pi_completeness_reentry(rt,p,b,ba,state(),request())
    assert 'epsilon' not in x.recomputed_stage_ids and len(ts.handoffs)==0 and x.reused_stage_ids==p.reusable_upstream_stages
