
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass

def build_graph_runtime():
    r=PVPPRegistry()
    r.register_domain(DomainDefinition('production','production',0.0))
    for aid in ('steady','continue','plant','maintain'):
        r.register_action(ActionDefinition(aid,aid,('production',)))
    r.register_graph_instance(GraphInstanceDefinition(
        'farm','productive_system',('production',),'active'
    ))
    r.register_graph_transformation(GraphTransformationDefinition(
        'cont','farm','farm','continuation',('production',),
        'reachable','continue',('continuation',),
        structural_effect='continue current productive operation'
    ))
    r.register_graph_transformation(GraphTransformationDefinition(
        'maintain','farm','farm','maintenance_local_adjustment',('production',),
        'reachable','maintain',('local_adjustment',),
        structural_effect='ordinary current-period maintenance'
    ))
    r.register_graph_transformation(GraphTransformationDefinition(
        'plant','farm','farm','structural_reconfiguration',('production',),
        'reachable','plant',('crop_initiation',),
        structural_effect='create delayed productive crop asset/corridor'
    ))
    return PVPPRuntime(r,W())

def preservation():
    return PreliminaryPreservationObject('p','preserve productive continuity')

def test_optional_structural_reconfiguration_remains_suppressed_in_mission():
    rt=build_graph_runtime()
    g=rt.construct_graph(
        preservation(),'Mission',('production',),
        required_family_ids=('continuation','maintenance_local_adjustment')
    )
    assert g.status=='PASS'
    plant=next(s for s in g.policy_seeds if s.id=='graph:plant')
    assert plant.family=='structural_shift'
    assert not plant.structurally_required

    pi=rt.construct_pi_from_graph(g,('continuation','local_adjustment'))
    assert pi.status=='pi_constructed'
    assert 'graph:plant' in pi.suppressed_seed_ids
    assert 'graph:plant' not in pi.emitted_candidate_ids

def test_explicit_required_structural_family_survives_mission_suppression():
    rt=build_graph_runtime()
    g=rt.construct_graph(
        preservation(),'Mission',('production',),
        required_family_ids=(
            'continuation','maintenance_local_adjustment','structural_reconfiguration'
        )
    )
    assert g.status=='PASS'
    plant=next(s for s in g.policy_seeds if s.id=='graph:plant')
    assert plant.structurally_required

    pi=rt.construct_pi_from_graph(
        g,('continuation','local_adjustment','crop_initiation')
    )
    assert pi.status=='pi_constructed'
    assert 'graph:plant' in pi.emitted_candidate_ids
    assert 'graph:plant' not in pi.suppressed_seed_ids
    candidate=next(c for c in pi.policy_space.candidates if c.id=='graph:plant')
    assert 'crop_initiation' in candidate.policy_class_ids

def test_materially_required_policy_class_alone_overrides_mission_family_shaping():
    rt=build_graph_runtime()
    g=rt.construct_graph(
        preservation(),'Mission',('production',),
        required_family_ids=('continuation','maintenance_local_adjustment')
    )
    plant=next(s for s in g.policy_seeds if s.id=='graph:plant')
    assert not plant.structurally_required

    # Upstream Pi-completeness basis says crop initiation is materially required.
    # Regime shaping must not remove the very class completeness is required to audit.
    pi=rt.construct_pi_from_graph(
        g,('continuation','local_adjustment','crop_initiation')
    )
    assert 'graph:plant' in pi.emitted_candidate_ids
    completeness=rt.validate_pi_completeness(pi.policy_space)
    assert completeness.complete
    assert 'crop_initiation' in completeness.represented_class_ids

def test_materially_required_direct_policy_seed_survives_mission_too():
    r=PVPPRegistry()
    r.register_domain(DomainDefinition('production','production',0.0))
    for aid in ('steady','continue','plant'):
        r.register_action(ActionDefinition(aid,aid,('production',)))
    r.register_policy_seed(PolicySeedDefinition(
        'continue',('continue',),'continuation',('production',),('continuation',)
    ))
    r.register_policy_seed(PolicySeedDefinition(
        'plant',('plant',),'structural_shift',('production',),('crop_initiation',),
        structurally_required=False
    ))
    rt=PVPPRuntime(r,W())
    pi=rt.construct_pi(
        'Mission',('production',),('continuation','crop_initiation')
    )
    assert 'plant' in pi.emitted_candidate_ids

def test_unrelated_optional_structural_seed_is_not_accidentally_activated():
    rt=build_graph_runtime()
    g=rt.construct_graph(
        preservation(),'Mission',('production',),
        required_family_ids=('continuation','maintenance_local_adjustment')
    )
    pi=rt.construct_pi_from_graph(g,('continuation','local_adjustment'))
    assert 'graph:plant' in pi.suppressed_seed_ids
    # Repair is narrow: Mission does not now activate structural_shift globally.
    assert all(
        c.metadata['pi_family']!='structural_shift'
        for c in pi.policy_space.candidates
    )

def test_required_graph_family_propagation_is_not_policy_preference():
    rt=build_graph_runtime()
    g=rt.construct_graph(
        preservation(),'Mission',('production',),
        required_family_ids=('continuation','structural_reconfiguration')
    )
    plant=next(s for s in g.policy_seeds if s.id=='graph:plant')
    assert plant.structurally_required
    # Required status says "must remain represented," not "must be selected."
    assert not hasattr(plant,'score')
    assert not hasattr(plant,'priority')

def test_required_path_class_marks_matching_composition_required():
    r=PVPPRegistry()
    r.register_domain(DomainDefinition('production','production',0.0))
    for aid in ('steady','continue','plant','tend'):
        r.register_action(ActionDefinition(aid,aid,('production',)))
    r.register_graph_instance(GraphInstanceDefinition(
        'farm','productive_system',('production',),'active'
    ))
    r.register_graph_transformation(GraphTransformationDefinition(
        'cont','farm','farm','continuation',('production',),'reachable',
        'continue',('continuation',)
    ))
    r.register_graph_transformation(GraphTransformationDefinition(
        'plant','farm','farm','structural_reconfiguration',('production',),'reachable',
        'plant',('crop_initiation',)
    ))
    r.register_graph_transformation(GraphTransformationDefinition(
        'tend','farm','farm','maintenance_local_adjustment',('production',),'reachable',
        'tend',('crop_maintenance',)
    ))
    r.register_graph_composition(GraphCompositionDefinition(
        'crop_start',('plant','tend'),'structural_reconfiguration',
        ('production',),('crop_corridor','seasonal_staging'),
        'creates and establishes the delayed crop corridor',
        'staged crop start is distinct from either single transformation'
    ))
    rt=PVPPRuntime(r,W())
    g=rt.construct_graph(
        preservation(),'Mission',('production',),
        required_family_ids=('continuation',),
        required_path_class_ids=('seasonal_staging',)
    )
    assert g.status=='PASS'
    staged=next(s for s in g.policy_seeds if s.id=='graphpath:crop_start')
    assert staged.structurally_required
    pi=rt.construct_pi_from_graph(
        g,('continuation','crop_corridor','seasonal_staging')
    )
    assert 'graphpath:crop_start' in pi.emitted_candidate_ids

def test_no_productive_investment_graph_family_is_added():
    rt=build_graph_runtime()
    try:
        rt.registry.register_graph_transformation(GraphTransformationDefinition(
            'investment','farm','farm','productive_investment',('production',),
            'reachable','plant',('crop_initiation',)
        ))
        assert False
    except ValueError as e:
        assert 'Unsupported graph transformation family' in str(e)

def test_required_class_does_not_rescue_malformed_seed():
    r=PVPPRegistry()
    r.register_domain(DomainDefinition('production','production',0.0))
    r.register_action(ActionDefinition('steady','steady',('production',)))
    r.register_action(ActionDefinition('continue','continue',('production',)))
    r.register_action(ActionDefinition('plant','plant',('production',)))
    r.register_policy_seed(PolicySeedDefinition(
        'continue',('continue',),'continuation',('production',),('continuation',)
    ))
    r.register_policy_seed(PolicySeedDefinition(
        'bad_plant',('plant',),'structural_shift',('production',),('crop_initiation',),
        structurally_required=False,coherent=False
    ))
    rt=PVPPRuntime(r,W())
    pi=rt.construct_pi('Mission',('production',),('continuation','crop_initiation'))
    assert 'bad_plant' in pi.malformed_seed_ids
    assert 'bad_plant' not in pi.emitted_candidate_ids
    completeness=rt.validate_pi_completeness(pi.policy_space)
    assert not completeness.complete
    assert 'crop_initiation' in completeness.missing_class_ids
