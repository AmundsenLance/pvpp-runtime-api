"""Locks the Chapter 10 behaviors of the operations-agent example."""
import pytest
from agent_ops import OpsAgent, Service, request, run_shift
from pvpp_runtime import ExecutionBindingIdentity


@pytest.fixture
def shift(capsys):
    out, agent = run_shift()
    capsys.readouterr()
    return dict(out), agent


def pick(r): return r["selected"].split(":")[1]


def test_each_episode_is_decided_where_expected(shift):
    out, _ = shift
    assert [pick(r) for r in out.values()] == [
        "restart", "escalate", "escalate", "failover", "escalate", "reconfigure"]


def test_hotfix_is_never_adequate_because_it_destroys_control(shift):
    out, _ = shift
    for r in out.values():
        assert "hotfix: inadequate" in r["why"] or "hotfix: change_freeze" in r["why"] \
            or "hotfix: write_credential" in r["why"]


def test_refresh_adds_the_route_to_the_graph(shift):
    out, _ = shift
    assert "graph:failover" not in out["2 bad config"]["graph"]
    assert "graph:failover" in out["3 route reachable, freeze on"]["graph"]


def test_reachable_is_not_permitted(shift):
    out, _ = shift
    assert "failover: change_freeze" in out["3 route reachable, freeze on"]["why"]


def test_revoked_credential_withdraws_authority_before_the_call(shift):
    out, agent = shift
    assert out["4 freeze lifted, credential revoked"]["withdrawn"] is True
    assert "failover" not in agent.svc.calls


def test_unadmitted_tool_cannot_be_bound():
    svc = Service(); agent = OpsAgent(svc)
    with pytest.raises(ValueError):
        agent.bindings.register(ExecutionBindingIdentity("reconfigure-v1", "reconfigure", "1.0"),
                                svc.reconfigure)


def test_admitted_tool_is_governed_like_any_other(shift):
    out, agent = shift
    assert pick(out["5 tool admitted"]) == "reconfigure" and agent.facts["healthy"] is True


def test_mission_regime_does_not_activate_the_substitution_family():
    svc = Service(); agent = OpsAgent(svc)
    agent.scanner_reports("failover", "reachable", "net-scanner")
    agent.record("service healthy", healthy=True)
    cycle = agent.rt.evaluate_integrated_canonical_cycle(agent.actual(), request()).decision
    assert cycle.regime_assessment.regime == "Mission"
    assert "graph:failover" in cycle.pi_construction.suppressed_seed_ids
