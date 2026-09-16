import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_integrated_canonical_cycle_v041 import build, req, actual


def sigma_plan():
    sig=GovernanceInvalidationSignal('sig-sigma','Sigma','selection evidence changed','evidence',('ev-sigma',),('old-sigma',))
    assessment=assess_governance_reentry((sig,))
    return plan_governance_reentry(assessment,(sig,))


def fixture():
    rt,w,t=build()
    integrated=rt.evaluate_integrated_canonical_cycle(actual(),req(),execute=False)
    d=integrated.decision; p=sigma_plan()
    records=tuple(d.projection_records)
    aq=SigmaReusableAdequacyArtifact(d.adequacy,records)
    payloads={
        'PPP': object(), 'Phi': d.pressure_field, 'H': d.horizon_assessment,
        'G': d.governing_assessment, 'R': d.regime_assessment,
        'Graph/Seed': d.graph_assessment, 'Pi': d.pi_construction,
        'Pi Completeness': d.pi_completeness, 'Constraints': d.constraints,
        'Domain Framing': d.domain_framing,
        'Joint Recovery Feasibility': d.joint_recovery_feasibility or object(),
        'Adequacy': aq,
    }
    bundle=GovernanceReusableArtifactBundle('b1','cycle-1',integrated.initial_actual_state_id,'cfg-1',tuple((s,payloads[s]) for s in p.reusable_upstream_stages),('prov-1',))
    ba=validate_reusable_artifact_bundle(p,bundle,expected_cycle_id='cycle-1',expected_initial_state_id=integrated.initial_actual_state_id,expected_configuration_id='cfg-1')
    return rt,w,t,d,p,bundle,ba


def test_sigma_reentry_executes_sigma_only_and_preserves_selected_result():
    rt,w,t,d,p,b,ba=fixture(); before=w.map_calls
    out=execute_sigma_reentry(rt,p,b,ba)
    assert out.valid and out.status=='reentry_pass_completed'
    assert out.recomputed_stage_ids==('Sigma',)
    assert out.reused_stage_ids==p.reusable_upstream_stages
    assert out.decision.selection.selected_policy_id==d.selection.selected_policy_id
    assert out.decision.stopped_at=='Sigma'
    assert w.map_calls==before and t.calls==0


def test_sigma_reentry_does_not_reproject_authoritative_q_records():
    rt,w,t,d,p,b,ba=fixture(); before=w.project_record_calls if hasattr(w,'project_record_calls') else None
    out=execute_sigma_reentry(rt,p,b,ba)
    assert out.valid
    assert out.decision.projection_records==d.projection_records
    if before is not None: assert w.project_record_calls==before


def test_sigma_reentry_rejects_wrong_boundary():
    rt,w,t,d,p,b,ba=fixture()
    sig=GovernanceInvalidationSignal('s-a','Adequacy','x','evidence')
    p2=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    out=execute_sigma_reentry(rt,p2,b,ba)
    assert not out.valid and out.status=='invalid_sigma_reentry'


def test_sigma_reentry_requires_valid_bundle_assessment():
    rt,w,t,d,p,b,ba=fixture()
    bad=GovernanceReusableArtifactBundleAssessment(False,b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,ba.reusable_stage_ids,('bad',),())
    out=execute_sigma_reentry(rt,p,b,bad)
    assert not out.valid


def test_sigma_reentry_rejects_missing_required_artifact_even_if_assessment_claimed_valid():
    rt,w,t,d,p,b,ba=fixture()
    stripped=GovernanceReusableArtifactBundle(b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,tuple(x for x in b.stage_artifacts if x[0]!='G'),b.provenance_ids)
    out=execute_sigma_reentry(rt,p,stripped,ba)
    assert not out.valid and any('omits required' in v for v in out.violations)


def test_sigma_reentry_rejects_wrong_artifact_type():
    rt,w,t,d,p,b,ba=fixture()
    arts=tuple((s,object() if s=='G' else x) for s,x in b.stage_artifacts)
    bad=GovernanceReusableArtifactBundle(b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,arts,b.provenance_ids)
    out=execute_sigma_reentry(rt,p,bad,ba)
    assert not out.valid and any('wrong type' in v for v in out.violations)


def test_sigma_reentry_rejects_fallback_path_in_v086():
    rt,w,t,d,p,b,ba=fixture()
    empty=AdequacyAssessment('none',(),(),('p',),())
    arts=tuple((s,SigmaReusableAdequacyArtifact(empty,d.projection_records) if s=='Adequacy' else x) for s,x in b.stage_artifacts)
    bad=GovernanceReusableArtifactBundle(b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,arts,b.provenance_ids)
    out=execute_sigma_reentry(rt,p,bad,ba)
    assert not out.valid and out.status=='sigma_reentry_not_executable'


def test_sigma_reentry_stops_before_epsilon_and_layer1():
    rt,w,t,d,p,b,ba=fixture()
    out=execute_sigma_reentry(rt,p,b,ba)
    assert out.valid and out.decision.pipeline_trace==('Sigma',)
    assert t.calls==0
