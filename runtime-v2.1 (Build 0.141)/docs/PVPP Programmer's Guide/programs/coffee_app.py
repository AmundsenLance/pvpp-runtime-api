"""Coffee vending — a complete PV-PP application against Runtime V2.1 (v0.141).

Chapter 8 example. Chapters 6 and 7 evaluated one cycle and executed one
purchase. This file assembles those pieces into an application that runs a
sequence of governed episodes:

  * actual state lives in a host-owned store that persists between episodes;
  * perception forms P_i(t) from recorded evidence, including its age;
  * observation intake records outside reports and derives what they invalidate;
  * every decision, execution, and state change goes through the runtime;
  * unknown outcomes are reconciled from later evidence, and harms are remedied
    by governed actions (a refund is decided, authorized, and executed like a sale).

Nothing here reimplements a PV-PP stage. The host supplies facts; the runtime
applies the stages.
"""
import json, os, sys
if os.environ.get("PVPP_RUNTIME_PATH"):
    sys.path.insert(0, os.environ["PVPP_RUNTIME_PATH"])

from pvpp_runtime import (
    PVPPRuntime, PVPPRegistry, WorldState, PerceivedDecisionState,
    DomainDefinition, ActionDefinition, GoverningConfiguration, RegimeConfiguration,
    ConstraintRuleDefinition, GraphInstanceDefinition, GraphTransformationDefinition,
    SigmaOrderDefinition, PressureFactors, ConstraintObservation,
    PolicyConstraintProfile, PolicyProjectionRecord, RecoveryCorridorProjection,
    CanonicalDecisionCycleRequest, PreliminaryPreservationObject, DomainFrame,
    DomainFrameTarget, ExecutionBindingRegistry, ExecutionBindingIdentity,
    ExecutionContext, ActualPersistentStateEnvelope, Layer1TransitionResult,
    CleanExecutionFailure, CompletedInvalidExecution, GovernanceArtifactDependency,
    GovernanceDependencyChange, derive_dependency_invalidations,
)
from pvpp_runtime.models import ActionProjection

PRICE = 2.50
MAX_EVIDENCE_AGE = 2           # periods a network health report stays current

# --------------------------------------------------------------------- registry
def build_registry():
    reg = PVPPRegistry()
    reg.register_domain(DomainDefinition("D", "delivery: served or made whole", 5.0))
    reg.register_domain(DomainDefinition("T", "transaction integrity", 5.0))
    for aid, text in (("steady", "baseline: machine idles"),
                      ("sell", "authorize, dispense, capture"),
                      ("decline", "refuse before any charge"),
                      ("refund", "return a charge to an unserved buyer")):
        reg.register_action(ActionDefinition(aid, text, ("D", "T")))
    reg.register_governing_configuration(GoverningConfiguration(epsilon_h=10.0))
    reg.register_regime_configuration(RegimeConfiguration(1, 2, 4, 100, 50, 10))
    for rule, text in (
            ("card_network", "card actions need a current, reachable network"),
            ("reconciliation_hold", "no new card sale while a capture is unknown"),
            ("refund_basis", "a refund needs a recorded charged-unserved buyer")):
        reg.register_constraint_rule(
            ConstraintRuleDefinition(rule, "hard", description=text))
    reg.register_graph_instance(
        GraphInstanceDefinition("purchase", "episode", ("D", "T"), "active"))
    for tid, family, cls in (("sell", "continuation", "continuation"),
                             ("decline", "exit_transfer_liquidation", "exit"),
                             ("refund", "corrective_repair", "restoration")):
        reg.register_graph_transformation(GraphTransformationDefinition(
            tid, "purchase", "purchase", family, ("D", "T"), "reachable", tid, (cls,)))
    for pid, order in (("graph:sell", 10), ("graph:decline", 20), ("graph:refund", 30)):
        reg.register_sigma_order(SigmaOrderDefinition(pid, order))      # ties only
    return reg

def request():
    return CanonicalDecisionCycleRequest(
        preservation_object=PreliminaryPreservationObject(
            "buyers-whole", "every paying buyer receives coffee or is made whole"),
        domain_frame=DomainFrame((DomainFrameTarget("D", "delivery"),
                                  DomainFrameTarget("T", "transaction"))),
        required_graph_family_ids=("continuation", "exit_transfer_liquidation"),
        materially_required_policy_class_ids=("continuation", "exit"),
        projection_horizon=30.0)

# ------------------------------------------------------- perception and adapter
class CoffeeAdapter:
    """Host adapter: forms P_i(t) from recorded evidence; supplies domain facts."""

    def perceived_decision_state_from_actual(self, actual):
        net = actual.context["network"]
        age = actual.time - net["as_of"]
        network = net["status"] if age <= MAX_EVIDENCE_AGE else "unknown"
        owed = actual.avs["refunds_owed"]
        facts = {"state_id": actual.state_id, "cups": actual.context["cups"],
                 "network": network, "refunds_owed": owed,
                 "unreconciled": bool(actual.avs["unreconciled"])}
        margins = {"D": 10.0, "T": 10.0 - 3.0 * owed}
        return PerceivedDecisionState(
            actual.actor_id, actual.state_id, actual.time,
            WorldState(actual.time, margins, facts),
            ppp={"dispense": "operational", "card_payments": network},
            x_hat={"cups": actual.context["cups"]},
            uncertainty={"network_evidence_age": age})

    # The Chapter 6 fact surfaces, now reading perceived facts.
    def perceive(self, state): return state
    def domain_value(self, state, d): return float(state.powers[d])
    def project(self, state, action):
        if action.id == "steady":
            p = dict(state.powers); p["D"] -= 1.0; p["T"] -= 0.5
            nxt = WorldState(state.time + 1, p, state.metadata)
            return ActionProjection(action.id, nxt, True)
        return ActionProjection(action.id, state, True)
    def pressure_factors(self, state, d, baseline_drift):
        drift = {"D": -1.0, "T": -0.5}[d]
        return PressureFactors(d, self.domain_value(state, d) - 5.0, drift)
    def pressure_value(self, d, f): return 1.0 / max(f.margin, 0.1)
    def expected_deterioration(self, state, d, drift, value, f):
        return f.local_trajectory
    def compare_constraint_violation_severity(self, a, pa, b, pb, cls): return 0

    def constraint_profile(self, state, policy_id, action_ids, regime, governing):
        m, acts = state.metadata, set(action_ids)
        card = bool({"sell", "refund"} & acts)
        return PolicyConstraintProfile(policy_id, (
            ConstraintObservation("card_network", card and m["network"] != "up"),
            ConstraintObservation("reconciliation_hold",
                                  "sell" in acts and m["unreconciled"]),
            ConstraintObservation("refund_basis",
                                  "refund" in acts and m["refunds_owed"] == 0)))


class CoffeeProjection:
    """PolicyProjectionService: projected consequences Q_t(pi). Never selects."""

    def project(self, req):
        m, acts = req.represented_state.metadata, req.action_ids
        owed = m["refunds_owed"] > 0
        if "refund" in acts:
            d, t = 12.0, 30.0                  # the unserved buyer is made whole
        elif "sell" in acts:
            d = t = 30.0 if m["cups"] > 0 else 0.5
            if owed: t = 0.5                   # an unremedied buyer stays unremedied
        else:
            d, t = 12.0, (0.5 if owed else 30.0)
        corridors = tuple(
            RecoveryCorridorProjection(k, f, h > 1, h > 1, h > 1,
                                       1.0 if h > 1 else None, None if h > 1 else h)
            for k, f, h in (("D", "delivery", d), ("T", "transaction", t)))
        horizons = {"D": d, "T": t}
        return PolicyProjectionRecord(
            req.policy_id, True, req.represented_state, horizons, corridors,
            projection_horizon=req.projection_horizon,
            right_censored_domain_ids=tuple(k for k, h in horizons.items()
                                            if h >= req.projection_horizon),
            state_id=req.state_id, state_time=req.represented_state.time,
            candidate_mode=req.candidate_mode, model_version="coffee-q1",
            projection_input_trace=dict(req.projection_input_trace))

# -------------------------------------------------------------------- the world
class Machine:
    """The external world: dispenser, payment terminal, and payment network."""
    def __init__(self, cups=12):
        self.cups, self.network_up, self.revenue = cups, True, 0.0
        self.faults, self.captures, self.unserved = [], {}, 0
        self.monitor_silent = False
        self._hidden = {}                      # what the network actually did

    def sell(self, context):
        fault = self.faults.pop(0) if self.faults else None
        if fault == "card_declined":
            raise CleanExecutionFailure("issuer declined; nothing held or dispensed")
        self.cups -= 1
        if fault == "capture_timeout":
            self.captures[context.execution_id] = "unknown"
            self._hidden[context.execution_id] = "captured"
            raise TimeoutError("no response from payment network during capture")
        self.captures[context.execution_id] = "captured"; self.revenue += PRICE
        if fault == "no_delivery":
            self.unserved += 1
            raise CompletedInvalidExecution("charge captured; sensor saw no cup")
        return {"receipt": context.execution_id}

    def refund(self, context):
        self.unserved -= 1; self.revenue -= PRICE
        return {"refund": context.execution_id}

    def decline(self, context):
        return {"declined": True}

    def monitor(self):                         # network health heartbeat
        if self.monitor_silent: return None
        return "up" if self.network_up else "down"

    def sensors(self):
        return {"cups": self.cups, "revenue": self.revenue,
                "unserved": self.unserved, "captures": dict(self.captures)}

    def settlement_report(self):               # the processor's end-of-batch file
        return {e: self._hidden[e] for e, s in self.captures.items() if s == "unknown"}

# ------------------------------------------------- host-owned store and Layer 1
class Store:
    """Authoritative actual state S_i(t) and its change log, persisted as JSON."""
    def __init__(self, path, cups=12):
        self.path = path
        if os.path.exists(path):
            with open(path) as f: self.s = json.load(f)
        else:
            self.s = {"version": 0, "time": 0.0, "cups": cups, "revenue": 0.0,
                      "network": {"status": "up", "as_of": 0.0},
                      "unreconciled": [], "refunds_owed": 0, "log": []}
            self.save("initial state")

    def save(self, why):
        s = self.s
        s["log"].append({"version": s["version"], "time": s["time"], "why": why})
        with open(self.path, "w") as f: json.dump(s, f, indent=1)

    def envelope(self):
        s = self.s
        return ActualPersistentStateEnvelope(
            actor_id="coffee-machine", state_id=f"s{s['version']}", time=s["time"],
            pp={"dispense": "operational"}, spv={"revenue_captured": s["revenue"]},
            avs={"unreconciled": tuple(s["unreconciled"]),
                 "refunds_owed": s["refunds_owed"]},
            context={"cups": s["cups"], "network": dict(s["network"])})

    def advance(self, why, dt=0.0, **changes):  # every recorded change: a new state
        self.s.update(changes); self.s["version"] += 1; self.s["time"] += dt
        self.save(why)

class StoreLayer1:
    """Layer-1 transition T: the next actual state from realized-effect evidence."""
    def __init__(self, store): self.store = store

    def transition(self, current, handoff):
        s = dict(self.store.s)
        for e in handoff.execution_information:        # info_exec from the episode
            if "network_heartbeat" in e:
                s["network"] = {"status": e["network_heartbeat"],
                                "as_of": s["time"] + 1.0}
        for b in handoff.realized_pv_bundles:          # B_real from host evidence
            s["cups"] -= b.get("cups_dispensed", 0)
            s["revenue"] += b.get("revenue_delta", 0.0)
            s["refunds_owed"] += b.get("refunds_owed_delta", 0)
            s["unreconciled"] = s["unreconciled"] + b.get("unknown_captures", [])
        keys = ("cups", "revenue", "refunds_owed", "unreconciled", "network")
        self.store.advance(f"{handoff.selected_policy_id}: {handoff.execution_status}",
                           dt=1.0, **{k: s[k] for k in keys})
        nxt = self.store.envelope()
        return Layer1TransitionResult(
            handoff.episode_id, handoff.selected_policy_id, current.state_id, nxt, True,
            {"cups_nonnegative": nxt.context["cups"] >= 0,
             "refunds_nonnegative": nxt.avs["refunds_owed"] >= 0})

# ----------------------------------------------------------- observation intake
def intake(store, report):
    """Record an outside report as evidence; return the facts it changed.

    Intake decides nothing. It updates host-owned actual state and names the
    changed facts so that registered dependencies can be checked.
    """
    kind, s = report["kind"], store.s
    if kind == "network":
        changed = report["status"] != s["network"]["status"]
        store.advance(f"network report: {report['status']}",
                      network={"status": report["status"], "as_of": s["time"]})
        return (GovernanceDependencyChange(
            f"chg-{s['version']}", "payment_network", ("network",),
            f"network reported {report['status']}"),) if changed else ()
    if kind == "settlement":
        done = [e for e in s["unreconciled"] if e in report["results"]]
        captured = sum(report["results"][e] == "captured" for e in done)
        store.advance(f"settlement: {len(done)} reconciled",
                      unreconciled=[e for e in s["unreconciled"] if e not in done],
                      revenue=s["revenue"] + captured * PRICE)
        return (GovernanceDependencyChange(
            f"chg-{s['version']}", "reconciliation", ("captures",),
            "captures reconciled"),)
    if kind == "clock":
        store.advance(f"{report['periods']} idle periods", dt=float(report["periods"]))
        return ()
    raise ValueError(f"unknown report kind: {kind}")

# -------------------------------------------------------------- the application
class CoffeeApp:
    def __init__(self, machine, store):
        self.machine, self.store, self.n, self.queue = machine, store, 0, []
        self.rt = PVPPRuntime(build_registry(), CoffeeAdapter(),
                              projection_service=CoffeeProjection(),
                              layer1_transition_service=StoreLayer1(store))
        self.bindings = ExecutionBindingRegistry(tuple(self.rt.registry.actions))
        for aid in ("sell", "decline", "refund"):
            self.bindings.register(
                ExecutionBindingIdentity(f"{aid}-v1", aid, "1.0"), getattr(machine, aid))
        self.provenance = None             # carried forward only if state is unchanged

    def report(self, r):                   # outside reports wait in the intake queue
        self.queue.append(r)

    def drain(self):
        changes = ()
        while self.queue:
            changes += intake(self.store, self.queue.pop(0))
        return changes

    def episode(self, arriving=()):
        """One governed episode: perceive, decide, authorize, act, record.

        `arriving` simulates reports that reach the intake queue while
        authority is outstanding, between authorization and the call.
        """
        self.drain()
        self.n += 1; cycle_id = f"cycle-{self.n}"
        actual = self.store.envelope()
        prior = self.provenance
        if prior is not None and prior.next_state_id != actual.state_id:
            prior = None
        req = request()
        cycle = self.rt.evaluate_integrated_canonical_cycle(
            actual, req, prior_transition_provenance=prior).decision
        license = self.rt.build_execution_license_from_cycle(cycle, req.domain_frame)
        episode = self.rt.instantiate_execution(
            f"ep-{self.n}", license, entry_sufficient=True, max_steps=1).episode
        auth = self.rt.issue_native_execution_authorization(
            episode, license.action_ids[0], self.bindings, decision_cycle_id=cycle_id)

        # What this decision relied on, so a later report can invalidate it.
        deps = tuple(GovernanceArtifactDependency(
                         f"{cycle_id}-{kind}", f"{cycle_id}:constraints",
                         "Constraints", kind, facts)
                     for kind, facts in (("payment_network", ("network",)),
                                         ("reconciliation", ("captures",))))
        for r in arriving: self.report(r)
        changes = self.drain()             # intake immediately before the call
        if changes:
            inv = derive_dependency_invalidations(deps, changes)
            if inv.reentry.return_to_governance:
                self.rt.invalidate_native_execution_authorizations(
                    decision_cycle_id=cycle_id,
                    reason="; ".join(c.reason for c in changes))
                return {"selected": license.selected_policy_id, "why": why(cycle),
                        "withdrawn": inv.reentry.recompute_from_stage}

        before = self.machine.sensors()
        native = self.rt.invoke_authorized_native(auth, self.bindings)
        after = self.machine.sensors()     # host evidence, not the return value
        bundle = {"cups_dispensed": before["cups"] - after["cups"],
                  "revenue_delta": after["revenue"] - before["revenue"],
                  "refunds_owed_delta": after["unserved"] - before["unserved"],
                  "unknown_captures": [e for e, s in after["captures"].items()
                                       if s == "unknown" and e not in before["captures"]]}
        realized = bundle if any(bundle.values()) else {}
        heartbeat = self.machine.monitor()
        info = {"network_heartbeat": heartbeat} if heartbeat else {}
        ctx = ExecutionContext(native.execution_id, auth.action_id, auth.binding_id,
                               auth.decision_cycle_id, auth.attempt)
        step = self.rt.advance_execution(episode, self.bindings.epsilon_observation(
            ctx, native, realized_pv_bundle=realized, information=info))
        handoff = self.rt.build_layer1_transition_handoff(step)
        transition = self.rt.apply_layer1_transition(actual, handoff)
        validation = self.rt.validate_layer1_transition_result(
            actual, handoff, transition)
        self.provenance = self.rt.build_execution_transition_provenance(
            actual, handoff, transition, validation)
        return {"selected": license.selected_policy_id, "why": why(cycle),
                "mode": license.selection_mode, "native": native.status,
                "epsilon": step.status, "provenance_checked": prior is not None}

# ------------------------------------------------------- a day at the machine
def why(cycle):
    """Name what set aside each candidate the cycle did not select."""
    chosen = cycle.selection.selected_policy_id
    adequate = set(cycle.adequacy.adequate_policy_ids)
    out = []
    for c in cycle.constraints.candidate_results:
        if c.policy_id == chosen: continue
        name = c.policy_id.split(":")[1]
        if not c.feasible:
            out.append(f"{name}: {', '.join(c.violation_profile.hard_violation_ids)}")
        else:
            out.append(f"{name}: {'Sigma' if c.policy_id in adequate else 'inadequate'}")
    return " | ".join(out)

def line(label, out, store):
    s = store.s
    if "withdrawn" in out:
        what = f"authority withdrawn (re-enter at {out['withdrawn']})"
    else:
        what = f"{out['native']:<17} -> {out['epsilon']}"
    print(f"{label:<24} {out['selected'].split(':')[1]:<8} {what}")
    print(f"{'':<24} set aside: {out['why']}")
    print(f"{'':<24} cups={s['cups']} revenue={s['revenue']:.2f} "
          f"unreconciled={len(s['unreconciled'])} refunds_owed={s['refunds_owed']}")

def run_day(path):
    if os.path.exists(path): os.remove(path)
    m, store = Machine(), Store(path)
    app = CoffeeApp(m, store)
    out = []
    def ep(label, arriving=()):
        r = app.episode(arriving); out.append((label, r)); line(label, r, store)
    ep("1 buyer")
    m.faults.append("capture_timeout");  ep("2 buyer, capture lost")
    ep("3 buyer, capture open")
    app.report({"kind": "settlement", "results": m.settlement_report()})
    ep("4 buyer, after settle")
    m.faults.append("no_delivery");      ep("5 buyer, no cup")
    ep("6 next episode")
    m.network_up = False                 # the outage is reported after authorization
    ep("7 buyer, network fails", arriving=[{"kind": "network", "status": "down"}])
    ep("7' buyer, re-decided")
    m.network_up = True;  app.report({"kind": "network", "status": "up"})
    ep("8 buyer, network back")
    m.monitor_silent = True;  app.report({"kind": "clock", "periods": 3})
    ep("9 buyer, monitor silent")
    return out, store

if __name__ == "__main__":
    run_day(os.environ.get("COFFEE_STATE", "coffee_state.json"))
