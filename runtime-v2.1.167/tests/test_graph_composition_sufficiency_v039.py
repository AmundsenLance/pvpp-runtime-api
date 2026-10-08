
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass

def base_runtime():
    r=PVPPRegistry()
    r.register_domain(DomainDefinition('Income','income',0))
    r.register_domain(DomainDefinition('Transport','transport',0))
    r.register_action(ActionDefinition('steady','steady',('Income','Transport')))
    for aid in ('transit','tempjob','save','buycar','betterjob','continue'):
        r.register_action(ActionDefinition(aid,aid,('Income','Transport')))
    for iid in ('s0','s1','s2','s3','s4','s5'):
        r.register_graph_instance(GraphInstanceDefinition(iid,'state',('Income','Transport'),'available'))
    trs=(
        GraphTransformationDefinition('t0','s0','s0','continuation',('Income','Transport'),'reachable','continue',('continuation',),structural_effect='remain'),
        GraphTransformationDefinition('t1','s0','s1','structural_reconfiguration',('Transport',),'reachable','transit',('staged_recovery',),structural_effect='obtain transit access'),
        GraphTransformationDefinition('t2','s1','s2','structural_reconfiguration',('Income',),'reachable','tempjob',('staged_recovery',),structural_effect='temporary income'),
        GraphTransformationDefinition('t3','s2','s3','maintenance_local_adjustment',('Income',),'reachable','save',('staged_recovery',),structural_effect='accumulate reserve'),
        GraphTransformationDefinition('t4','s3','s4','substitution',('Transport',),'reachable','buycar',('staged_recovery',),structural_effect='restore transport'),
        GraphTransformationDefinition('t5','s4','s5','structural_reconfiguration',('Income',),'reachable','betterjob',('staged_recovery',),structural_effect='access stronger income'),
    )
    for t in trs: r.register_graph_transformation(t)
    return PVPPRuntime(r,W())

def po():
    return PreliminaryPreservationObject('life','preserve income and transportation function')

def test_required_staged_path_fails_when_only_single_steps_exist():
    rt=base_runtime()
    g=rt.construct_graph(po(),'Survival',('Income','Transport'),
                         required_family_ids=('continuation',),
                         required_path_class_ids=('staged_recovery',),
                         config=GraphConstructionConfig(max_seeds=64))
    assert g.status=='FAIL'
    assert 'G-005' in g.failure_codes
    assert g.missing_required_path_class_ids==('staged_recovery',)
    assert g.composition_ids==()

def test_explicit_multistep_composition_satisfies_required_path_class():
    rt=base_runtime()
    rt.registry.register_graph_composition(GraphCompositionDefinition(
        'recovery',('t1','t2','t3','t4','t5'),'structural_reconfiguration',
        ('Income','Transport'),('staged_recovery',),
        recovery_relevance='staged path restores transportation then access to stronger income',
        distinctness_justification='direct job acquisition and immediate vehicle purchase are unavailable',
        structurally_required=True
    ))
    g=rt.construct_graph(po(),'Survival',('Income','Transport'),
                         required_family_ids=('continuation',),
                         required_path_class_ids=('staged_recovery',),
                         config=GraphConstructionConfig(max_seeds=64))
    assert g.status=='PASS'
    assert g.missing_required_path_class_ids==()
    assert g.invalid_composition_ids==()
    assert g.composition_ids==('recovery',)
    staged=[s for s in g.policy_seeds if s.path_type=='staged']
    assert len(staged)==1
    assert staged[0].source_ids==('t1','t2','t3','t4','t5')

def test_one_step_composition_cannot_fake_staging():
    rt=base_runtime()
    rt.registry.register_graph_composition(GraphCompositionDefinition(
        'fake',('t1',),'structural_reconfiguration',('Transport',),('staged_recovery',),
        recovery_relevance='claims staging',distinctness_justification='claims distinct'
    ))
    g=rt.construct_graph(po(),'Survival',('Income','Transport'),
                         required_path_class_ids=('staged_recovery',))
    assert g.status=='FAIL'
    assert g.invalid_composition_ids==('fake',)
    assert g.missing_required_path_class_ids==('staged_recovery',)
    assert 'G-005' in g.failure_codes

def test_composition_requires_recovery_relevance_and_distinctness_record():
    rt=base_runtime()
    rt.registry.register_graph_composition(GraphCompositionDefinition(
        'weak',('t1','t2'),'structural_reconfiguration',('Income','Transport'),
        ('staged_recovery',),recovery_relevance='',distinctness_justification=''
    ))
    g=rt.construct_graph(po(),'Survival',('Income','Transport'),
                         required_path_class_ids=('staged_recovery',))
    assert g.status=='FAIL'
    assert g.invalid_composition_ids==('weak',)
    assert g.missing_required_path_class_ids==('staged_recovery',)

def test_noncontiguous_composition_fails():
    rt=base_runtime()
    rt.registry.register_graph_composition(GraphCompositionDefinition(
        'broken',('t1','t3'),'structural_reconfiguration',('Income','Transport'),
        ('staged_recovery',),recovery_relevance='staged recovery',
        distinctness_justification='sequential staging matters'
    ))
    g=rt.construct_graph(po(),'Survival',('Income','Transport'),
                         required_path_class_ids=('staged_recovery',))
    assert g.status=='FAIL'
    assert g.invalid_composition_ids==('broken',)

def test_unreachable_step_invalidates_whole_composition():
    rt=base_runtime()
    # replace t2 in-place only for the injected structural defect
    rt.registry.graph_transformations['t2']=GraphTransformationDefinition(
        't2','s1','s2','structural_reconfiguration',('Income',),'unreachable','tempjob',
        ('staged_recovery',),structural_effect='temporary income'
    )
    rt.registry.register_graph_composition(GraphCompositionDefinition(
        'blocked',('t1','t2'),'structural_reconfiguration',('Income','Transport'),
        ('staged_recovery',),recovery_relevance='staged recovery',
        distinctness_justification='sequential staging matters'
    ))
    g=rt.construct_graph(po(),'Survival',('Income','Transport'),
                         required_path_class_ids=('staged_recovery',))
    assert g.status=='FAIL'
    assert g.invalid_composition_ids==('blocked',)

def test_runtime_does_not_invent_general_graph_search_or_depth_limit():
    rt=base_runtime()
    g=rt.construct_graph(po(),'Survival',('Income','Transport'))
    assert all(s.path_type!='staged' for s in g.policy_seeds)
    assert any('does not invent a general path-depth limit' in n for n in g.notes)
