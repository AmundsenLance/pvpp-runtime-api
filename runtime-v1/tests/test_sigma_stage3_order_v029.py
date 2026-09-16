import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection
class W:
 def perceive(self,s):return s
 def domain_value(self,s,d):return 1
 def project(self,s,a):return ActionProjection(a.id,s,True)
def rt():
 r=PVPPRegistry();r.register_domain(DomainDefinition('G1','G1',0));r.register_domain(DomainDefinition('G2','G2',0));r.register_domain(DomainDefinition('N','N',0));r.register_action(ActionDefinition('steady','steady',()))
 return PVPPRuntime(r,W())
def ev(pid,g1,g2,n):return PolicySetEvaluation(pid,(),True,True,{'G1':g1,'G2':g2,'N':n})
def test_stage3_requires_explicit_order_for_multi_policy_a2():
 runtime=rt()
 try: runtime.evaluate_sigma_standard((ev('A',10,5,5),ev('B',5,10,10)),('G1','G2'));assert False
 except ValueError as e: assert 'OrderIndex' in str(e)
def test_stage3_uses_explicit_index_not_candidate_order_or_policy_id():
 runtime=rt();runtime.registry.register_sigma_order(SigmaOrderDefinition('A',50));runtime.registry.register_sigma_order(SigmaOrderDefinition('B',10))
 x=runtime.evaluate_sigma_standard((ev('A',10,5,5),ev('B',5,10,10)),('G1','G2'))
 y=runtime.evaluate_sigma_standard((ev('B',5,10,10),ev('A',10,5,5)),('G1','G2'))
 assert x.selected_policy_id==y.selected_policy_id=='B';assert x.selected_order_index==10
def test_duplicate_order_indices_rejected_at_registration():
 runtime=rt();runtime.registry.register_sigma_order(SigmaOrderDefinition('A',1))
 try: runtime.registry.register_sigma_order(SigmaOrderDefinition('B',1));assert False
 except ValueError as e: assert 'already registered' in str(e)
def test_singleton_a2_does_not_require_order_registration():
 runtime=rt();s=runtime.evaluate_sigma_standard((ev('A',10,10,10),ev('B',9,9,9)),('G1','G2'));assert s.selected_policy_id=='A';assert s.selected_order_index is None
def test_order_index_cannot_rescue_stage1_eliminated_policy():
 runtime=rt();runtime.registry.register_sigma_order(SigmaOrderDefinition('A',100));runtime.registry.register_sigma_order(SigmaOrderDefinition('B',1))
 s=runtime.evaluate_sigma_standard((ev('A',10,10,10),ev('B',9,9,1000)),('G1','G2'));assert s.selected_policy_id=='A';assert s.stage1.survivor_policy_ids==('A',)
