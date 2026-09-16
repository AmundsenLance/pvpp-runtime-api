import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples" / "tiny_food_world"))

from run_food import build_runtime, initial_state


def test_pipeline_order_is_explicit():
    rt = build_runtime()
    a = rt.assess(initial_state())
    assert a.pipeline_trace == (
        "PPP", "Phi", "H", "G", "R", "Graph/Seed", "Pi", "Pi Completeness",
        "Constraints", "Domain Framing", "Adequacy", "Sigma", "epsilon"
    )


def test_productive_powers_are_registered_and_state_is_named():
    rt = build_runtime()
    assert set(rt.registry.powers) == {"food_stock", "labor_available"}
    state = initial_state()
    assert state.power_value("food_stock") == 30.0
    assert state.powers["labor_available"].executable_value == 10.0


def test_baseline_is_derived_from_registered_steady_policy():
    rt = build_runtime()
    state = initial_state()
    assert not hasattr(rt.world, "baseline_drift")
    a = rt.assess(state)
    assert a.domains["F"].horizon == 2.5


def test_food_pressure_makes_f_governing():
    rt = build_runtime()
    a = rt.assess(initial_state())
    assert "F" in a.governing_domains
    assert a.domains["F"].horizon == 2.5


def test_steady_is_inadequate_and_gather_is_selected():
    rt = build_runtime()
    a = rt.decide(initial_state())
    assert a.steady_adequate is False
    assert a.selected_action == "gather_food"


def test_host_executes_selected_action_and_state_changes():
    rt = build_runtime()
    state = initial_state()
    a = rt.decide(state)
    result = rt.world.execute(state, a.selected_action)
    new_state = result.next_state
    assert new_state.power_value("food_stock") == 38.0
    assert new_state.power_value("labor_available") == 6.0
    assert state.power_value("food_stock") == 30.0


def test_external_proposal_can_be_evaluated():
    rt = build_runtime()
    ev = rt.evaluate_proposal(initial_state(), "rest")
    assert ev.feasible is True
    assert ev.adequate is False


def test_constraint_blocks_gather_without_labor():
    rt = build_runtime()
    ev = rt.evaluate_proposal(initial_state(labor=2.0), "gather_food")
    assert ev.feasible is False
    assert "requires 4 labor units" in ev.reasons
