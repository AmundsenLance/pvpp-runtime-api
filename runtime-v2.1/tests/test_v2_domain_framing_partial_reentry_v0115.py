import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from test_integrated_canonical_cycle_v041 import build, req, actual


def plan():
    sig=GovernanceInvalidationSignal('sig-df','Domain Framing','framing evidence changed','evidence',('ev-df',),('old-df',))
    a=assess_governance_reentry((sig,)); return plan_governance_reentry(a,(sig,))

def fixture():
    rt,w,t=build(); r=req(); integ=rt.evaluate_integrated_canonical_cycle(actual(),r,execute=False); d=integ.decision; p=plan()
    payloads={'PPP':object(),'Phi':d.pressure_field,'H':d.horizon_assessment,'G':d.governing_assessment,'R':d.regime_assessment,'Graph/Seed':d.graph_assessment,'Pi':d.pi_construction,'Pi Completeness':d.pi_completeness,'Constraints':d.constraints}
    b=GovernanceReusableArtifactBundle('b-df','cycle-df',integ.initial_actual_state_id,'cfg-df',tuple((s,payloads[s]) for s in p.reusable_upstream_stages),('prov-df',))
    ba=validate_reusable_artifact_bundle(p,b,expected_cycle_id='cycle-df',expected_initial_state_id=integ.initial_actual_state_id,expected_configuration_id='cfg-df')
    return rt,w,t,r,d,p,b,ba

def test_domain_framing_reentry_runs_to_standard_sigma():
    rt,w,t,r,d,p,b,ba=fixture(); out=execute_domain_framing_reentry(rt,p,b,ba,actual(),r)
    assert out.valid and out.recomputed_stage_ids==('Domain Framing','Joint Recovery Feasibility','Adequacy','Sigma')
    assert out.decision.selection.selected_policy_id==d.selection.selected_policy_id

def test_domain_framing_reentry_reuses_upstream_artifacts():
    rt,w,t,r,d,p,b,ba=fixture(); out=execute_domain_framing_reentry(rt,p,b,ba,actual(),r)
    assert out.valid and out.reused_stage_ids==p.reusable_upstream_stages
    assert out.decision.governing_assessment is d.governing_assessment and out.decision.constraints is d.constraints

def test_domain_framing_reentry_rejects_wrong_boundary():
    rt,w,t,r,d,p,b,ba=fixture(); sig=GovernanceInvalidationSignal('s','Adequacy','x','evidence'); p2=plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))
    assert not execute_domain_framing_reentry(rt,p2,b,ba,actual(),r).valid

def test_domain_framing_reentry_requires_exact_bundle_scope():
    rt,w,t,r,d,p,b,ba=fixture(); bad=GovernanceReusableArtifactBundleAssessment(True,b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,('G',),(),())
    assert not execute_domain_framing_reentry(rt,p,b,bad,actual(),r).valid

def test_domain_framing_reentry_rejects_wrong_constraints_type():
    rt,w,t,r,d,p,b,ba=fixture(); arts=tuple((s,object() if s=='Constraints' else x) for s,x in b.stage_artifacts); bad=GovernanceReusableArtifactBundle(b.bundle_id,b.cycle_id,b.initial_state_id,b.configuration_id,arts,b.provenance_ids)
    assert not execute_domain_framing_reentry(rt,p,bad,ba,actual(),r).valid

def test_domain_framing_reentry_stops_before_epsilon_layer1():
    rt,w,t,r,d,p,b,ba=fixture(); out=execute_domain_framing_reentry(rt,p,b,ba,actual(),r)
    assert out.valid and out.decision.stopped_at=='Sigma' and t.calls==0

def test_epistemic_dispatch_supports_domain_framing(monkeypatch):
    import pvpp_runtime.reentry as re
    rt,w,t,r,d,p,b,ba=fixture()
    class G: valid=True; plan=p
    class O: valid=True; governance_invalidation=G()
    called={}
    real=re.execute_domain_framing_reentry
    def wrap(*args,**kwargs): called['yes']=True; return real(*args,**kwargs)
    monkeypatch.setattr(re,'execute_domain_framing_reentry',wrap)
    out=re.execute_epistemic_reentry_plan(rt,O(),bundle=b,bundle_assessment=ba,state=actual(),request=r)
    assert called.get('yes') and out.valid and out.recompute_from_stage=='Domain Framing'

def test_epistemic_domain_framing_dispatch_missing_inputs_fails_closed():
    rt,w,t,r,d,p,b,ba=fixture()
    class G: valid=True; plan=p
    class O: valid=True; governance_invalidation=G()
    out=execute_epistemic_reentry_plan(rt,O(),bundle=b,bundle_assessment=ba)
    assert not out.valid and out.execution_result is None
