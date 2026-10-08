import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_concurrent_recovery_execution_binding_v055 import build,state,request


def setup_case():
    rt,w,ts=build(); original=rt.evaluate_canonical_decision_cycle(state(),request())
    sig=GovernanceInvalidationSignal('c91','Constraints','constraint evidence changed','evidence')
    plan=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    payload=ConstraintsReusablePiArtifact(original.pi_construction,original.regime_assessment,original.governing_assessment,original.joint_recovery_feasibility)
    arts={'PPP':original.pressure_field,'Phi':original.pressure_field,'H':original.horizon_assessment,'G':original.governing_assessment,'R':original.regime_assessment,'Graph/Seed':original.graph_assessment,'Pi':payload,'Pi Completeness':original.pi_completeness}
    b=GovernanceReusableArtifactBundle('b91','c91','s91','cfg91',tuple((s,arts[s]) for s in plan.reusable_upstream_stages))
    ba=validate_reusable_artifact_bundle(plan,b,expected_cycle_id='c91',expected_initial_state_id='s91',expected_configuration_id='cfg91')
    return rt,w,ts,original,plan,b,ba

def test_v091_constraints_reentry_recomputes_downstream_only():
    rt,w,ts,o,p,b,ba=setup_case(); c0=len(w.constraint_calls); q0=len(w.q_calls)
    x=execute_constraints_reentry(rt,p,b,ba,state(),request())
    assert x.valid and x.status=='reentry_pass_completed'
    assert x.recomputed_stage_ids==('Constraints','Domain Framing','Adequacy','Sigma')
    assert x.decision.selection.selected_policy_id==o.selection.selected_policy_id
    assert len(w.constraint_calls)>c0 and len(w.q_calls)>q0 and len(ts.handoffs)==0

def test_v091_reuses_exact_bound_pi_without_joint_recovery_rebinding():
    rt,w,ts,o,p,b,ba=setup_case(); x=execute_constraints_reentry(rt,p,b,ba,state(),request())
    assert x.decision.pi_construction is o.pi_construction
    assert x.decision.joint_recovery_feasibility is o.joint_recovery_feasibility

def test_v091_wrong_boundary_fails_before_world_work():
    rt,w,ts,o,p,b,ba=setup_case(); bad=GovernanceReentryPlan(True,'Sigma',p.reusable_upstream_stages,p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids)
    c=len(w.constraint_calls); q=len(w.q_calls); x=execute_constraints_reentry(rt,bad,b,ba,state(),request())
    assert not x.valid and (len(w.constraint_calls),len(w.q_calls))==(c,q)

def test_v091_invalid_bundle_assessment_fails_closed():
    rt,w,ts,o,p,b,ba=setup_case(); bad=GovernanceReusableArtifactBundleAssessment(False,b.bundle_id,'c91','s91','cfg91',p.reusable_upstream_stages,('bad',))
    assert not execute_constraints_reentry(rt,p,b,bad,state(),request()).valid

def test_v091_wrong_pi_payload_type_fails_closed():
    rt,w,ts,o,p,b,ba=setup_case(); arts=tuple((s,object() if s=='Pi' else a) for s,a in b.stage_artifacts); b2=GovernanceReusableArtifactBundle('b91','c91','s91','cfg91',arts)
    x=execute_constraints_reentry(rt,p,b2,ba,state(),request()); assert not x.valid and any('Pi artifact has wrong type' in v for v in x.violations)

def test_v091_stops_before_epsilon_and_layer1():
    rt,w,ts,o,p,b,ba=setup_case(); x=execute_constraints_reentry(rt,p,b,ba,state(),request())
    assert 'epsilon' not in x.recomputed_stage_ids and len(ts.handoffs)==0

def test_v091_preserves_reused_stage_identity_list():
    rt,w,ts,o,p,b,ba=setup_case(); x=execute_constraints_reentry(rt,p,b,ba,state(),request()); assert x.reused_stage_ids==p.reusable_upstream_stages
