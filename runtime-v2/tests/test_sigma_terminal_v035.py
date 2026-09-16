import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ConstraintAssessment, ConstraintViolationProfile

class W:
    def project(self,s,a): return None


def rt_with(comparator):
    r=PVPPRegistry(); r.register_action(ActionDefinition('steady','s',()))
    w=W(); w.compare_constraint_violation_severity=comparator
    return PVPPRuntime(r,w)


def ca(pid, hard=(), cond=(), soft=()):
    return ConstraintAssessment(pid,False,(),ConstraintViolationProfile(tuple(hard),tuple(cond),(),tuple(soft)),'canonical_typed_constraint_profile')


def test_hard_class_dominates_any_lower_class_improvement():
    severity={'a':{'hard':2,'conditional':0,'soft':0},'b':{'hard':1,'conditional':99,'soft':99}}
    def cmp(a,pa,b,pb,cls): return (severity[a][cls]>severity[b][cls])-(severity[a][cls]<severity[b][cls])
    rt=rt_with(cmp)
    x=rt.evaluate_sigma_terminal((ca('a',('h',)),ca('b',('h',),('c',),('s',))))
    assert x.hard_survivor_policy_ids==('b',); assert x.selected_policy_id=='b'


def test_conditional_refines_only_after_hard_equivalence():
    severity={'a':{'hard':1,'conditional':3,'soft':0},'b':{'hard':1,'conditional':1,'soft':8}}
    def cmp(a,pa,b,pb,cls): return (severity[a][cls]>severity[b][cls])-(severity[a][cls]<severity[b][cls])
    x=rt_with(cmp).evaluate_sigma_terminal((ca('a',('h',),('c',)),ca('b',('h',),('c',),('s',))))
    assert x.hard_survivor_policy_ids==('a','b'); assert x.conditional_survivor_policy_ids==('b',); assert x.selected_policy_id=='b'


def test_higher_class_incomparability_cannot_be_overridden_by_lower_class():
    def cmp(a,pa,b,pb,cls):
        if cls=='hard': return None
        if cls=='conditional': return 0
        return -1 if a=='a' else (1 if b=='a' else 0)
    rt=rt_with(cmp)
    rt.registry.register_sigma_order(SigmaOrderDefinition('a',8)); rt.registry.register_sigma_order(SigmaOrderDefinition('b',2))
    x=rt.evaluate_sigma_terminal((ca('a',('h1',),soft=('s',)),ca('b',('h2',),soft=('s',))))
    assert set(x.hard_survivor_policy_ids)=={'a','b'}
    assert set(x.soft_survivor_policy_ids)=={'a','b'}
    assert x.selected_policy_id=='b'  # lower soft severity was not allowed to compensate for hard incomparability


def test_residual_tie_requires_explicit_order_index_not_candidate_order():
    rt=rt_with(lambda a,pa,b,pb,cls: 0)
    rt.registry.register_sigma_order(SigmaOrderDefinition('z',1)); rt.registry.register_sigma_order(SigmaOrderDefinition('a',9))
    x=rt.evaluate_sigma_terminal((ca('a',('h',)),ca('z',('h',))))
    assert x.selected_policy_id=='z'; assert x.selected_order_index==1


def test_missing_comparator_fails_closed():
    r=PVPPRegistry(); r.register_action(ActionDefinition('steady','s',())); rt=PVPPRuntime(r,W())
    try: rt.evaluate_sigma_terminal((ca('a',('h',)),ca('b',('h',)))); assert False
    except ValueError as e: assert 'compare_constraint_violation_severity' in str(e)


def test_bad_comparator_contract_is_rejected():
    rt=rt_with(lambda *args: 7)
    try: rt.evaluate_sigma_terminal((ca('a',('h',)),ca('b',('h',)))); assert False
    except ValueError as e: assert '-1, 0, 1, or None' in str(e)
