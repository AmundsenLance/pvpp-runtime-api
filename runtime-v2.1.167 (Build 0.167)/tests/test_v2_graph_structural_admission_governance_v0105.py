from pvpp_runtime import *


def setup():
    r=PVPPRegistry(); r.register_domain(DomainDefinition('D','d',0.0))
    r.register_action(ActionDefinition('a','a',('D',)))
    r.register_graph_instance(GraphInstanceDefinition('i','unit',('D',),'s'))
    return r


def request(r, **kw):
    tr=GraphTransformationDefinition('new','i','i','continuation',('D',),'unreachable','a')
    x=dict(admission_id='adm-105', expected_graph_substrate_identity=r.graph_substrate_identity(),
           transformation=tr, configuration_version='cfg-105', source_id='configuration-authority',
           provenance_id='prov-105', rationale='approved represented mechanism', evidence={'ticket':'105'})
    x.update(kw); return GraphTransformationAdmissionRequest(**x)


def test_successful_admission_explicitly_triggers_graph_stage_reentry_plan():
    r=setup(); old=r.graph_substrate_identity(); x=admit_graph_transformation_and_plan_reentry(r,request(r))
    assert x.valid and x.admission_assessment.status=='ADMITTED'
    assert x.admission_assessment.prior_graph_substrate_identity==old
    assert x.admission_assessment.resulting_graph_substrate_identity==r.graph_substrate_identity()!=old
    assert x.invalidation_signal.invalidated_stage=='Graph/Seed'
    assert x.reentry_plan.valid and x.reentry_plan.recompute_from_stage=='Graph/Seed'


def test_admission_trigger_preserves_upstream_scope_and_invalidates_graph_downstream():
    r=setup(); x=admit_graph_transformation_and_plan_reentry(r,request(r))
    assert x.reentry_plan.reusable_upstream_stages==('PPP','Phi','H','G','R')
    assert x.reentry_plan.nonreusable_stages[0]=='Graph/Seed'
    assert 'Pi' in x.reentry_plan.nonreusable_stages and 'Sigma' in x.reentry_plan.nonreusable_stages


def test_admission_provenance_and_prior_substrate_are_explicit_in_signal():
    r=setup(); old=r.graph_substrate_identity(); x=admit_graph_transformation_and_plan_reentry(r,request(r))
    assert x.invalidation_signal.source_kind=='graph_structural_admission'
    assert x.invalidation_signal.evidence_ids==('prov-105',)
    assert x.invalidation_signal.artifact_ids==(old,)
    assert any('configuration_version=cfg-105' in n for n in x.invalidation_signal.notes)


def test_rejected_admission_creates_no_reentry_authority_and_no_mutation():
    r=setup(); old=r.graph_substrate_identity(); bad=request(r,expected_graph_substrate_identity='stale')
    x=admit_graph_transformation_and_plan_reentry(r,bad)
    assert not x.valid and x.admission_assessment.status=='REJECTED'
    assert x.invalidation_signal is None and x.reentry_plan is None
    assert r.graph_substrate_identity()==old and 'new' not in r.graph_transformations


def test_duplicate_is_not_revision_and_creates_no_second_governance_trigger():
    r=setup(); first=admit_graph_transformation_and_plan_reentry(r,request(r)); assert first.valid
    second_req=request(r,expected_graph_substrate_identity=r.graph_substrate_identity())
    second=admit_graph_transformation_and_plan_reentry(r,second_req)
    assert not second.valid and second.admission_assessment.status=='REJECTED'
    assert second.invalidation_signal is None and second.reentry_plan is None


def test_trigger_is_planning_only_and_does_not_create_execution_authority():
    r=setup(); x=admit_graph_transformation_and_plan_reentry(r,request(r))
    assert x.valid and x.reentry_plan.execute_reentry is False
    assert not hasattr(x,'execution_license') and not hasattr(x,'epsilon')
    assert not hasattr(x.admission_assessment,'execution_license')


def test_admitted_transformation_remains_unreachable_as_declared_pending_governance():
    r=setup(); x=admit_graph_transformation_and_plan_reentry(r,request(r))
    assert x.valid and r.graph_transformations['new'].reachability_status=='unreachable'
    assert x.admission_assessment.admitted_transformation_id=='new'


def test_signal_names_exact_admitted_transformation_for_traceability():
    r=setup(); x=admit_graph_transformation_and_plan_reentry(r,request(r))
    assert any('admitted_transformation_id=new' in n for n in x.invalidation_signal.notes)
