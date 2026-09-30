"""Locks the Chapter 7 execution behaviors of the coffee example."""
from coffee_execute import CoffeeMachine, purchase, start


def run(fault=None, **kw):
    m = CoffeeMachine(fault=fault)
    return m, purchase(m, start(m), **kw)


def test_success_completes_and_layer1_records_the_sale():
    m, out = run()
    assert (out["native"], out["epsilon"], out["return_upstream"]) == ("succeeded", "completed", False)
    assert out["actual"].context["cups"] == 11 and out["actual"].spv["revenue_captured"] == 2.50


def test_authorization_is_single_use():
    _, out = run()
    assert out["reuse"] == "refused" and out["calls"] == 1


def test_clean_failure_changes_nothing_material():
    _, out = run("card_declined")
    assert (out["native"], out["epsilon"], out["return_upstream"]) == ("failed_cleanly", "failed", True)
    assert out["actual"].context["cups"] == 12 and out["actual"].avs["unresolved_buyers"] == 0


def test_unknown_effect_is_indeterminate_not_failure():
    _, out = run("capture_timeout")
    assert out["native"] == "indeterminate" and out["epsilon"] == "partial_realization"
    assert out["return_upstream"] is True
    assert "reconcile capture" in out["actual"].context["open_items"]


def test_completed_but_invalid_returns_upstream_with_refund_owed():
    _, out = run("no_delivery")
    assert out["native"] == "completed_invalid" and out["return_upstream"] is True
    assert "refund owed: charged, not served" in out["actual"].context["open_items"]


def test_stale_authority_is_refused_before_the_function_runs():
    m, out = run(stale_before_call=True)
    assert "invalidated" in out["refused"] and out["calls"] == 0 and m.cups == 12


def test_next_cycle_from_updated_facts_declines():
    m = CoffeeMachine()
    purchase(m, start(m), stale_before_call=True)
    out = purchase(m, start(m))
    assert out["selected"] == "graph:decline" and out["epsilon"] == "completed"
