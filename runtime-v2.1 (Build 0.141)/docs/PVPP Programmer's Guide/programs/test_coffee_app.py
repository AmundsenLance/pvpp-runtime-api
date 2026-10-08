"""Locks the Chapter 8 application behaviors of the coffee example."""
import pytest
from coffee_app import CoffeeAdapter, Store, run_day


@pytest.fixture
def day(tmp_path, capsys):
    out, store = run_day(str(tmp_path / "state.json"))
    capsys.readouterr()
    return dict(out), store, tmp_path / "state.json"


def test_each_episode_is_decided_where_expected(day):
    out, _, _ = day
    picks = {k: v["selected"].split(":")[1] for k, v in out.items()}
    assert picks == {"1 buyer": "sell", "2 buyer, capture lost": "sell",
                     "3 buyer, capture open": "decline", "4 buyer, after settle": "sell",
                     "5 buyer, no cup": "sell", "6 next episode": "refund",
                     "7 buyer, network fails": "sell", "7' buyer, re-decided": "decline",
                     "8 buyer, network back": "sell", "9 buyer, monitor silent": "decline"}


def test_unknown_capture_blocks_new_sales_at_constraints(day):
    out, _, _ = day
    assert out["2 buyer, capture lost"]["native"] == "indeterminate"
    assert "sell: reconciliation_hold" in out["3 buyer, capture open"]["why"]


def test_refund_is_chosen_by_adequacy_not_by_host_code(day):
    out, _, _ = day
    assert out["5 buyer, no cup"]["native"] == "completed_invalid"
    assert out["6 next episode"]["why"] == "sell: inadequate | decline: inadequate"


def test_report_during_authorization_withdraws_authority_before_the_call(day):
    out, store, _ = day
    assert out["7 buyer, network fails"]["withdrawn"] == "Constraints"
    whys = [e["why"] for e in store.s["log"]]
    i = whys.index("network report: down")
    assert whys[i - 1] == "graph:refund: completed"      # no transition from the withdrawn sale


def test_stale_evidence_is_not_current_evidence(day):
    out, store, _ = day
    p = CoffeeAdapter().perceived_decision_state_from_actual(store.envelope())
    assert p.represented_state.metadata["network"] == "unknown"
    assert "sell: card_network" in out["9 buyer, monitor silent"]["why"]


def test_state_persists_between_runs(day):
    _, store, path = day
    again = Store(str(path))
    assert again.envelope() == store.envelope()
    assert (again.s["cups"], again.s["revenue"], again.s["refunds_owed"]) == (7, 10.0, 0)


def test_prior_transition_provenance_is_checked_when_state_is_unchanged(day):
    out, _, _ = day
    assert out["2 buyer, capture lost"]["provenance_checked"] is True
    assert out["4 buyer, after settle"]["provenance_checked"] is False   # a report intervened
