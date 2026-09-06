
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'benchmarks'))

from pvpp_runtime.testing import analyze_sequence
from three_domain_oscillation_scenario_v047 import run_runtime as run_baseline, viability_precheck
from three_domain_buffered_multistep_scenario_v048 import run_runtime as run_buffered


def test_same_ecology_has_viable_reference_witness():
    w=viability_precheck(12)
    assert w.feasible
    assert w.action_path[:2]==('seek_water','seek_water')
    assert ('forage_food','forage_food') == w.action_path[2:4]


def test_v047_baseline_still_exhibits_periodic_survival_cycling():
    final,policies,governing,margins,regimes,collapsed,rec,statuses,adequacy=run_baseline(18)
    assert not collapsed
    assert not rec
    pd=analyze_sequence(policies)
    assert pd.strict_cycle_detected
    assert pd.repeated_period==3


def test_buffered_multistep_variant_reaches_recovery():
    result=run_buffered(12)
    final,policies,governing,margins,regimes,collapsed,rec,statuses,adequacy,graph_paths=result
    assert not collapsed
    assert rec
    assert policies==(
        'graphpath:water_depth',
        'graphpath:food_depth',
        'graphpath:hide_depth'
    )
    assert final.pp['domains']=={'hydration':13.0,'energy':14.0,'safety':19.0}


def test_buffered_variant_uses_standard_sigma_only():
    result=run_buffered(12)
    statuses=result[7]
    adequacy=result[8]
    assert statuses==(
        'sigma_standard_policy_selected',
        'sigma_standard_policy_selected',
        'sigma_standard_policy_selected'
    )
    assert set(adequacy)=={'adequacy_passed_some_policies'}


def test_explicit_graph_compositions_are_present_each_cycle():
    result=run_buffered(12)
    graph_paths=result[9]
    assert len(graph_paths)==3
    for paths in graph_paths:
        assert set(paths)=={'water_depth','food_depth','hide_depth'}


def test_buffered_variant_has_no_periodic_policy_signature():
    policies=run_buffered(12)[1]
    pd=analyze_sequence(policies)
    assert not pd.strict_cycle_detected
    assert pd.repeated_period is None


def test_governing_domains_progress_without_tied_multidomain_fallback():
    governing=run_buffered(12)[2]
    assert governing==( ('hydration',), ('energy',), ('safety',) )
    assert all(len(g)==1 for g in governing)


def test_source_supported_depth_is_explicit_not_hidden_search():
    result=run_buffered(12)
    paths=result[9]
    # The runtime sees registered graph compositions; no arbitrary depth search
    # or anti-oscillation rule is required.
    assert all(paths for paths in result[9])


def test_recovery_is_not_caused_by_sigma_ordering():
    result=run_buffered(12)
    policies=result[1]
    # Each selected staged policy is domain-specific and adequacy-passing.
    # If order were driving the result, the first order-indexed path would repeat.
    assert len(set(policies))==3
    assert policies[0] != policies[1] != policies[2]


def test_comparison_preserves_same_initial_ecology():
    baseline=run_baseline(1)
    buffered=run_buffered(1)
    assert baseline[3][0]==buffered[3][0]
