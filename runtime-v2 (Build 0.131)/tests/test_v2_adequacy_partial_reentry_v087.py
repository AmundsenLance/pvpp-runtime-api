import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_integrated_canonical_cycle_v041 import build, req, actual


def adequacy_plan():
    sig=GovernanceInvalidationSignal('sig-a','Adequacy','recovery evidence changed','evidence',('ev-a',),('old-a',))
    assessment=assess_governance_reentry((sig,))
    return plan_governance_reentry(assessment,(sig,))


def fixture():
    rt,w,t=build(); integrated=rt.evaluate_integrated_canonical_cycle(actual(),req(),execute=False)
    d=integrated.decision; p=adequacy_plan()
    q=AdequacyReusableProjectionArtifact(tuple(d.projection_records),d.joint_recovery_feasibility)
    payloads={'PPP':object(),'Phi':d.pressure_field,'H':d.horizon_assessment,'G':d.governing_assessment,'R':d.regime_assessment,'Graph/Seed':d.graph_assessment,'Pi':d.pi_construction,'Pi Completeness':d.pi_completeness,'Constraints':d.constraints,'Domain Framing':AdequacyReusableDomainFramingArtifact(d.domain_framing,req().domain_frame),'Joint Recovery Feasibility':q}
    b=GovernanceReusableArtifactBundle('b-a','cycle-a',integrated.initial_actual_state_id,'cfg-a',tuple((s,payloads[s]) for s in p.reusable_upstream_stages),('prov-a',))
    ba=validate_reusable_artifact_bundle(p,b,expected_cycle_id='cycle-a',expected_initial_state_id=integrated.initial_actual_state_id,expected_configuration_id='cfg-a')
    return rt,w,t,d,p,b,ba


def test_adequacy_reentry_recomputes_only_adequacy_and_sigma():
    rt,w,t,d,p,b,ba=fixture(); before=w.map_calls
    out=execute_adequacy_reentry(rt,p,b,ba)
    assert out.valid and out.recomputed_stage_ids==('Adequacy','Sigma')
    assert out.decision.selection.selected_policy_id==d.selection.selected_policy_id
    assert out.decision.pipeline_trace==('Adequacy','Sigma')
    assert w.map_calls==before and t.calls==0


def test_adequacy_reentry_does_not_reproject_q():
    rt,w,t,d,p,b,ba=fixture(); before=getattr(w,'project_record_calls',None)
    out=execute_adequacy_reentry(rt,p,b,ba)
    assert out.valid and out.decision.projection_records==d.projection_records
    if before is not None: assert w.project_record_calls==before


def test_adequacy_reentry_rejects_wrong_boundary():
    rt,w,t,d,p,b,ba=fixture(); sig=GovernanceInvalidationSignal('s','Sigma','x','evidence')
    p2=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    out=execute_adequacy_reentry(rt,p2,b,ba); assert not out.valid


def test_adequacy_reentry_requires_valid_bundle_assessment():
    rt,w,t,d,p,b,ba=fixture(); bad=GovernanceReusableArtifactBundleAssessment(False,b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,ba.reusable_stage_ids,('bad',),())
    assert not execute_adequacy_reentry(rt,p,b,bad).valid


def test_adequacy_reentry_rejects_wrong_q_artifact_type():
    rt,w,t,d,p,b,ba=fixture(); arts=tuple((s,object() if s=='Joint Recovery Feasibility' else x) for s,x in b.stage_artifacts)
    bad=GovernanceReusableArtifactBundle(b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,arts,b.provenance_ids)
    out=execute_adequacy_reentry(rt,p,bad,ba); assert not out.valid and any('wrong type' in v for v in out.violations)


def test_adequacy_reentry_requires_q_coverage_equal_feasible_set():
    rt,w,t,d,p,b,ba=fixture(); arts=[]
    for s,x in b.stage_artifacts:
        if s=='Joint Recovery Feasibility': x=AdequacyReusableProjectionArtifact(tuple(x.projection_records[:-1]),x.joint_recovery_artifact)
        arts.append((s,x))
    bad=GovernanceReusableArtifactBundle(b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,tuple(arts),b.provenance_ids)
    out=execute_adequacy_reentry(rt,p,bad,ba); assert not out.valid and any('coverage' in v for v in out.violations)


def test_adequacy_reentry_stops_before_epsilon_layer1():
    rt,w,t,d,p,b,ba=fixture(); out=execute_adequacy_reentry(rt,p,b,ba)
    assert out.valid and out.decision.stopped_at=='Sigma' and t.calls==0


def test_adequacy_reentry_preserves_reused_stage_identity_list():
    rt,w,t,d,p,b,ba=fixture(); out=execute_adequacy_reentry(rt,p,b,ba)
    assert out.valid and out.reused_stage_ids==p.reusable_upstream_stages
