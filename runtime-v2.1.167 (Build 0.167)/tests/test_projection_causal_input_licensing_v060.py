import sys
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from pvpp_runtime import *
from test_projection_state_and_consistency_v059 import EchoService
from test_projection_service_v036 import build as build_projection, req as projection_req
from test_integrated_canonical_cycle_v041 import actual as integrated_actual


def build_typed(inputs=()):
    svc=EchoService(); rt,w=build_projection(svc)
    def mapper(a):
        s=WorldState(a.time,{'G':10.0},{'state_id':a.state_id})
        return PerceivedDecisionState(
            a.actor_id,a.state_id,a.time,s,ppp={'G':'perceived'},
            confidence={'forecast':'opaque'},uncertainty={'forecast':'represented'},
            projection_causal_inputs=tuple(inputs)
        )
    w.perceived_decision_state_from_actual=mapper
    return rt,w,svc


def item(i='commitment:crop',kind='active_commitment',t=0.0):
    return ProjectionCausalStateInput(i,kind,{'status':'active'},'host/domain projection contract',t,('host-ledger',))


def test_required_represented_causal_input_reaches_projection_service():
    rt,w,svc=build_typed((item(),))
    rq=replace(projection_req(),projection_required_causal_input_ids=('commitment:crop',))
    out=rt.evaluate_integrated_canonical_cycle(integrated_actual(),rq)
    assert out.decision.stopped_at=='Sigma'
    lic=out.decision.projection_input_license_assessment
    assert lic.valid and lic.licensed_input_ids==('commitment:crop',)
    assert all(c.input_license_assessment is not None and c.input_license_assessment.valid for c in svc.calls)
    assert all(c.projection_input_trace['licensed_causal_input_ids']==('commitment:crop',) for c in svc.calls)


def test_missing_required_causal_input_fails_closed_before_projection():
    rt,w,svc=build_typed(())
    rq=replace(projection_req(),projection_required_causal_input_ids=('commitment:crop',))
    try:
        rt.evaluate_integrated_canonical_cycle(integrated_actual(),rq)
        assert False
    except ValueError as e:
        assert 'licensing failed closed' in str(e)
        assert 'commitment:crop' in str(e)
    assert svc.calls==[]


def test_future_hindsight_causal_input_is_rejected():
    rt,w,svc=build_typed((item(t=1.0),))
    rq=replace(projection_req(),projection_required_causal_input_ids=('commitment:crop',))
    try:
        rt.evaluate_integrated_canonical_cycle(integrated_actual(),rq)
        assert False
    except ValueError as e:
        assert 'future/hindsight' in str(e)
    assert svc.calls==[]


def test_duplicate_causal_input_identity_is_rejected():
    rt,w,svc=build_typed((item(),item()))
    rq=replace(projection_req(),projection_required_causal_input_ids=('commitment:crop',))
    try:
        rt.evaluate_integrated_canonical_cycle(integrated_actual(),rq)
        assert False
    except ValueError as e:
        assert 'unique' in str(e)
    assert svc.calls==[]


def test_blank_license_basis_is_rejected():
    bad=ProjectionCausalStateInput('env:rain','environmental_estimate',{'rain':'possible'},'',0.0)
    rt,w,svc=build_typed((bad,))
    rq=replace(projection_req(),projection_required_causal_input_ids=('env:rain',))
    try:
        rt.evaluate_integrated_canonical_cycle(integrated_actual(),rq)
        assert False
    except ValueError as e:
        assert 'license_basis' in str(e)
    assert svc.calls==[]


def test_runtime_does_not_infer_required_input_from_actual_or_graph():
    rt,w,svc=build_typed(())
    rq=replace(projection_req(),projection_required_causal_input_ids=('capacity:skilled_labor',))
    try:
        rt.evaluate_integrated_canonical_cycle(integrated_actual(),rq)
        assert False
    except ValueError as e:
        assert 'capacity:skilled_labor' in str(e)
    assert svc.calls==[]


def test_optional_explicit_causal_input_is_preserved_without_becoming_requirement():
    rt,w,svc=build_typed((item('institution:access','institutional_estimate'),))
    out=rt.evaluate_integrated_canonical_cycle(integrated_actual(),projection_req())
    lic=out.decision.projection_input_license_assessment
    assert lic.valid
    assert lic.required_input_ids==()
    assert lic.licensed_input_ids==('institution:access',)
    assert svc.calls[0].perceived_decision_state.projection_causal_inputs[0].value=={'status':'active'}


def test_q_must_preserve_causal_input_identity_in_projection_trace():
    class DroppingService(EchoService):
        def project(self,req):
            r=super().project(req)
            tr=dict(r.projection_input_trace); tr.pop('licensed_causal_input_ids',None)
            return replace(r,projection_input_trace=tr)
    svc=DroppingService(); rt,w=build_projection(svc)
    def mapper(a):
        s=WorldState(a.time,{'G':10.0},{'state_id':a.state_id})
        return PerceivedDecisionState(a.actor_id,a.state_id,a.time,s,ppp={},projection_causal_inputs=(item(),))
    w.perceived_decision_state_from_actual=mapper
    rq=replace(projection_req(),projection_required_causal_input_ids=('commitment:crop',))
    try:
        rt.evaluate_integrated_canonical_cycle(integrated_actual(),rq)
        assert False
    except ValueError as e:
        assert 'preserve licensed causal input identities' in str(e)
