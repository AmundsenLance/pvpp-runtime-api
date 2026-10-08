import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_v2_sigma_partial_reentry_v086 import fixture as sigma_fixture


def orch_for(plan):
    re=GovernanceReentryAssessment(True,plan.signal_ids,(plan.recompute_from_stage,),plan.recompute_from_stage,True,(),())
    gi=EvidenceAuthorityGovernanceInvalidationAssessment(True,('ed',),('ad',),(),re,plan,(),())
    return EpistemicInvalidationOrchestrationAssessment(True,'src','prov',('ed',),(),gi,(),())


def test_dispatches_sigma_to_existing_executor():
    rt,w,t,d,p,b,ba=sigma_fixture()
    out=execute_epistemic_reentry_plan(rt,orch_for(p),bundle=b,bundle_assessment=ba)
    assert out.valid and out.status=='epistemic_reentry_dispatched'
    assert out.execution_result.recomputed_stage_ids==('Sigma',)
    assert out.execution_result.decision.selection.selected_policy_id==d.selection.selected_policy_id

def test_sigma_missing_bundle_fails_before_recomputation():
    rt,w,t,d,p,b,ba=sigma_fixture()
    out=execute_epistemic_reentry_plan(rt,orch_for(p))
    assert not out.valid and out.execution_result is None
    assert any('bundle' in v for v in out.violations)

def test_invalid_orchestration_fails_closed():
    rt,w,t,d,p,b,ba=sigma_fixture()
    bad=EpistemicInvalidationOrchestrationAssessment(False,'src','prov',(),(),None,('bad',),())
    out=execute_epistemic_reentry_plan(rt,bad,bundle=b,bundle_assessment=ba)
    assert not out.valid and out.execution_result is None

def test_no_invalidation_plan_fails_closed():
    rt,w,t,d,p,b,ba=sigma_fixture()
    gi=EvidenceAuthorityGovernanceInvalidationAssessment(True,(),(),(),GovernanceReentryAssessment(True,(),(),None,False,(),()),None,(),())
    o=EpistemicInvalidationOrchestrationAssessment(True,'src','prov',(),(),gi,(),())
    out=execute_epistemic_reentry_plan(rt,o,bundle=b,bundle_assessment=ba)
    assert not out.valid

def test_domain_framing_has_no_generic_bypass_with_incompatible_artifacts():
    rt,w,t,d,p,b,ba=sigma_fixture()
    sig=GovernanceInvalidationSignal('x','Domain Framing','evidence changed','evidence')
    plan=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    out=execute_epistemic_reentry_plan(rt,orch_for(plan),bundle=b,bundle_assessment=ba,state=actual() if 'actual' in globals() else object(),request=object())
    assert not out.valid and out.execution_result is not None and not out.execution_result.valid
    assert any('stage coverage' in v for v in out.violations)

def test_executor_rejection_is_preserved_not_overridden():
    rt,w,t,d,p,b,ba=sigma_fixture()
    badba=GovernanceReusableArtifactBundleAssessment(False,b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,ba.reusable_stage_ids,('bad',),())
    out=execute_epistemic_reentry_plan(rt,orch_for(p),bundle=b,bundle_assessment=badba)
    assert not out.valid and out.status=='epistemic_reentry_executor_rejected'
    assert out.execution_result is not None and not out.execution_result.valid

def test_dispatch_adds_no_epsilon_or_layer1_execution():
    rt,w,t,d,p,b,ba=sigma_fixture(); before=t.calls
    out=execute_epistemic_reentry_plan(rt,orch_for(p),bundle=b,bundle_assessment=ba)
    assert out.valid and out.execution_result.decision.stopped_at=='Sigma' and t.calls==before

def test_stage_identity_is_preserved_in_wrapper():
    rt,w,t,d,p,b,ba=sigma_fixture()
    out=execute_epistemic_reentry_plan(rt,orch_for(p),bundle=b,bundle_assessment=ba)
    assert out.recompute_from_stage==p.recompute_from_stage=='Sigma'
