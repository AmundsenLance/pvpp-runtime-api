import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_integrated_canonical_cycle_v041 import build, req, actual


def plan(stage):
    sig=GovernanceInvalidationSignal('s-'+stage,stage,'changed fact','state',('ev',),('artifact',))
    a=assess_governance_reentry((sig,))
    return plan_governance_reentry(a,(sig,))


def test_ppp_reentry_executes_one_governance_pass_and_stops_before_epsilon():
    rt,w,t=build()
    out=execute_governance_reentry(rt,plan('PPP'),actual(),req())
    assert out.valid and out.status=='reentry_pass_completed'
    assert out.decision.stopped_at=='Sigma'
    assert out.recomputed_stage_ids[0]=='PPP' and out.recomputed_stage_ids[-1]=='Sigma'
    assert t.calls==0 and w.map_calls==1


def test_ppp_reentry_has_no_reused_upstream_stages():
    rt,_,_=build(); out=execute_governance_reentry(rt,plan('PPP'),actual(),req())
    assert out.reused_stage_ids==()


def test_later_stage_plan_fails_visible_instead_of_silently_restarting_at_ppp():
    rt,w,t=build(); p=plan('Sigma')
    out=execute_governance_reentry(rt,p,actual(),req())
    assert not out.valid and out.status=='partial_stage_reentry_not_yet_supported'
    assert 'Adequacy' in out.reused_stage_ids
    assert w.map_calls==0 and t.calls==0


def test_no_reentry_plan_executes_nothing():
    rt,w,t=build()
    a=GovernanceReentryAssessment(True,(),(),None,False,(),())
    p=plan_governance_reentry(a,())
    out=execute_governance_reentry(rt,p,actual(),req())
    assert out.valid and out.status=='no_reentry_required'
    assert out.decision is None and w.map_calls==0 and t.calls==0


def test_invalid_plan_fails_before_operator_execution():
    rt,w,t=build()
    p=GovernanceReentryPlan(False,'PPP',(),CANONICAL_REENTRY_STAGE_ORDER,(),(),False,('bad',),())
    out=execute_governance_reentry(rt,p,actual(),req())
    assert not out.valid and out.status=='invalid_reentry_plan'
    assert w.map_calls==0 and t.calls==0


def test_executor_rejects_source_plan_that_claims_execution_already_enabled():
    rt,w,t=build(); p=plan('PPP')
    p=GovernanceReentryPlan(p.valid,p.recompute_from_stage,p.reusable_upstream_stages,p.nonreusable_stages,p.signal_ids,p.invalidated_artifact_ids,True,p.violations,p.notes)
    out=execute_governance_reentry(rt,p,actual(),req())
    assert not out.valid and w.map_calls==0 and t.calls==0
