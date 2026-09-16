
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
    result=EpsilonStepResult(ep,'completed',True,False,(),(),('ev',))
    return rt,result

def test_commit_starts_then_advances_and_completes_corridor():
    rt,result=build()
    a=rt.record_layer1_execution_commit(
        result,Layer1ExecutionCommit('ep',10.0,True,(RecoveryActionConfirmation('start'),))
    )
    assert a.started_corridor_ids==('rp',)
    c=rt.active_corridors['rp']; assert c.deadline==15.0 and c.remaining_actions==('step1','step2')
    a=rt.record_layer1_execution_commit(
        result,Layer1ExecutionCommit('ep',11.0,True,(RecoveryActionConfirmation('step1'),))
    )
    assert a.advanced_corridor_ids==('rp',)
    assert rt.active_corridors['rp'].remaining_actions==('step2',)
    a=rt.record_layer1_execution_commit(
        result,Layer1ExecutionCommit('ep',12.0,True,(RecoveryActionConfirmation('step2'),))
    )
    assert a.completed_corridor_ids==('rp',)
    assert rt.active_corridors['rp'].status=='complete'

def test_commit_requires_layer1_transition_confirmation():
    rt,result=build()
    try:
        rt.record_layer1_execution_commit(
            result,Layer1ExecutionCommit('ep',10.0,False,(RecoveryActionConfirmation('start'),))
        )
        assert False
    except ValueError as e:
        assert 'Layer 1 transition' in str(e)
    assert rt.active_corridors=={}

def test_epsilon_completion_alone_does_not_update_corridor():
    rt,result=build()
    assert result.status=='completed'
    assert rt.active_corridors=={}

def test_episode_mismatch_fails_closed():
    rt,result=build()
    try:
        rt.record_layer1_execution_commit(
            result,Layer1ExecutionCommit('other',10.0,True,(RecoveryActionConfirmation('start'),))
        )
        assert False
    except ValueError as e:
        assert 'episode_id' in str(e)

def test_unrelated_confirmed_action_is_audited_but_does_not_change_corridors():
    rt,result=build()
    a=rt.record_layer1_execution_commit(
        result,Layer1ExecutionCommit('ep',10.0,True,(RecoveryActionConfirmation('shared'),))
    )
    assert a.ignored_action_ids==('shared',)
    assert rt.active_corridors=={}

def test_ambiguous_action_requires_explicit_recovery_plan_id():
    rt,result=build()
    rt.registry.register_recovery_plan(RecoveryPlanDefinition('rp2','G','continuity2','shared',('step1',),3.0))
    rt.registry.register_recovery_plan(RecoveryPlanDefinition('rp3','G','continuity3','shared',('step2',),4.0))
    try:
        rt.record_layer1_execution_commit(
            result,Layer1ExecutionCommit('ep',10.0,True,(RecoveryActionConfirmation('shared'),))
        )
        assert False
    except ValueError as e:
        assert 'ambiguous recovery bookkeeping' in str(e)
    assert 'rp2' not in rt.active_corridors and 'rp3' not in rt.active_corridors

    a=rt.record_layer1_execution_commit(
        result,Layer1ExecutionCommit('ep',10.0,True,(RecoveryActionConfirmation('shared','rp2'),))
    )
    assert a.started_corridor_ids==('rp2',)
    assert 'rp3' not in rt.active_corridors

def test_two_active_corridors_waiting_on_same_action_require_explicit_plan():
    rt,result=build()
    rt.registry.register_recovery_plan(RecoveryPlanDefinition('rp2','G','continuity2','shared',('step1',),3.0))
    rt.active_corridors['rp']=ActiveRecoveryCorridor('rp','G','continuity',('step1',),20.0)
    rt.active_corridors['rp2']=ActiveRecoveryCorridor('rp2','G','continuity2',('step1',),20.0)
    try:
        rt.record_layer1_execution_commit(
            result,Layer1ExecutionCommit('ep',10.0,True,(RecoveryActionConfirmation('step1'),))
        )
        assert False
    except ValueError as e:
        assert 'ambiguous recovery bookkeeping' in str(e)

def test_nonterminal_epsilon_result_cannot_be_committed():
    rt,result=build()
    active_ep=ExecutionEpisode('ep',result.episode.license,5,0,True,None,active=True)
    active=EpsilonStepResult(active_ep,'active',False,False)
    try:
        rt.record_layer1_execution_commit(
            active,Layer1ExecutionCommit('ep',10.0,True,(RecoveryActionConfirmation('start'),))
        )
        assert False
    except ValueError as e:
        assert 'terminal epsilon' in str(e)
