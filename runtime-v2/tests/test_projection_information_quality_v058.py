import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass

def runtime():
    reg=PVPPRegistry()
    reg.register_domain(DomainDefinition('D','D',0.0))
    reg.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(reg,W())

def req():
    s=WorldState(0.0,{'D':1.0},{'state_id':'s'})
    return ProjectionRequest(s,'p',('a',),'ordinary_adequacy',5.0,None,'s',{'state':'s'})

def rec(**kw):
    base=dict(policy_id='p',feasible=True,projected_horizons={'D':5.0},projection_horizon=5.0,
              right_censored_domain_ids=('D',),state_id='s',state_time=0.0,candidate_mode='ordinary_adequacy',
              model_version='m1',projection_input_trace={'state':'s'})
    base.update(kw)
    return PolicyProjectionRecord(**base)

def test_typed_quality_claim_validates_without_affecting_censoring():
    c=ProjectionInformationQualityClaim('reachability','route:A','current graph + K forecast','moderate','visibility degraded',('graph:v7','K:12'))
    out=runtime().validate_projection_record(req(),rec(information_quality_claims=(c,)))
    assert out.right_censored_domain_ids==('D',)
    assert out.information_quality_claims[0].confidence=='moderate'

def test_confidence_is_opaque_not_numeric_or_truth_required():
    for value in ('low',{'grade':'contested'},0.73):
        c=ProjectionInformationQualityClaim('closure','route:A','licensed predictive model',value)
        assert runtime().validate_projection_record(req(),rec(information_quality_claims=(c,)))

def test_blank_basis_rejected():
    c=ProjectionInformationQualityClaim('reachability','route:A','', 'high')
    try:
        runtime().validate_projection_record(req(),rec(information_quality_claims=(c,)))
        assert False
    except ValueError as e:
        assert 'basis' in str(e)

def test_missing_confidence_metadata_rejected_for_typed_claim():
    c=ProjectionInformationQualityClaim('reachability','route:A','sensor+memory',None)
    try:
        runtime().validate_projection_record(req(),rec(information_quality_claims=(c,)))
        assert False
    except ValueError as e:
        assert 'confidence' in str(e)

def test_duplicate_subject_claim_rejected():
    c=ProjectionInformationQualityClaim('reopening','route:A','model','medium')
    try:
        runtime().validate_projection_record(req(),rec(information_quality_claims=(c,c)))
        assert False
    except ValueError as e:
        assert 'duplicate' in str(e)

def test_unknown_subject_kind_rejected():
    c=ProjectionInformationQualityClaim('preference','p','model','high')
    try:
        runtime().validate_projection_record(req(),rec(information_quality_claims=(c,)))
        assert False
    except ValueError as e:
        assert 'subject_kind' in str(e)

def test_quality_claim_cannot_replace_right_censoring_semantics():
    c=ProjectionInformationQualityClaim('horizon','D','model','high')
    bad=rec(projected_horizons={'D':99.0},information_quality_claims=(c,))
    try:
        runtime().validate_projection_record(req(),bad)
        assert False
    except ValueError as e:
        assert 'right-censored' in str(e)

def test_quality_claim_has_no_selector_or_feasibility_surface():
    fields=ProjectionInformationQualityClaim.__dataclass_fields__
    for forbidden in ('utility','score','weight','rank','feasible','selected_policy_id'):
        assert forbidden not in fields
