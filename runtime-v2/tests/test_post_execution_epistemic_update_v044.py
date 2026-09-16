
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W:
    pass

class UpdateSvc:
    def __init__(self, mode='both'):
        self.mode=mode
        self.requests=[]
    def update(self,req):
        self.requests.append(req)
        m=req.prior_memory_state
        k=req.prior_expectation_state
        if self.mode in ('memory','both'):
            m=MemoryStateReference(req.actor_id,m.memory_state_id+'-next',req.next_actual_time,
                                   {'updated_from':req.execution_status})
        if self.mode in ('expectation','both'):
            kid='k-next' if k is None else k.expectation_state_id+'-next'
            k=ExpectationStateReference(req.actor_id,kid,req.next_actual_time,
                                        {'learned_from':req.execution_status})
        return PostExecutionEpistemicUpdateResult(
            req.actor_id,req.episode_id,m,k,
            self.mode in ('memory','both'),
            self.mode in ('expectation','both')
        )

def runtime(service=None):
    r=PVPPRegistry()
    r.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(r,W(),epistemic_update_service=service)

def prior_actual():
    return ActualPersistentStateEnvelope('actor','s0',1.0,{}, {}, {}, {})

def next_actual():
    return ActualPersistentStateEnvelope('actor','s1',2.0,{}, {}, {}, {})

def memory():
    return MemoryStateReference('actor','m0',1.0,{'history':'opaque'})

def expectation():
    return ExpectationStateReference('actor','k0',1.0,{'forecast':'opaque'})

def epsilon(status='completed', terminal=True, return_upstream=False):
    lic=ExecutionLicenseEnvelope(
        'policy',('act',),('G',),('continuity',),
        True,True,True,True,(),selection_mode='standard',entry_authorized=True
    )
    ep=ExecutionEpisode('ep',lic,2,1,True,None,active=not terminal)
    return EpsilonStepResult(
        ep,status,terminal,return_upstream,
        ({'pv':'realized'},),({'fact':'learned'},),('event-1',)
    )

def transition(applied=True, *, episode_id='ep', policy='policy', state=None):
    return Layer1TransitionResult(
        episode_id,policy,'s0',state or next_actual(),applied,{'ok':True}
    )

def test_memory_and_expectation_can_update_independently_but_together():
    svc=UpdateSvc('both'); rt=runtime(svc)
    req,res,val=rt.apply_post_execution_epistemic_update(
        prior_actual(),epsilon(),transition(),memory(),expectation()
    )
    assert val.valid
    assert res.memory_updated and res.expectation_updated
    assert res.next_memory_state.memory_state_id=='m0-next'
    assert res.next_expectation_state.expectation_state_id=='k0-next'
    assert res.next_memory_state.time==2.0 and res.next_expectation_state.time==2.0
    assert req.realized_pv_bundles==({'pv':'realized'},)
    assert req.execution_information==({'fact':'learned'},)

def test_memory_only_update_preserves_expectation_exactly():
    svc=UpdateSvc('memory'); rt=runtime(svc)
    k=expectation()
    _,res,val=rt.apply_post_execution_epistemic_update(
        prior_actual(),epsilon(),transition(),memory(),k
    )
    assert val.valid and res.memory_updated and not res.expectation_updated
    assert res.next_expectation_state is k

def test_expectation_only_update_preserves_memory_exactly():
    svc=UpdateSvc('expectation'); rt=runtime(svc)
    m=memory()
    _,res,val=rt.apply_post_execution_epistemic_update(
        prior_actual(),epsilon(),transition(),m,expectation()
    )
    assert val.valid and not res.memory_updated and res.expectation_updated
    assert res.next_memory_state is m

def test_neither_update_is_valid_and_has_no_hidden_rewrite():
    svc=UpdateSvc('none'); rt=runtime(svc)
    m=memory(); k=expectation()
    _,res,val=rt.apply_post_execution_epistemic_update(
        prior_actual(),epsilon(),transition(),m,k
    )
    assert val.valid
    assert not res.memory_updated and not res.expectation_updated
    assert res.next_memory_state is m and res.next_expectation_state is k

def test_failed_execution_can_still_generate_memory_and_expectation_update():
    svc=UpdateSvc('both'); rt=runtime(svc)
    failed=epsilon('failed',True,True)
    req,res,val=rt.apply_post_execution_epistemic_update(
        prior_actual(),failed,transition(),memory(),expectation()
    )
    assert val.valid
    assert req.execution_status=='failed' and req.return_upstream
    assert res.memory_updated and res.expectation_updated

def test_nonterminal_execution_cannot_be_committed_to_epistemic_update():
    svc=UpdateSvc('both'); rt=runtime(svc)
    try:
        rt.apply_post_execution_epistemic_update(
            prior_actual(),epsilon('active',False,False),transition(),memory(),expectation()
        )
        assert False
    except ValueError as e:
        assert 'terminal epsilon' in str(e)
    assert not svc.requests

def test_invalid_layer1_transition_blocks_epistemic_update():
    svc=UpdateSvc('both'); rt=runtime(svc)
    try:
        rt.apply_post_execution_epistemic_update(
            prior_actual(),epsilon(),transition(applied=False),memory(),expectation()
        )
        assert False
    except ValueError as e:
        assert 'validated Layer 1 transition' in str(e)
    assert not svc.requests

def test_silent_memory_rewrite_with_update_flag_false_is_rejected():
    class Bad:
        def update(self,req):
            changed=MemoryStateReference(req.actor_id,'changed',req.next_actual_time,{})
            return PostExecutionEpistemicUpdateResult(
                req.actor_id,req.episode_id,changed,req.prior_expectation_state,False,False
            )
    rt=runtime(Bad())
    try:
        rt.apply_post_execution_epistemic_update(
            prior_actual(),epsilon(),transition(),memory(),expectation()
        )
        assert False
    except ValueError as e:
        assert 'silently alter retained memory' in str(e)

def test_updated_memory_requires_new_identity_and_next_state_time():
    class BadSameId:
        def update(self,req):
            changed=MemoryStateReference(req.actor_id,req.prior_memory_state.memory_state_id,
                                         req.next_actual_time,{})
            return PostExecutionEpistemicUpdateResult(
                req.actor_id,req.episode_id,changed,req.prior_expectation_state,True,False
            )
    rt=runtime(BadSameId())
    try:
        rt.apply_post_execution_epistemic_update(
            prior_actual(),epsilon(),transition(),memory(),expectation()
        )
        assert False
    except ValueError as e:
        assert 'new memory_state_id' in str(e)

    class BadTime:
        def update(self,req):
            changed=MemoryStateReference(req.actor_id,'m-next',req.next_actual_time+1,{})
            return PostExecutionEpistemicUpdateResult(
                req.actor_id,req.episode_id,changed,req.prior_expectation_state,True,False
            )
    rt=runtime(BadTime())
    try:
        rt.apply_post_execution_epistemic_update(
            prior_actual(),epsilon(),transition(),memory(),expectation()
        )
        assert False
    except ValueError as e:
        assert 'time must align' in str(e)

def test_expectation_update_can_create_k_when_prior_k_absent():
    svc=UpdateSvc('expectation'); rt=runtime(svc)
    _,res,val=rt.apply_post_execution_epistemic_update(
        prior_actual(),epsilon(),transition(),memory(),None
    )
    assert val.valid
    assert res.next_expectation_state.expectation_state_id=='k-next'
    assert res.expectation_updated

def test_episode_or_actor_mismatch_is_rejected():
    class Bad:
        def update(self,req):
            return PostExecutionEpistemicUpdateResult(
                'other','wrong',req.prior_memory_state,req.prior_expectation_state,False,False
            )
    rt=runtime(Bad())
    try:
        rt.apply_post_execution_epistemic_update(
            prior_actual(),epsilon(),transition(),memory(),expectation()
        )
        assert False
    except ValueError as e:
        assert 'actor_id' in str(e) and 'episode_id' in str(e)

def test_missing_update_service_is_explicit_not_implicit_learning():
    rt=runtime(None)
    try:
        rt.apply_post_execution_epistemic_update(
            prior_actual(),epsilon(),transition(),memory(),expectation()
        )
        assert False
    except ValueError as e:
        assert 'no EpistemicUpdateService' in str(e)
