"""Locks the four Chapter 6 behaviors of the coffee decision cycle."""
from coffee_decision import decide, WorldState, make_runtime, request

def test_sells_when_cups_available():
    c = decide(cups=12)
    assert c.selection.selected_policy_id == "graph:sell"

def test_adequacy_rejects_sale_without_cups():
    c = decide(cups=0)
    assert c.adequacy.inadequate_policy_ids == ("graph:sell",)
    assert c.selection.selected_policy_id == "graph:decline"

def test_constraints_remove_sale_when_network_down():
    c = decide(cups=12, network_up=False)
    assert "graph:sell" in c.constraints.infeasible_policy_ids
    assert c.selection.selected_policy_id == "graph:decline"

def test_missing_exit_family_stops_at_graph():
    c = decide(cups=12, include_exit=False)
    assert c.stopped_at == "Graph/Seed" and "G-002" in c.graph_assessment.failure_codes
    assert c.selection is None

def test_cycle_does_not_mutate_host_state():
    state = WorldState(0, {"D": 10.0, "T": 10.0}, {"cups": 12, "network_up": True})
    before = repr(state)
    make_runtime().evaluate_canonical_decision_cycle(state, request())
    assert repr(state) == before
