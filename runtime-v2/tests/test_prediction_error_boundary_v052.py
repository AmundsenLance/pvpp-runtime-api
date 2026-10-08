
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import *
from test_post_execution_epistemic_update_v044 import prior_actual,next_actual,memory,expectation,epsilon,transition

class W: pass

class PESvc:
    def __init__(self, components=None):
        self.requests=[]
        self.components=components if components is not None else (
            PredictionErrorComponent('policy_outcome',expected={'success':True},realized={'success':False},material=True),
        )
    def evaluate(self,req):
        self.requests.append(req)
        return PredictionErrorAssessment(
            req.actor_id,req.episode_id,req.selected_policy_id,
            tuple(self.components),any(c.material for c in self.components),
            notes=('typed mismatch only',)
        )

def runtime(pe=None,eu=None):
    r=PVPPRegistry(); r.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(r,W(),prediction_error_service=pe,epistemic_update_service=eu)

def projection():
    return PolicyProjectionRecord(
        'policy',True,None,{'G':10.0},(),
        metadata={'expected_success':True},projection_horizon=12.0
    )

def test_prediction_error_request_is_built_after_validated_realization():
    svc=PESvc(); rt=runtime(svc)
    req,res,val=rt.apply_prediction_error(
        prior_actual(),epsilon('failed',True,True),transition(),
        expectation(),projection()
    )
    assert val.valid and res.material_mismatch
    assert req.selected_policy_id=='policy'
    assert req.prior_actual_state_id=='s0' and req.next_actual_state_id=='s1'
    assert req.execution_status=='failed'
    assert req.prior_expectation_state.expectation_state_id=='k0'
    assert req.selected_projection_record.policy_id=='policy'
    assert req.realized_pv_bundles==({'pv':'realized'},)

def test_core_prediction_error_types_are_preserved_not_scalarized():
    components=tuple(
        PredictionErrorComponent(k,expected={'x':1},realized={'x':2})
        for k in ('transition','source','policy_outcome','timing','interaction_response')
    )
    svc=PESvc(components); rt=runtime(svc)
    _,res,val=rt.apply_prediction_error(
        prior_actual(),epsilon(),transition(),expectation(),projection()
    )
    assert val.valid
    assert tuple(c.error_class for c in res.components)==(
        'transition','source','policy_outcome','timing','interaction_response'
    )
    assert not hasattr(res,'score')
    assert not hasattr(res,'magnitude')

def test_unsupported_generic_error_class_fails_closed():
    svc=PESvc((PredictionErrorComponent('generic_surprise',1,2),))
    rt=runtime(svc)
    try:
        rt.apply_prediction_error(
            prior_actual(),epsilon(),transition(),expectation(),projection()
        )
        assert False
    except ValueError as e:
        assert 'unsupported prediction error class' in str(e)

def test_material_flag_must_match_typed_components():
    class Bad:
        def evaluate(self,req):
            return PredictionErrorAssessment(
                req.actor_id,req.episode_id,req.selected_policy_id,
                (PredictionErrorComponent('timing',1,2,material=True),),
                material_mismatch=False
            )
    rt=runtime(Bad())
    try:
        rt.apply_prediction_error(
            prior_actual(),epsilon(),transition(),expectation(),projection()
        )
        assert False
    except ValueError as e:
        assert 'material_mismatch' in str(e)

def test_policy_projection_stage_mismatch_is_rejected():
    bad=PolicyProjectionRecord('other',True,None,{},())
    rt=runtime(PESvc())
    try:
        rt.apply_prediction_error(
            prior_actual(),epsilon(),transition(),expectation(),bad
        )
        assert False
    except ValueError as e:
        assert 'projection record policy mismatch' in str(e)

def test_nonterminal_or_invalid_transition_cannot_generate_prediction_error():
    svc=PESvc(); rt=runtime(svc)
    try:
        rt.apply_prediction_error(
            prior_actual(),epsilon('active',False,False),transition(),expectation(),projection()
        )
        assert False
    except ValueError as e:
        assert 'terminal epsilon' in str(e)
    assert svc.requests==[]

    try:
        rt.apply_prediction_error(
            prior_actual(),epsilon(),transition(applied=False),expectation(),projection()
        )
        assert False
    except ValueError as e:
        assert 'validated Layer 1 transition' in str(e)

def test_prediction_error_can_be_carried_into_epistemic_update_without_defining_learning_formula():
    pe=PredictionErrorAssessment(
        'actor','ep','policy',
        (PredictionErrorComponent('policy_outcome','expected','realized'),),True
    )
    class EU:
        def __init__(self): self.req=None
        def update(self,req):
            self.req=req
            # Host chooses K-only update; runtime does not derive alpha or formula.
            k=ExpectationStateReference(req.actor_id,'k1',req.next_actual_time,{'updated':'host-owned'})
            return PostExecutionEpistemicUpdateResult(
                req.actor_id,req.episode_id,req.prior_memory_state,k,False,True
            )
    eu=EU(); rt=runtime(None,eu)
    req,res,val=rt.apply_post_execution_epistemic_update(
        prior_actual(),epsilon(),transition(),memory(),expectation(),
        prediction_error=pe
    )
    assert val.valid
    assert eu.req.prediction_error is pe
    assert res.expectation_updated and not res.memory_updated

def test_no_prediction_error_service_means_no_implicit_computation():
    rt=runtime(None)
    try:
        rt.apply_prediction_error(
            prior_actual(),epsilon(),transition(),expectation(),projection()
        )
        assert False
    except ValueError as e:
        assert 'no PredictionErrorService' in str(e)


def test_memory_conditioned_explicit_update_routes_prediction_error_before_k_update():
    from test_memory_conditioned_sequence_v045 import build as build_mem, actual as mem_actual, memory as mem_memory, expectation as mem_expectation, req as mem_req

    class PE:
        def __init__(self): self.requests=[]
        def evaluate(self,req):
            self.requests.append(req)
            return PredictionErrorAssessment(
                req.actor_id,req.episode_id,req.selected_policy_id,
                (PredictionErrorComponent('policy_outcome',
                    expected={'horizon':20.0},realized={'status':req.execution_status}),),
                True
            )

    pe=PE()
    rt,w,retrieval,transition,upd=build_mem()
    rt.prediction_error_service=pe
    out=rt.evaluate_memory_conditioned_integrated_cycle(
        mem_actual(),mem_memory(),mem_req(),
        query='cue',expectation_state=mem_expectation(),
        execute=True,update_epistemic_state=True,
        episode_id='ep-pe',
        execution_observations=(ExecutionObservation('obs',completed=True),)
    )
    assert out.status=='memory_cycle_transition_and_epistemic_update_applied'
    assert len(pe.requests)==1
    assert out.prediction_error is not None
    assert out.prediction_error_validation.valid
    assert out.epistemic_update_request.prediction_error is out.prediction_error
    assert upd.requests[0].prediction_error is out.prediction_error
    assert pe.requests[0].selected_projection_record.policy_id=='graph:cont'
