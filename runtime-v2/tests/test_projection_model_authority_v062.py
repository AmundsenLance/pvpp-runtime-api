import sys
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_projection_service_v036 import build as build_projection, req as projection_req, state as projection_state


class AuthorityEchoService:
    def __init__(self, mutate=None):
        self.calls=[]; self.mutate=mutate
    def project(self, req):
        self.calls.append(req)
        a=req.model_authority
        rec=PolicyProjectionRecord(
            req.policy_id, False, req.represented_state, {'G':20.0},
            (RecoveryCorridorProjection('G','continuity',True,True,True,2.0,20.0),),
            projection_horizon=req.projection_horizon,
            state_id=req.state_id, state_time=req.represented_state.time,
            candidate_mode=req.candidate_mode,
            projected_domain_trajectories={'G':(10.0,9.0)},
            reachable_viable={'G':('i',)},
            information_quality_trace={'basis':'authority-test'},
            model_version=a.model_version if a else 'legacy-model-v1',
            projection_input_trace=dict(req.projection_input_trace),
            model_id=a.model_id if a else '',
            model_configuration_id=a.configuration_id if a else '',
            model_parameter_set_id=a.parameter_set_id if a else '',
        )
        return self.mutate(rec) if self.mutate else rec


def authority(lp=30.0, version='v3'):
    return ProjectionModelAuthority('forecast-engine',version,'cfg-A','theta-2026-09','host/model registry',lp)


def request_with_authority(a):
    return replace(projection_req(a.licensed_projection_horizon), projection_model_authority=a)


def test_explicit_model_authority_reaches_every_q_call_and_is_reported():
    svc=AuthorityEchoService(); rt,_=build_projection(svc); a=authority()
    out=rt.evaluate_canonical_decision_cycle(projection_state(),request_with_authority(a))
    assert out.projection_model_authority_assessment.valid
    assert out.projection_model_authority_assessment.model_id=='forecast-engine'
    assert len(svc.calls)==2
    assert all(c.model_authority is a for c in svc.calls)
    assert all(c.model_authority_assessment.valid for c in svc.calls)
    assert all(r.model_version=='v3' and r.model_id=='forecast-engine' for r in out.projection_records)


def test_model_version_mismatch_fails_closed_before_downstream_consumption():
    svc=AuthorityEchoService(lambda r: replace(r,model_version='wrong-version'))
    rt,_=build_projection(svc); a=authority()
    try: rt.evaluate_canonical_decision_cycle(projection_state(),request_with_authority(a)); assert False
    except ValueError as e: assert 'model_version' in str(e) and 'authority' in str(e)


def test_model_identity_configuration_and_parameter_set_mismatches_fail_closed():
    mutations=(
        lambda r: replace(r,model_id='wrong'),
        lambda r: replace(r,model_configuration_id='wrong'),
        lambda r: replace(r,model_parameter_set_id='wrong'),
    )
    words=('model_id','configuration','parameter-set')
    for mut,word in zip(mutations,words):
        rt,_=build_projection(AuthorityEchoService(mut)); a=authority()
        try: rt.evaluate_canonical_decision_cycle(projection_state(),request_with_authority(a)); assert False
        except ValueError as e: assert word in str(e)


def test_authority_horizon_must_match_externally_supplied_LP_exactly():
    svc=AuthorityEchoService(); rt,_=build_projection(svc)
    a=authority(30.0)
    bad=replace(projection_req(25.0),projection_model_authority=a)
    try: rt.evaluate_canonical_decision_cycle(projection_state(),bad); assert False
    except ValueError as e: assert 'licensed horizon' in str(e) and 'L_P' in str(e)
    assert not svc.calls


def test_malformed_authority_fails_closed_without_calling_projection():
    svc=AuthorityEchoService(); rt,_=build_projection(svc)
    a=ProjectionModelAuthority('','v1','cfg','params','basis',30.0)
    try: rt.evaluate_canonical_decision_cycle(projection_state(),request_with_authority(a)); assert False
    except ValueError as e: assert 'model_id' in str(e)
    assert not svc.calls


def test_absent_explicit_authority_remains_backward_compatible_but_is_not_synthesized():
    svc=AuthorityEchoService(); rt,_=build_projection(svc)
    out=rt.evaluate_canonical_decision_cycle(projection_state(),projection_req())
    assert out.projection_model_authority_assessment.valid
    assert out.projection_model_authority_assessment.model_id==''
    assert all(c.model_authority is None for c in svc.calls)
    assert all(r.model_version=='legacy-model-v1' for r in out.projection_records)


def test_runtime_does_not_rank_or_compare_model_versions():
    # Two separate host-invoked cycles may deliberately use different declared models.
    # The runtime validates each one independently; it does not choose a preferred version.
    svc=AuthorityEchoService(); rt,_=build_projection(svc)
    out1=rt.evaluate_canonical_decision_cycle(projection_state(),request_with_authority(authority(version='v3')))
    out2=rt.evaluate_canonical_decision_cycle(projection_state(),request_with_authority(authority(version='v4')))
    assert out1.projection_model_authority_assessment.model_version=='v3'
    assert out2.projection_model_authority_assessment.model_version=='v4'
    assert out1.selection.selected_policy_id == out2.selection.selected_policy_id


def test_model_parameter_contents_remain_opaque_to_runtime():
    svc=AuthorityEchoService(); rt,_=build_projection(svc)
    a=replace(authority(), metadata={'theta': {'decline_rule':'domain-owned'}, 'numeric': 999999})
    out=rt.evaluate_canonical_decision_cycle(projection_state(),request_with_authority(a))
    assert out.projection_model_authority_assessment.valid
    assert svc.calls[0].model_authority.metadata['numeric']==999999
