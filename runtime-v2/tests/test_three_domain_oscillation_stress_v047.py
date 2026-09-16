
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime.testing import bounded_viability_oracle, analyze_sequence, classify_multidomain_stress

BENCH=ROOT/'benchmarks'
sys.path.insert(0,str(BENCH))
from three_domain_oscillation_scenario_v047 import (
    EcoState, ecology_step, viable, recovered, viability_precheck, run_runtime, THRESHOLD
)

def test_structural_feasibility_precheck_finds_viable_recovery_path():
    w=viability_precheck(12)
    assert w.feasible
    assert w.action_path
    assert recovered(w.state_path[-1])
    # The witness uses repeated same-domain repair, showing deep recovery is physically available.
    assert any(a==b for a,b in zip(w.action_path,w.action_path[1:]))

def test_oracle_is_external_ground_truth_not_runtime_selection():
    init=EcoState(0,9.0,10.0,15.0,None)
    w=bounded_viability_oracle(
        init,('seek_water','forage_food','hide_rest'),ecology_step,viable,12,
        state_key=lambda s:(s.hydration,s.energy,s.safety,s.previous_action),
        success=recovered
    )
    assert w.feasible
    # Result object contains no runtime policy/selection authorization surface.
    assert not hasattr(w,'selected_policy_id')
    assert not hasattr(w,'admissible')

def test_current_one_step_representation_enters_periodic_survival_cycle():
    final,policies,governing,margins,regimes,collapsed,rec,statuses,adequacy=run_runtime(18)
    assert not collapsed
    assert not rec
    # After the transient, a 3-policy cycle repeats.
    pd=analyze_sequence(policies)
    assert pd.strict_cycle_detected
    assert pd.repeated_period==3
    assert pd.repeated_period_repetitions>=4
    assert set(policies[-3:])=={'graph:water','graph:food','graph:hide'}
    assert set(regimes)=={'Survival'}

def test_governing_domain_rotation_is_periodic_after_transient():
    final,policies,governing,margins,regimes,collapsed,rec,statuses,adequacy=run_runtime(18)
    gd=analyze_sequence(governing)
    assert gd.strict_cycle_detected
    assert gd.repeated_period==3
    assert any(len(g)>1 for g in governing)

def test_tied_governing_set_exposes_conjunctive_adequacy_failure_then_fallback():
    final,policies,governing,margins,regimes,collapsed,rec,statuses,adequacy=run_runtime(18)
    idx=next(i for i,g in enumerate(governing) if len(g)>1)
    assert adequacy[idx]=='adequacy_no_recovery_capable_policy'
    assert statuses[idx].startswith('fallback_')
    # This is explicit recovery-unavailable handling, not a false adequacy pass.
    assert policies[idx] is not None

def test_stress_classification_distinguishes_periodicity_from_forced_ecology():
    w=viability_precheck(12)
    final,policies,governing,margins,regimes,collapsed,rec,statuses,adequacy=run_runtime(18)
    c=classify_multidomain_stress(
        structurally_feasible=w.feasible,collapsed=collapsed,recovered=rec,
        margins=margins,policies=policies,governing_sets=governing
    )
    assert c.oscillatory
    assert c.structurally_feasible
    assert c.outcome=='periodic_survival_cycling_with_viable_recovery_path'
    assert 'not a new PV-PP regime' in c.notes[0]

def test_periodicity_diagnostics_are_observational_only():
    d=analyze_sequence(('a','b','c','a','b','c','a','b','c'))
    assert d.strict_cycle_detected and d.repeated_period==3
    assert any('observational evidence only' in n for n in d.notes)

def test_forced_collapse_is_not_misattributed_to_architecture():
    init=EcoState(0,5.1,5.1,5.1,None)
    w=bounded_viability_oracle(
        init,('seek_water','forage_food','hide_rest'),ecology_step,
        lambda s:min(s.values().values())>THRESHOLD,3,
        state_key=lambda s:(s.hydration,s.energy,s.safety,s.previous_action)
    )
    assert not w.feasible
