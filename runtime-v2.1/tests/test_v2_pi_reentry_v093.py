import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_concurrent_recovery_execution_binding_v055 import build,state,request


def setup_case():
    rt,w,ts=build(); req=request(); original=rt.evaluate_canonical_decision_cycle(state(),req)
    sig=GovernanceInvalidationSignal('pi93','Pi','candidate construction inputs changed','structure')
    plan=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    arts={'PPP':original.pressure_field,'Phi':original.pressure_field,'H':original.horizon_assessment,'G':original.governing_assessment,'R':original.regime_assessment,'Graph/Seed':original.graph_assessment}
    b=GovernanceReusableArtifactBundle('b93','c93','s93','cfg93',tuple((s,arts[s]) for s in plan.reusable_upstream_stages))
    ba=validate_reusable_artifact_bundle(plan,b,expected_cycle_id='c93',expected_initial_state_id='s93',expected_configuration_id='cfg93')
    inputs=PiReusableConstructionInputs(req.materially_required_policy_class_ids,req.pi_config)
    return rt,w,ts,req,original,plan,b,ba,inputs

def test_v093_pi_reentry_reconstructs_pi_then_downstream():
    rt,w,ts,req,o,p,b,ba,i=setup_case(); c0=len(w.constraint_calls); q0=len(w.q_calls)
    x=execute_pi_reentry(rt,p,b,ba,state(),req,i)
    assert x.valid and x.status=='reentry_pass_completed'
    assert x.recomputed_stage_ids==('Pi','Pi Completeness','Joint Recovery Feasibility','Constraints','Domain Framing','Adequacy','Sigma')
    assert x.decision.pi_before_joint_recovery_binding.emitted_candidate_ids==o.pi_before_joint_recovery_binding.emitted_candidate_ids
    assert len(w.constraint_calls)>c0 and len(w.q_calls)>q0 and len(ts.handoffs)==0

def test_v093_pi_inputs_must_match_request_authority():
    rt,w,ts,req,o,p,b,ba,i=setup_case(); bad=PiReusableConstructionInputs(('different',),req.pi_config)
    x=execute_pi_reentry(rt,p,b,ba,state(),req,bad)
    assert not x.valid and any('material-requirement' in v for v in x.violations)

def test_v093_pi_config_must_match_request():
    rt,w,ts,req,o,p,b,ba,i=setup_case(); bad=PiReusableConstructionInputs(req.materially_required_policy_class_ids,PiConstructionConfig(7))
    x=execute_pi_reentry(rt,p,b,ba,state(),req,bad)
    assert not x.valid and any('configuration' in v for v in x.violations)

def test_v093_wrong_boundary_fails_before_world_work():
    rt,w,ts,req,o,p,b,ba,i=setup_case(); bad=GovernanceReentryPlan(True,'Pi Completeness',p.reusable_upstream_stages,p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids)
    c=len(w.constraint_calls); q=len(w.q_calls); x=execute_pi_reentry(rt,bad,b,ba,state(),req,i)
    assert not x.valid and (len(w.constraint_calls),len(w.q_calls))==(c,q)

def test_v093_invalid_bundle_fails_closed():
    rt,w,ts,req,o,p,b,ba,i=setup_case(); bad=GovernanceReusableArtifactBundleAssessment(False,b.bundle_id,'c93','s93','cfg93',p.reusable_upstream_stages,('bad',))
    assert not execute_pi_reentry(rt,p,b,bad,state(),req,i).valid

def test_v093_wrong_graph_type_fails_closed():
    rt,w,ts,req,o,p,b,ba,i=setup_case(); arts=tuple((s,object() if s=='Graph/Seed' else a) for s,a in b.stage_artifacts); b2=GovernanceReusableArtifactBundle('b93','c93','s93','cfg93',arts)
    x=execute_pi_reentry(rt,p,b2,ba,state(),req,i); assert not x.valid and any('Graph/Seed' in v for v in x.violations)

def test_v093_stops_before_epsilon_and_preserves_reuse_identity():
    rt,w,ts,req,o,p,b,ba,i=setup_case(); x=execute_pi_reentry(rt,p,b,ba,state(),req,i)
    assert 'epsilon' not in x.recomputed_stage_ids and len(ts.handoffs)==0 and x.reused_stage_ids==p.reusable_upstream_stages
