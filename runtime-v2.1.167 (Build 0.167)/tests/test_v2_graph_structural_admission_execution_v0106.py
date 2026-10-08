from pvpp_runtime import *
from test_v2_graph_reentry_v094 import setup_case
from test_concurrent_recovery_execution_binding_v055 import state


def case():
    rt,w,ts,req,original,plan,b,ba,gi,pi=setup_case()
    did=next(iter(rt.registry.domains)); aid=next(a for a in rt.registry.actions if a!='steady'); inst=next(iter(rt.registry.graph_instances))
    tr=GraphTransformationDefinition('new106',inst,inst,'continuation',(did,),'unreachable',aid)
    ar=GraphTransformationAdmissionRequest('adm-106',rt.registry.graph_substrate_identity(),tr,'cfg-106','configuration-authority','prov-106','approved represented mechanism',{'ticket':'106'})
    trigger=admit_graph_transformation_and_plan_reentry(rt.registry,ar)
    return rt,w,ts,req,b,ba,gi,pi,trigger


def test_admission_executes_existing_graph_downstream_path():
    rt,w,ts,req,b,ba,gi,pi,tr=case(); c=len(w.constraint_calls); q=len(w.q_calls)
    x=execute_graph_structural_admission_reentry(rt,tr,b,ba,state(),req,gi,pi)
    assert x.valid and x.status=='reentry_pass_completed'
    assert x.recomputed_stage_ids[0:3]==('Graph/Seed','Pi','Pi Completeness')
    assert len(w.constraint_calls)>c and len(w.q_calls)>q and len(ts.handoffs)==0


def test_pre_admission_graph_input_identity_is_required():
    rt,w,ts,req,b,ba,gi,pi,tr=case()
    bad=GraphReusableConstructionInputs(gi.preservation_object,gi.required_graph_family_ids,gi.required_graph_path_class_ids,gi.graph_config,'wrong')
    x=execute_graph_structural_admission_reentry(rt,tr,b,ba,state(),req,bad,pi)
    assert not x.valid and any('pre-admission' in v for v in x.violations)


def test_post_admission_registry_mutation_fails_closed():
    rt,w,ts,req,b,ba,gi,pi,tr=case(); did=next(iter(rt.registry.domains))
    rt.registry.register_graph_instance(GraphInstanceDefinition('late106','thing',(did,),'available'))
    x=execute_graph_structural_admission_reentry(rt,tr,b,ba,state(),req,gi,pi)
    assert not x.valid and any('no longer matches' in v for v in x.violations)


def test_rejected_admission_trigger_cannot_execute():
    rt,w,ts,req,original,plan,b,ba,gi,pi=setup_case(); did=next(iter(rt.registry.domains)); aid=next(a for a in rt.registry.actions if a!='steady'); inst=next(iter(rt.registry.graph_instances))
    trdef=GraphTransformationDefinition('bad106',inst,inst,'continuation',(did,),'unreachable',aid)
    ar=GraphTransformationAdmissionRequest('bad-adm','stale',trdef,'cfg','source','prov','reason',{})
    tr=admit_graph_transformation_and_plan_reentry(rt.registry,ar)
    x=execute_graph_structural_admission_reentry(rt,tr,b,ba,state(),req,gi,pi)
    assert not x.valid and 'bad106' not in rt.registry.graph_transformations


def test_bridge_preserves_graph_and_pi_declarations():
    rt,w,ts,req,b,ba,gi,pi,tr=case(); before=(gi.preservation_object,gi.required_graph_family_ids,gi.required_graph_path_class_ids,gi.graph_config,pi)
    x=execute_graph_structural_admission_reentry(rt,tr,b,ba,state(),req,gi,pi)
    assert x.valid and before==(gi.preservation_object,gi.required_graph_family_ids,gi.required_graph_path_class_ids,gi.graph_config,pi)


def test_admitted_definition_is_preserved_exactly_through_reentry():
    rt,w,ts,req,b,ba,gi,pi,tr=case(); before=rt.registry.graph_transformations['new106']
    x=execute_graph_structural_admission_reentry(rt,tr,b,ba,state(),req,gi,pi)
    assert x.valid and rt.registry.graph_transformations['new106']==before
    assert tr.admission_assessment.configuration_version=='cfg-106' and tr.admission_assessment.provenance_id=='prov-106'


def test_execution_stays_before_epsilon_and_layer1():
    rt,w,ts,req,b,ba,gi,pi,tr=case(); x=execute_graph_structural_admission_reentry(rt,tr,b,ba,state(),req,gi,pi)
    assert x.valid and 'epsilon' not in x.recomputed_stage_ids and len(ts.handoffs)==0
    assert any('granted no execution authority' in n for n in x.notes)
