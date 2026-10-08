import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def rt():
    reg=PVPPRegistry()
    for d in ('G1','G2','N1','N2'):
        reg.register_domain(DomainDefinition(d,d,0))
    reg.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(reg,W())

def ordered(*pairs):
    runtime=rt()
    for pid,idx in pairs:
        runtime.registry.register_sigma_order(SigmaOrderDefinition(pid,idx))
    return runtime

def ev(pid,g1,g2,n1,n2):
    return PolicySetEvaluation(pid,(),True,True,{'G1':g1,'G2':g2,'N1':n1,'N2':n2})

def test_stage1_uses_governing_domains_only_and_stage2_refines_globally():
    a=ev('A',10,6,8,8)
    b=ev('B',10,6,6,7)
    c=ev('C',8,4,100,100)
    s=rt().evaluate_sigma_standard((a,b,c),('G1','G2'))
    assert set(s.stage1.survivor_policy_ids)=={'A','B'}
    assert s.stage2.survivor_policy_ids==('A',)
    assert s.final_policy_ids==('A',)
    assert s.selected_policy_id=='A'

def test_non_governing_advantage_cannot_rescue_policy_eliminated_at_stage1():
    strong_g=ev('strong_g',10,10,0,0)
    weak_g=ev('weak_g',9,9,1000,1000)
    s=rt().evaluate_sigma_standard((strong_g,weak_g),('G1','G2'))
    assert s.stage1.survivor_policy_ids==('strong_g',)
    assert s.stage2.survivor_policy_ids==('strong_g',)

def test_crossing_governing_policies_remain_in_a1_and_may_remain_set_valued():
    a=ev('A',10,6,8,4)
    b=ev('B',6,10,4,8)
    s=ordered(('A',20),('B',10)).evaluate_sigma_standard((a,b),('G1','G2'))
    assert set(s.stage1.survivor_policy_ids)=={'A','B'}
    assert set(s.stage2.survivor_policy_ids)=={'A','B'}
    assert s.selected_policy_id=='B'
    assert s.selected_order_index==10

def test_governing_equivalent_global_equal_policies_remain_set_valued():
    a=ev('A',10,10,5,5)
    b=ev('B',10,10,5,5)
    s=ordered(('A',2),('B',1)).evaluate_sigma_standard((a,b),('G1','G2'))
    assert set(s.final_policy_ids)=={'A','B'}
    assert s.selected_policy_id=='B'

def test_candidate_order_never_breaks_a2_tie():
    a=ev('A',10,6,8,4)
    b=ev('B',6,10,4,8)
    x=ordered(('A',7),('B',3)).evaluate_sigma_standard((a,b),('G1','G2'))
    y=ordered(('A',7),('B',3)).evaluate_sigma_standard((b,a),('G1','G2'))
    assert set(x.final_policy_ids)==set(y.final_policy_ids)=={'A','B'}
    assert x.selected_policy_id==y.selected_policy_id=='B'

def test_misaligned_consequence_representations_are_rejected():
    a=ev('A',10,10,5,5)
    b=PolicySetEvaluation('B',(),True,True,{'G1':10,'G2':10,'N1':5})
    try:
        rt().evaluate_sigma_standard((a,b),('G1','G2'))
        assert False
    except ValueError as e:
        assert 'aligned' in str(e)

def test_missing_governing_coordinate_is_rejected():
    a=PolicySetEvaluation('A',(),True,True,{'G1':10,'N1':5})
    try:
        rt().evaluate_sigma_standard((a,),('G1','G2'))
        assert False
    except ValueError as e:
        assert 'omits governing domains' in str(e)

def test_inadequate_policy_never_enters_standard_sigma():
    a=ev('A',10,10,5,5)
    b=PolicySetEvaluation('B',(),True,False,{'G1':100,'G2':100,'N1':100,'N2':100})
    s=rt().evaluate_sigma_standard((a,b),('G1','G2'))
    assert s.stage1.input_policy_ids==('A',)
    assert s.final_policy_ids==('A',)

def test_stage2_refines_only_within_governing_equivalence_fibers():
    a=ev('A',10,10,8,8)
    b=ev('B',10,10,6,7)
    c=ev('C',9,11,100,100)
    sig=ordered(('A',1),('C',2)).evaluate_sigma_standard((a,b,c),('G1','G2'))
    # A and B are one governing-equivalence fiber; C is crossing and separate.
    assert set(sig.stage1.survivor_policy_ids)=={'A','B','C'}
    assert set(sig.stage2.survivor_policy_ids)=={'A','C'}
