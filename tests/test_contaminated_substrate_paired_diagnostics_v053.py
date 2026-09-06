
import sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import compare_contaminated_substrate_cycles

def cycle(classes, seeds, complete=True, adequate=(), selected=None, governing=('G',)):
    candidates=tuple(SimpleNamespace(policy_class_ids=(c,)) for c in classes)
    pi=SimpleNamespace(policy_space=SimpleNamespace(candidates=candidates))
    graph=SimpleNamespace(policy_seeds=tuple(SimpleNamespace(id=s,visible=True) for s in seeds))
    return SimpleNamespace(
        pi_construction=pi,graph_assessment=graph,
        pi_completeness=SimpleNamespace(complete=complete),
        adequacy=SimpleNamespace(adequate_policy_ids=tuple(adequate)),
        selection=SimpleNamespace(selected_policy_id=selected),
        governing_assessment=SimpleNamespace(governing_domain_ids=tuple(governing))
    )

def test_test006_material_omission_plus_passed_completeness_is_flagged():
    ref=cycle(('continuation','sale_stabilize'),('cont','sale'),True,('sale',),'sale')
    con=cycle(('continuation',),('cont',),True,('cont',),'cont')
    a=compare_contaminated_substrate_cycles(
        ref,con,materially_relevant_reference_class_ids=('sale_stabilize',)
    )
    assert a.status=='material_omission_with_apparent_completeness'
    assert a.omitted_reference_class_ids==('sale_stabilize',)
    assert a.omitted_graph_seed_ids==('sale',)
    assert a.apparent_completeness_laundering

def test_nonmaterial_difference_is_not_called_laundering():
    ref=cycle(('continuation','optional'),('cont','opt'),True)
    con=cycle(('continuation',),('cont',),True)
    a=compare_contaminated_substrate_cycles(ref,con)
    assert a.status=='contaminated_omission_observed'
    assert not a.apparent_completeness_laundering

def test_test007_extra_structure_is_observed_without_declaring_fabrication():
    ref=cycle(('continuation',),('cont',),True)
    con=cycle(('continuation','fake_help'),('cont','help'),True)
    a=compare_contaminated_substrate_cycles(ref,con)
    assert a.status=='contaminated_extra_structure_observed'
    assert a.extra_contaminated_class_ids==('fake_help',)
    assert a.extra_graph_seed_ids==('help',)
    assert all('fabrication' not in n.lower() or 'licensing' in n.lower() for n in a.notes)

def test_downstream_selection_divergence_is_visible():
    ref=cycle(('continuation',),('cont',),True,('p1',),'p1')
    con=cycle(('continuation',),('cont',),True,('p2',),'p2')
    a=compare_contaminated_substrate_cycles(ref,con)
    assert a.status=='downstream_epistemic_divergence_observed'
    assert a.selection_diverged

def test_governing_and_adequacy_divergence_are_separate_flags():
    ref=cycle(('continuation',),('cont',),True,('p1',),'p1',('A',))
    con=cycle(('continuation',),('cont',),True,(),'p1',('B',))
    a=compare_contaminated_substrate_cycles(ref,con)
    assert a.governing_diverged
    assert a.adequacy_diverged
    assert not a.selection_diverged

def test_no_difference_reports_clean_observation():
    ref=cycle(('continuation',),('cont',),True,('p1',),'p1')
    con=cycle(('continuation',),('cont',),True,('p1',),'p1')
    a=compare_contaminated_substrate_cycles(ref,con)
    assert a.status=='no_structural_or_downstream_divergence_observed'
    assert not a.apparent_completeness_laundering

def test_diagnostic_output_has_no_policy_or_runtime_mutation_surface():
    ref=cycle(('continuation','sale_stabilize'),('cont','sale'),True)
    con=cycle(('continuation',),('cont',),True)
    a=compare_contaminated_substrate_cycles(ref,con,materially_relevant_reference_class_ids=('sale_stabilize',))
    for forbidden in ('selected_policy','candidate_override','graph_override','repair','feasible'):
        assert not hasattr(a,forbidden)
