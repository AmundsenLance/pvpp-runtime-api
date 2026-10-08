import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *


def mkplan(stage='Sigma'):
    sig=GovernanceInvalidationSignal('sig',stage,'changed','evidence',('ev',),('artifact',))
    return plan_governance_reentry(assess_governance_reentry((sig,)),(sig,))


def bundle_for(plan, **kw):
    vals=dict(bundle_id='b1',cycle_id='c1',initial_state_id='s1',configuration_id='cfg1',
              stage_artifacts=tuple((s,object()) for s in plan.reusable_upstream_stages),
              provenance_ids=('prov1',))
    vals.update(kw); return GovernanceReusableArtifactBundle(**vals)


def validate(plan,b):
    return validate_reusable_artifact_bundle(plan,b,expected_cycle_id='c1',expected_initial_state_id='s1',expected_configuration_id='cfg1')


def test_exact_identity_bound_bundle_is_valid():
    p=mkplan(); a=validate(p,bundle_for(p))
    assert a.valid and a.reusable_stage_ids==p.reusable_upstream_stages


def test_cycle_identity_mismatch_fails_closed():
    p=mkplan(); a=validate(p,bundle_for(p,cycle_id='other'))
    assert not a.valid and any('cycle_id' in x for x in a.violations)


def test_state_identity_mismatch_fails_closed():
    p=mkplan(); a=validate(p,bundle_for(p,initial_state_id='other'))
    assert not a.valid and any('initial_state_id' in x for x in a.violations)


def test_configuration_identity_mismatch_fails_closed():
    p=mkplan(); a=validate(p,bundle_for(p,configuration_id='other'))
    assert not a.valid and any('configuration_id' in x for x in a.violations)


def test_missing_reusable_stage_fails_closed():
    p=mkplan(); arts=tuple((s,object()) for s in p.reusable_upstream_stages[:-1])
    assert not validate(p,bundle_for(p,stage_artifacts=arts)).valid


def test_extra_or_reordered_stage_fails_closed():
    p=mkplan(); arts=tuple(reversed(tuple((s,object()) for s in p.reusable_upstream_stages)))
    assert not validate(p,bundle_for(p,stage_artifacts=arts)).valid


def test_missing_payload_and_duplicate_provenance_fail_closed():
    p=mkplan(); arts=list((s,object()) for s in p.reusable_upstream_stages); arts[0]=(arts[0][0],None)
    a=validate(p,bundle_for(p,stage_artifacts=tuple(arts),provenance_ids=('x','x')))
    assert not a.valid and len(a.violations)>=2


def test_ppp_plan_requires_empty_reuse_bundle_and_executes_nothing():
    p=mkplan('PPP'); b=bundle_for(p,stage_artifacts=())
    a=validate(p,b)
    assert a.valid and a.reusable_stage_ids==()
    assert not hasattr(a,'decision') and not hasattr(a,'recomputed_cycle')
