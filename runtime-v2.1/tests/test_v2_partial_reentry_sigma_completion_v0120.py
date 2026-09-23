import sys
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import *
from test_v2_constraints_partial_reentry_v091 import setup_case
from test_concurrent_recovery_execution_binding_v055 import state,request


def setup120():
    rt,w,ts,o,p,b,ba=setup_case()
    w.compare_constraint_violation_severity=lambda *a,**k: 0
    w.fallback_structure_profile=lambda st,pid,action_ids,governing: FallbackStructuralProfile(pid)
    return rt,w,ts,o,p,b,ba


def test_v0120_constraints_reentry_executes_canonical_terminal_sigma():
    rt,w,ts,o,p,b,ba=setup120()
    original=rt._constraint_system_from_perceived
    def no_valid(*a,**k):
        x=original(*a,**k)
        return replace(x, feasible_policy_ids=())
    rt._constraint_system_from_perceived=no_valid
    x=execute_constraints_reentry(rt,p,b,ba,state(),request())
    assert x.valid and x.status=='reentry_pass_completed'
    assert x.recomputed_stage_ids==('Constraints','Sigma')
    assert x.decision.selection.terminal_sigma is not None
    assert x.decision.domain_framing is None and x.decision.adequacy is None
    assert len(ts.handoffs)==0


def test_v0120_constraints_reentry_executes_canonical_fallback_sigma():
    rt,w,ts,o,p,b,ba=setup120()
    original=rt.evaluate_restoration_adequacy
    def none_adequate(*a,**k):
        x=original(*a,**k)
        return replace(x, adequate_policy_ids=())
    rt.evaluate_restoration_adequacy=none_adequate
    x=execute_constraints_reentry(rt,p,b,ba,state(),request())
    assert x.valid and x.status=='reentry_pass_completed'
    assert x.recomputed_stage_ids==('Constraints','Domain Framing','Adequacy','Sigma')
    assert x.decision.selection.fallback_sigma is not None
    assert x.decision.selection.terminal_sigma is None
    assert len(ts.handoffs)==0


def test_v0120_terminal_sigma_uses_existing_kernel_not_new_reentry_ranking():
    rt,w,ts,o,p,b,ba=setup120(); calls=[]
    original=rt.evaluate_sigma_terminal
    def wrapped(results): calls.append(tuple(r.policy_id for r in results)); return original(results)
    rt.evaluate_sigma_terminal=wrapped
    c0=rt._constraint_system_from_perceived
    rt._constraint_system_from_perceived=lambda *a,**k: replace(c0(*a,**k),feasible_policy_ids=())
    x=execute_constraints_reentry(rt,p,b,ba,state(),request())
    assert x.valid and len(calls)==1 and x.decision.selection.terminal_sigma is not None


def test_v0120_fallback_sigma_uses_existing_kernel_not_new_reentry_ranking():
    rt,w,ts,o,p,b,ba=setup120(); calls=[]
    original_sigma=rt.evaluate_sigma_fallback
    rt.evaluate_sigma_fallback=lambda *a,**k: (calls.append(True) or original_sigma(*a,**k))
    original_a=rt.evaluate_restoration_adequacy
    rt.evaluate_restoration_adequacy=lambda *a,**k: replace(original_a(*a,**k),adequate_policy_ids=())
    x=execute_constraints_reentry(rt,p,b,ba,state(),request())
    assert x.valid and calls==[True] and x.decision.selection.fallback_sigma is not None


def test_v0120_terminal_continuation_still_stops_before_epsilon():
    rt,w,ts,o,p,b,ba=setup120(); c0=rt._constraint_system_from_perceived
    rt._constraint_system_from_perceived=lambda *a,**k: replace(c0(*a,**k),feasible_policy_ids=())
    x=execute_constraints_reentry(rt,p,b,ba,state(),request())
    assert 'epsilon' not in x.recomputed_stage_ids and len(ts.handoffs)==0


def test_v0120_fallback_continuation_still_stops_before_epsilon():
    rt,w,ts,o,p,b,ba=setup120(); a0=rt.evaluate_restoration_adequacy
    rt.evaluate_restoration_adequacy=lambda *a,**k: replace(a0(*a,**k),adequate_policy_ids=())
    x=execute_constraints_reentry(rt,p,b,ba,state(),request())
    assert 'epsilon' not in x.recomputed_stage_ids and len(ts.handoffs)==0
