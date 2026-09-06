import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def __init__(self, profiles): self.profiles=profiles
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)
    def constraint_profile(self,state,pid,action_ids,regime,governing):
        return self.profiles[pid]

def build(profiles):
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',0)); r.register_action(ActionDefinition('steady','steady',()))
    r.register_action(ActionDefinition('a','a',('G',)))
    r.register_constraint_rule(ConstraintRuleDefinition('H','hard'))
    r.register_constraint_rule(ConstraintRuleDefinition('C','conditional','prudence'))
    r.register_constraint_rule(ConstraintRuleDefinition('S','soft'))
    return PVPPRuntime(r,W(profiles))

def cand(pid): return CandidatePolicySet(pid,('a',))

def test_hard_violation_filters_in_every_regime():
    p=PolicyConstraintProfile('p',(ConstraintObservation('H',True,True,False,False),))
    rt=build({'p':p})
    a=rt.evaluate_constraint_system(WorldState(0,{}),(cand('p'),),regime='Existential',governing_domain_ids=('G',))
    assert a.feasible_policy_ids==()
    assert a.candidate_results[0].violation_profile.hard_violation_ids==('H',)

def test_hard_relaxation_flags_are_rejected():
    p=PolicyConstraintProfile('p',(ConstraintObservation('H',True,True,True,True),))
    rt=build({'p':p})
    try: rt.evaluate_constraint_system(WorldState(0,{}),(cand('p'),),regime='Existential',governing_domain_ids=('G',)); assert False
    except ValueError as e: assert 'hard constraint' in str(e)

def test_conditional_requires_both_regime_permission_and_necessity():
    for rp,na,expected in [(False,False,False),(True,False,False),(False,True,False),(True,True,True)]:
        p=PolicyConstraintProfile('p',(ConstraintObservation('C',True,True,rp,na),))
        rt=build({'p':p}); a=rt.evaluate_constraint_system(WorldState(0,{}),(cand('p'),),regime='Survival',governing_domain_ids=('G',))
        assert bool(a.feasible_policy_ids)==expected
        if expected: assert a.candidate_results[0].violation_profile.relaxed_conditional_violation_ids==('C',)

def test_soft_violation_never_filters():
    p=PolicyConstraintProfile('p',(ConstraintObservation('S',True),))
    rt=build({'p':p}); a=rt.evaluate_constraint_system(WorldState(0,{}),(cand('p'),),regime='Mission',governing_domain_ids=('G',))
    assert a.feasible_policy_ids==('p',)
    assert a.candidate_results[0].violation_profile.soft_violation_ids==('S',)

def test_inactive_constraint_does_not_filter():
    p=PolicyConstraintProfile('p',(ConstraintObservation('H',True,False),ConstraintObservation('C',True,False)))
    rt=build({'p':p}); a=rt.evaluate_constraint_system(WorldState(0,{}),(cand('p'),),regime='Mission',governing_domain_ids=('G',))
    assert a.feasible_policy_ids==('p',)

def test_unknown_and_duplicate_rule_observations_fail_closed():
    rt=build({'p':PolicyConstraintProfile('p',(ConstraintObservation('X',True),))})
    try: rt.evaluate_constraint_system(WorldState(0,{}),(cand('p'),),regime='Mission',governing_domain_ids=('G',)); assert False
    except ValueError as e: assert 'unregistered rule' in str(e)
    rt=build({'p':PolicyConstraintProfile('p',(ConstraintObservation('S',False),ConstraintObservation('S',True)))})
    try: rt.evaluate_constraint_system(WorldState(0,{}),(cand('p'),),regime='Mission',governing_domain_ids=('G',)); assert False
    except ValueError as e: assert 'duplicate constraint observation' in str(e)

def test_profile_policy_mismatch_fails_closed():
    rt=build({'p':PolicyConstraintProfile('q',())})
    try: rt.evaluate_constraint_system(WorldState(0,{}),(cand('p'),),regime='Mission',governing_domain_ids=('G',)); assert False
    except ValueError as e: assert 'policy mismatch' in str(e)

def test_mixed_candidates_produce_typed_valid_subset_without_scalar_counting():
    profiles={
      'hard':PolicyConstraintProfile('hard',(ConstraintObservation('H',True),)),
      'conditional':PolicyConstraintProfile('conditional',(ConstraintObservation('C',True,True,True,True),)),
      'soft':PolicyConstraintProfile('soft',(ConstraintObservation('S',True),)),
    }
    rt=build(profiles); a=rt.evaluate_constraint_system(WorldState(0,{}),tuple(cand(x) for x in profiles),regime='Survival',governing_domain_ids=('G',))
    assert a.feasible_policy_ids==('conditional','soft')
    assert a.infeasible_policy_ids==('hard',)

class IntegratedW(W):
    def __init__(self,profiles): super().__init__(profiles); self.q_calls=[]
    def project_policy_record(self,state,pid,action_ids):
        self.q_calls.append(pid)
        return PolicyProjectionRecord(pid,True,state,{'G':10.0},())

def integrated_rt(profiles):
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',0,governing_horizon=100))
    r.register_action(ActionDefinition('steady','steady',('G',))); r.register_action(ActionDefinition('a','a',('G',)))
    r.register_governing_configuration(GoverningConfiguration(0)); r.register_regime_configuration(RegimeConfiguration(1,2,3,1000,900,800))
    r.register_constraint_rule(ConstraintRuleDefinition('H','hard')); r.register_constraint_rule(ConstraintRuleDefinition('S','soft'))
    w=IntegratedW(profiles); return PVPPRuntime(r,w),w

def test_strict_recovery_path_uses_typed_constraints_and_skips_q_for_filtered_policy():
    profiles={'hard':PolicyConstraintProfile('hard',(ConstraintObservation('H',True),)), 'soft':PolicyConstraintProfile('soft',(ConstraintObservation('S',True),))}
    rt,w=integrated_rt(profiles)
    a,term,records=rt._evaluate_constraints_with_projection_records(WorldState(0,{}),(cand('hard'),cand('soft')))
    assert a.infeasible_policy_ids==('hard',); assert a.feasible_policy_ids==('soft',)
    assert w.q_calls==['soft']; assert set(records)=={'soft'}

def test_q_cannot_overrule_typed_constraint_feasibility():
    profiles={'soft':PolicyConstraintProfile('soft',(ConstraintObservation('S',True),))}
    rt,w=integrated_rt(profiles)
    def badq(state,pid,action_ids): return PolicyProjectionRecord(pid,False,None,{},(),reasons=('projection says no',))
    w.project_policy_record=badq
    try: rt._evaluate_constraints_with_projection_records(WorldState(0,{}),(cand('soft'),)); assert False
    except ValueError as e: assert 'contradicts canonical Constraints' in str(e)
