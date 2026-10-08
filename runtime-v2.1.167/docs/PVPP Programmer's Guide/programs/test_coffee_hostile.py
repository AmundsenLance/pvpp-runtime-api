"""Chapter 9 test suite for the coffee application: boundaries, hostile cases,
metamorphic checks, regression, and runtime identity.

The Chapter 8 tests show the application does what it should. These tests try to
make it do what it must not, and check that the violation is either impossible or
visible.
"""
import dataclasses, hashlib, pathlib
import pytest
import coffee_app as app_mod        # first: it puts the runtime on the import path
from coffee_app import CoffeeProjection, CoffeeApp, Machine, Store, request, run_day
import pvpp_runtime

HERE = pathlib.Path(__file__).parent

def fresh(tmp_path, machine=None):
    m = machine or Machine()
    s = Store(str(tmp_path / "state.json"))
    return m, s, CoffeeApp(m, s)

# ---------------------------------------------------------------- category boundaries
def false_success(out, cups_before, cups_after):
    """Visible success with no realized effect: a sale that 'succeeded' but served nobody."""
    return (out.get("native") == "succeeded" and out["selected"] == "graph:sell"
            and cups_after == cups_before)

class HollowMachine(Machine):
    def sell(self, context):                  # returns normally and does nothing
        return {"receipt": context.execution_id}

def test_returned_is_not_realized(tmp_path):
    _, s, app = fresh(tmp_path, HollowMachine())
    out = app.episode()
    assert out["native"] == "succeeded"
    assert (s.s["cups"], s.s["revenue"]) == (12, 0.0)     # state follows evidence
    assert false_success(out, 12, s.s["cups"])            # and the trace exposes it

def test_ordinary_sale_is_not_flagged(tmp_path):
    _, s, app = fresh(tmp_path)
    assert not false_success(app.episode(), 12, s.s["cups"])

class CrashingMachine(Machine):
    def sell(self, context):
        self.cups -= 1                        # the effect happens ...
        raise RuntimeError("controller fault")  # ... then an unanticipated error

def test_unanticipated_error_is_indeterminate_not_clean(tmp_path):
    _, s, app = fresh(tmp_path, CrashingMachine())
    out = app.episode()
    assert out["native"] == "indeterminate" and out["epsilon"] == "partial_realization"
    assert s.s["cups"] == 11                  # the dispensed cup is recorded

# ---------------------------------------------------------------- stale or forged authority
def selected_episode(app):
    actual = app.store.envelope(); req = request()
    cycle = app.rt.evaluate_integrated_canonical_cycle(actual, req).decision
    return req, cycle, app.rt.build_execution_license_from_cycle(cycle, req.domain_frame)

def test_license_cannot_be_instantiated_twice(tmp_path):
    _, _, app = fresh(tmp_path)
    _, _, license = selected_episode(app)
    app.rt.instantiate_execution("e1", license, entry_sufficient=True, max_steps=1)
    with pytest.raises(ValueError):
        app.rt.instantiate_execution("e2", license, entry_sufficient=True, max_steps=1)

def test_reconstructed_authorization_is_refused(tmp_path):
    m, _, app = fresh(tmp_path)
    _, _, license = selected_episode(app)
    ep = app.rt.instantiate_execution("e1", license, entry_sufficient=True, max_steps=1).episode
    auth = app.rt.issue_native_execution_authorization(ep, "sell", app.bindings,
                                                       decision_cycle_id="c1")
    forged = dataclasses.replace(auth)        # identical fields, not the ledger record
    with pytest.raises(ValueError):
        app.rt.invoke_authorized_native(forged, app.bindings)
    assert m.cups == 12                       # the function never ran

# ---------------------------------------------------------------- evidence freshness
@pytest.mark.parametrize("age", range(6))
def test_network_evidence_counts_only_while_fresh(tmp_path, age):
    _, s, app = fresh(tmp_path)
    s.advance("aged report", dt=float(age))  # report as_of stays at 0
    _, cycle, _ = selected_episode(app)
    sell_feasible = "graph:sell" in cycle.constraints.feasible_policy_ids
    assert sell_feasible == (age <= app_mod.MAX_EVIDENCE_AGE)

# ---------------------------------------------------------------- hostile projection
class LaunderingProjection(CoffeeProjection):
    """Hides a known harm: projects as if no refund were owed."""
    def project(self, req):
        state = req.represented_state
        clean = dataclasses.replace(state, metadata=dict(state.metadata, refunds_owed=0))
        return super().project(dataclasses.replace(req, represented_state=clean))

def harm_left_unremedied(owed_before, out):
    return owed_before > 0 and out["selected"] != "graph:refund"

def owed_then_next(tmp_path, monkeypatch, projection):
    monkeypatch.setattr(app_mod, "CoffeeProjection", projection)
    m, s, app = fresh(tmp_path)
    m.faults.append("no_delivery"); app.episode()
    owed = s.s["refunds_owed"]
    return owed, app.episode()

def test_honest_projection_remedies_the_harm(tmp_path, monkeypatch):
    owed, out = owed_then_next(tmp_path, monkeypatch, CoffeeProjection)
    assert owed == 1 and not harm_left_unremedied(owed, out)

def test_laundering_projection_is_caught_by_the_invariant(tmp_path, monkeypatch):
    owed, out = owed_then_next(tmp_path, monkeypatch, LaunderingProjection)
    assert owed == 1 and harm_left_unremedied(owed, out)   # the violation is visible

# ---------------------------------------------------------------- metamorphic check
def picks(tmp_path, capsys):
    out, _ = run_day(str(tmp_path / "day.json")); capsys.readouterr()
    return [r["selected"] for _, r in out]

def test_tie_order_is_not_a_hidden_preference(tmp_path, capsys, monkeypatch):
    baseline = picks(tmp_path, capsys)
    real = app_mod.SigmaOrderDefinition
    monkeypatch.setattr(app_mod, "SigmaOrderDefinition",
                        lambda pid, order: real(pid, 100 - order))   # reverse the order
    assert picks(tmp_path, capsys) == baseline

# ---------------------------------------------------------------- regression and identity
def test_day_matches_banked_output(tmp_path, capsys):
    run_day(str(tmp_path / "day.json"))
    banked = (HERE / "coffee_day_expected.txt").read_text()
    assert capsys.readouterr().out == banked

def test_runtime_is_the_frozen_v0141_build():
    root = pathlib.Path(pvpp_runtime.__file__).resolve().parents[1]
    manifest = root / "V0141_FILE_HASHES.sha256"
    if not manifest.exists():
        pytest.skip("runtime manifest not found beside pvpp_runtime")
    for line in manifest.read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        if name.startswith("pvpp_runtime/") and name.endswith(".py"):
            assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
