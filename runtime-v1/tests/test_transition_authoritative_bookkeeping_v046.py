
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass

def build():
    r=PVPPRegistry()
    r.register_domain(DomainDefinition('G','g',0))
    for aid in ('steady','start','step1','step2','shared'):
        r.register_action(ActionDefinition(aid,aid,('G',)))
    r.register_recovery_plan(RecoveryPlanDefinition('rp','G','continuity','start',('step1','step2'),5.0))
    rt=PVPPRuntime(r,W())
    lic=ExecutionLicenseEnvelope('p',('start','step1','step2'),('G',),('continuity',),
                                 True,True,True,True,selection_mode='standard',entry_authorized=True)
    ep=ExecutionEpisode('ep',lic,5,1,True,None,active=False)
    eps=EpsilonStepResult(ep,'completed',True,False,(),(),('ev',))
    prior=ActualPersistentStateEnvelope('actor','s0',9.0,{}, {}, {}, {})
    nxt=ActualPersistentStateEnvelope('actor','s1',10.0,{}, {}, {}, {})
    tr=Layer1TransitionResult('ep','p','s0',nxt,True,{'ok':True})
    return rt,eps,prior,tr

def test_commit_is_derived_from_validated_transition_not_independent_boolean():
    rt,eps,prior,tr=build()
    commit=rt.build_layer1_execution_commit_from_transition(
        prior,eps,tr,(RecoveryActionConfirmation('start'),)
    )
    assert commit.episode_id=='ep'
    assert commit.committed_state_time==10.0
    assert commit.state_transition_applied is True
    assert commit.action_confirmations==(RecoveryActionConfirmation('start'),)
    assert any('derived from validated' in n for n in commit.notes)

def test_transition_authoritative_bridge_starts_advances_and_completes_corridor():
    rt,eps,prior,tr=build()
    a=rt.record_recovery_bookkeeping_from_transition(
        prior,eps,tr,(RecoveryActionConfirmation('start'),)
    )
    assert a.started_corridor_ids==('rp',)
    assert rt.active_corridors['rp'].deadline==15.0

    # Each later realized continuation is represented by a later validated transition.
    p1=tr.next_state
    t1=Layer1TransitionResult('ep','p','s1',
        ActualPersistentStateEnvelope('actor','s2',11.0,{}, {}, {}, {}),True,{'ok':True})
    a=rt.record_recovery_bookkeeping_from_transition(
        p1,eps,t1,(RecoveryActionConfirmation('step1'),)
    )
    assert a.advanced_corridor_ids==('rp',)
    assert rt.active_corridors['rp'].remaining_actions==('step2',)

    p2=t1.next_state
    t2=Layer1TransitionResult('ep','p','s2',
        ActualPersistentStateEnvelope('actor','s3',12.0,{}, {}, {}, {}),True,{'ok':True})
    a=rt.record_recovery_bookkeeping_from_transition(
        p2,eps,t2,(RecoveryActionConfirmation('step2'),)
    )
    assert a.completed_corridor_ids==('rp',)
    assert rt.active_corridors['rp'].status=='complete'

def test_invalid_transition_cannot_be_used_as_bookkeeping_authority():
    rt,eps,prior,tr=build()
    bad=Layer1TransitionResult('ep','p','s0',tr.next_state,False,{'ok':True})
    try:
        rt.record_recovery_bookkeeping_from_transition(
            prior,eps,bad,(RecoveryActionConfirmation('start'),)
        )
        assert False
    except ValueError as e:
        assert 'invalid Layer 1 transition' in str(e)
    assert rt.active_corridors=={}

def test_transition_episode_and_policy_identity_must_match_epsilon():
    rt,eps,prior,tr=build()
    bad=Layer1TransitionResult('other','p','s0',tr.next_state,True,{'ok':True})
    try:
        rt.build_layer1_execution_commit_from_transition(prior,eps,bad)
        assert False
    except ValueError as e:
        assert 'episode_id' in str(e)

    bad=Layer1TransitionResult('ep','other','s0',tr.next_state,True,{'ok':True})
    try:
        rt.build_layer1_execution_commit_from_transition(prior,eps,bad)
        assert False
    except ValueError as e:
        assert 'selected_policy_id' in str(e)

def test_committed_time_is_derived_from_next_actual_state_time():
    rt,eps,prior,tr=build()
    commit=rt.build_layer1_execution_commit_from_transition(prior,eps,tr)
    assert commit.committed_state_time==tr.next_state.time
    # No caller-provided committed time exists on the canonical bridge.

def test_action_identity_is_still_explicit_not_inferred_from_epsilon_path_or_policy():
    rt,eps,prior,tr=build()
    a=rt.record_recovery_bookkeeping_from_transition(prior,eps,tr,())
    assert a.started_corridor_ids==()
    assert rt.active_corridors=={}

def test_ambiguous_recovery_action_still_requires_explicit_plan_id():
    rt,eps,prior,tr=build()
    rt.registry.register_recovery_plan(RecoveryPlanDefinition('rp2','G','c2','shared',('step1',),3.0))
    rt.registry.register_recovery_plan(RecoveryPlanDefinition('rp3','G','c3','shared',('step2',),4.0))
    try:
        rt.record_recovery_bookkeeping_from_transition(
            prior,eps,tr,(RecoveryActionConfirmation('shared'),)
        )
        assert False
    except ValueError as e:
        assert 'ambiguous recovery bookkeeping' in str(e)
    assert 'rp2' not in rt.active_corridors and 'rp3' not in rt.active_corridors

def test_legacy_commit_surface_remains_compatible():
    rt,eps,prior,tr=build()
    a=rt.record_layer1_execution_commit(
        eps,Layer1ExecutionCommit('ep',10.0,True,(RecoveryActionConfirmation('start'),))
    )
    assert a.started_corridor_ids==('rp',)
    assert any('legacy compatibility' in n for n in a.notes)

def test_nonterminal_epsilon_cannot_derive_transition_authority():
    rt,eps,prior,tr=build()
    active_ep=ExecutionEpisode('ep',eps.episode.license,5,0,True,None,active=True)
    active=EpsilonStepResult(active_ep,'active',False,False)
    try:
        rt.build_layer1_execution_commit_from_transition(prior,active,tr)
        assert False
    except ValueError as e:
        assert 'terminal epsilon' in str(e)
