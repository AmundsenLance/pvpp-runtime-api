from pvpp_runtime import *
from pvpp_runtime.models import DomainDefinition, ActionDefinition, GraphInstanceDefinition, GraphTransformationDefinition
from pvpp_runtime.registry import PVPPRegistry


def setup():
    r=PVPPRegistry(); r.register_domain(DomainDefinition('D','d',0))
    r.register_action(ActionDefinition('steady','steady',('D',))); r.register_action(ActionDefinition('a','a',('D',)))
    r.register_graph_instance(GraphInstanceDefinition('i','thing',('D',),'ok'))
    r.register_graph_transformation(GraphTransformationDefinition('t','i','i','continuation',('D',),'unreachable','a'))
    return r


def obs(status='reachable', tid='t', provenance='prov-102'):
    return GraphReachabilityObservation(tid,status,2.0,'reachability-sensor',provenance,'',{'v':102})


def req(r, observations, rid='refresh-102'):
    return GraphReachabilityRefreshRequest(r.graph_substrate_identity(),tuple(observations),rid)


def test_material_refresh_explicitly_triggers_graph_stage_reentry_plan():
    r=setup(); old=r.graph_substrate_identity()
    x=refresh_graph_reachability_and_plan_reentry(r,req(r,(obs(),)))
    assert x.valid and x.refresh_assessment.status=='APPLIED'
    assert x.refresh_assessment.resulting_graph_substrate_identity != old
    assert x.invalidation_signal.invalidated_stage=='Graph/Seed'
    assert x.reentry_assessment.recompute_from_stage=='Graph/Seed'
    assert x.reentry_plan.valid and x.reentry_plan.recompute_from_stage=='Graph/Seed'


def test_trigger_preserves_reusable_upstream_scope_and_invalidates_graph_downstream():
    r=setup(); x=refresh_graph_reachability_and_plan_reentry(r,req(r,(obs(),)))
    assert x.reentry_plan.reusable_upstream_stages==('PPP','Phi','H','G','R')
    assert x.reentry_plan.nonreusable_stages[0]=='Graph/Seed'
    assert 'Pi' in x.reentry_plan.nonreusable_stages and 'Sigma' in x.reentry_plan.nonreusable_stages


def test_trigger_carries_changed_observation_provenance_as_evidence_identity():
    r=setup(); x=refresh_graph_reachability_and_plan_reentry(r,req(r,(obs(provenance='p-a'),)))
    assert x.invalidation_signal.evidence_ids==('p-a',)
    assert x.invalidation_signal.source_kind=='graph_reachability_refresh'
    assert x.invalidation_signal.artifact_ids==(x.refresh_assessment.prior_graph_substrate_identity,)


def test_noop_refresh_does_not_invent_invalidation_or_reentry():
    r=setup(); x=refresh_graph_reachability_and_plan_reentry(r,req(r,(obs('unreachable'),),'noop-102'))
    assert x.valid and x.refresh_assessment.status=='APPLIED'
    assert x.refresh_assessment.changed_transformation_ids==()
    assert x.invalidation_signal is None and x.reentry_assessment is None and x.reentry_plan is None


def test_rejected_refresh_creates_no_reentry_authority():
    r=setup(); bad=GraphReachabilityRefreshRequest('stale',(obs(),),'bad-102')
    x=refresh_graph_reachability_and_plan_reentry(r,bad)
    assert not x.valid and x.refresh_assessment.status=='REJECTED'
    assert x.invalidation_signal is None and x.reentry_plan is None
    assert r.graph_transformations['t'].reachability_status=='unreachable'


def test_unknown_transformation_remains_structural_admission_boundary():
    r=setup(); before=r.graph_substrate_identity()
    x=refresh_graph_reachability_and_plan_reentry(r,req(r,(obs(tid='novel'),),'novel-102'))
    assert not x.valid and x.invalidation_signal is None
    assert r.graph_substrate_identity()==before and 'novel' not in r.graph_transformations


def test_multiple_changed_observations_deduplicate_provenance_evidence():
    r=setup()
    r.register_graph_transformation(GraphTransformationDefinition('t2','i','i','continuation',('D',),'unreachable','a'))
    x=refresh_graph_reachability_and_plan_reentry(r,req(r,(obs(tid='t',provenance='same'),obs(tid='t2',provenance='same')),'multi-102'))
    assert x.valid and set(x.refresh_assessment.changed_transformation_ids)=={'t','t2'}
    assert x.invalidation_signal.evidence_ids==('same',)


def test_trigger_is_planning_only_and_does_not_construct_graph_or_pi():
    r=setup(); before=set(r.graph_instances),set(r.graph_transformations)
    x=refresh_graph_reachability_and_plan_reentry(r,req(r,(obs(),),'plan-only-102'))
    assert x.valid and x.reentry_plan.execute_reentry is False
    assert set(r.graph_instances)==before[0] and set(r.graph_transformations)==before[1]
