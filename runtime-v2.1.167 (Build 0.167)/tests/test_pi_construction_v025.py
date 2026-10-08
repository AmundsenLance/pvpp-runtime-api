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
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',0)); r.register_domain(DomainDefinition('N','n',0))
    for a in ('steady','c','l','s','e','x'):
        r.register_action(ActionDefinition(a,a,('G',)))
    return PVPPRuntime(r,W()),r

def add(r,id,aid,fam,domains=('G',),classes=(),required=False,coherent=True,visible=True):
    r.register_policy_seed(PolicySeedDefinition(id,(aid,),fam,domains,classes,required,coherent,visible))

def test_mission_keeps_continuation_local_and_required_structural():
    runtime,r=rt(); add(r,'cont','c','continuation'); add(r,'local','l','local_adjustment'); add(r,'struct','s','structural_shift'); add(r,'req','x','emergency_escape',required=True)
    a=runtime.construct_pi('Mission',('G',),('contclass',))
    assert set(a.emitted_candidate_ids)=={'cont','local','req'}
    assert 'struct' in a.suppressed_seed_ids

def test_survival_activates_all_families_but_suppresses_unrelated_optional_seed():
    runtime,r=rt(); add(r,'cont','c','continuation'); add(r,'escape','e','emergency_escape'); add(r,'unrelated','x','structural_shift',domains=('N',))
    a=runtime.construct_pi('Survival',('G',),())
    assert set(a.emitted_candidate_ids)=={'cont','escape'}
    assert 'unrelated' in a.suppressed_seed_ids

def test_continuation_is_mandatory():
    runtime,r=rt(); add(r,'local','l','local_adjustment')
    a=runtime.construct_pi('Mission',('G',),())
    assert a.status=='pi_missing_mandatory_continuation' and a.policy_space is None

def test_exact_duplicates_are_pruned_without_projection():
    runtime,r=rt(); add(r,'cont','c','continuation',classes=('k',)); add(r,'cont2','c','continuation',classes=('k',))
    a=runtime.construct_pi('Mission',('G',),('k',))
    assert len(a.policy_space.candidates)==1 and a.duplicate_seed_ids==('cont2',)

def test_overflow_blocks_instead_of_using_registration_order():
    runtime,r=rt(); add(r,'cont','c','continuation')
    for i in range(4):
        aid='l' if i%2==0 else 's'; r.register_action(ActionDefinition(f'z{i}',f'z{i}',('G',))); add(r,f'p{i}',f'z{i}','local_adjustment',classes=(f'k{i}',))
    a=runtime.construct_pi('Mission',('G',),(),config=PiConstructionConfig(max_candidates=3))
    assert a.status=='pi_boundedness_overflow' and a.policy_space is None

def test_required_classes_are_not_invented_by_pi_and_flow_to_separate_completeness_gate():
    runtime,r=rt(); add(r,'cont','c','continuation',classes=('continuation',))
    a=runtime.construct_pi('Mission',('G',),('continuation','exit_transfer'))
    comp=runtime.validate_pi_completeness(a.policy_space)
    assert comp.complete is False and comp.missing_class_ids==('exit_transfer',)

def test_malformed_and_invisible_seeds_do_not_emit():
    runtime,r=rt(); add(r,'cont','c','continuation'); add(r,'bad','l','local_adjustment',coherent=False); add(r,'hidden','s','structural_shift',visible=False)
    a=runtime.construct_pi('Stabilization',('G',),())
    assert a.emitted_candidate_ids==('cont',); assert a.malformed_seed_ids==('bad',); assert 'hidden' not in a.visible_seed_ids
