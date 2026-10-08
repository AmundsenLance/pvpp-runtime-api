"""Coffee vending — from selection to realized state against PV-PP Runtime V2.1 (v0.141).

Chapter 7 example. It reuses the Chapter 6 registry, adapter, and request, then
carries the selected policy through the runtime's execution lineage:

    cycle -> license -> episode -> single-use native authorization
          -> authorized call-through -> execution evidence -> epsilon
          -> Layer-1 handoff -> host-owned Layer-1 transition

The machine below stands in for the external world. Its records, not the
function's return value, are the evidence from which actual state is updated.
"""
import os, sys
if os.environ.get("PVPP_RUNTIME_PATH"):
    sys.path.insert(0, os.environ["PVPP_RUNTIME_PATH"])

from pvpp_runtime import (
    PVPPRuntime, WorldState, ExecutionBindingRegistry, ExecutionBindingIdentity,
    ExecutionContext, ActualPersistentStateEnvelope, Layer1TransitionResult,
    CleanExecutionFailure, CompletedInvalidExecution,
)
from coffee_decision import build_registry, CoffeeWorld, CoffeeProjection, request

PRICE = 2.50

# ------------------------------------------------------------------ the world
class CoffeeMachine:
    """The external world. `fault` injects one realistic failure into a sale."""
    def __init__(self, cups=12, network_up=True, fault=None):
        self.cups, self.network_up, self.fault = cups, network_up, fault
        self.revenue, self.capture, self.unserved, self.calls = 0.0, "none", 0, 0

    def sell(self, context):                  # the registered native function
        self.calls += 1
        if self.fault == "card_declined":     # nothing happened, and we know it
            raise CleanExecutionFailure("issuer declined; nothing held or dispensed")
        self.cups -= 1                        # the cup is dispensed
        if self.fault == "capture_timeout":   # money may or may not have moved
            self.capture = "unknown"
            raise TimeoutError("no response from payment network during capture")
        self.revenue += PRICE; self.capture = "captured"
        if self.fault == "no_delivery":       # finished, but the result is wrong
            self.unserved += 1
            raise CompletedInvalidExecution("charge captured; sensor saw no cup")
        return {"receipt": context.execution_id}

    def records(self):                        # what the machine's sensors report
        return {"cups": self.cups, "revenue": self.revenue,
                "capture": self.capture, "charged_unserved": self.unserved}

# ------------------------------------------------------ Layer 1 (host-owned)
def open_items(r):
    items = ["reconcile capture"] if r["capture"] == "unknown" else []
    return items + ["refund owed: charged, not served"] * r["charged_unserved"]

def envelope(machine, state_id, time):
    r = machine.records(); items = open_items(r)
    return ActualPersistentStateEnvelope(
        actor_id="coffee-machine", state_id=state_id, time=time,
        pp={"dispense": "operational",
            "payment": "up" if machine.network_up else "down"},
        spv={"revenue_captured": r["revenue"]},
        avs={"unresolved_buyers": len(items)},
        context={"cups": r["cups"], "open_items": tuple(items)})

class CoffeeLayer1:
    """Next actual state from the machine's records, attributed to the episode."""
    def __init__(self, machine): self.machine = machine
    def transition(self, current, handoff):
        nxt = envelope(self.machine, f"{current.state_id}+1", current.time + 1)
        return Layer1TransitionResult(
            handoff.episode_id, handoff.selected_policy_id, current.state_id,
            nxt, True, {"cups_nonnegative": nxt.context["cups"] >= 0})

# ---------------------------------------------------- one governed purchase
def perceive(actual):
    """P_i(t) from S_i(t). Perception is exact here; Chapter 8 makes it real."""
    return WorldState(actual.time, {"D": 10.0, "T": 10.0},
                      {"cups": actual.context["cups"],
                       "network_up": actual.pp["payment"] == "up"})

def purchase(machine, actual, *, stale_before_call=False):
    rt = PVPPRuntime(build_registry(), CoffeeWorld(),
                     projection_service=CoffeeProjection(),
                     layer1_transition_service=CoffeeLayer1(machine))
    req = request()
    cycle = rt.evaluate_canonical_decision_cycle(perceive(actual), req)  # Ch. 6
    license = rt.build_execution_license_from_cycle(cycle, req.domain_frame)
    episode = rt.instantiate_execution("purchase-1", license,
                                       entry_sufficient=True, max_steps=1).episode
    action = license.action_ids[0]

    bindings = ExecutionBindingRegistry(tuple(rt.registry.actions))  # not authority
    bindings.register(ExecutionBindingIdentity("sell-v1", "sell", "1.0"),
                      machine.sell)
    bindings.register(ExecutionBindingIdentity("decline-v1", "decline", "1.0"),
                      lambda context: {"declined": True})
    auth = rt.issue_native_execution_authorization(
        episode, action, bindings, decision_cycle_id="cycle-1")

    if stale_before_call:         # a fact the decision relied on has changed
        machine.network_up = False
        rt.invalidate_native_execution_authorizations(
            decision_cycle_id="cycle-1", reason="payment network reported down")
    try:
        result = rt.invoke_authorized_native(auth, bindings)  # consume, then call
    except RuntimeError as refused:
        return {"selected": license.selected_policy_id, "refused": str(refused),
                "calls": machine.calls}
    try:
        rt.invoke_authorized_native(auth, bindings)            # single use
        reuse = "accepted"
    except RuntimeError:
        reuse = "refused"

    after = machine.records()                          # host evidence, not result
    dispensed = actual.context["cups"] - after["cups"]
    realized = {"cups_dispensed": dispensed, "capture": after["capture"]} \
        if dispensed else {}
    ctx = ExecutionContext(result.execution_id, auth.action_id, auth.binding_id,
                           auth.decision_cycle_id, auth.attempt)
    obs = bindings.epsilon_observation(ctx, result, realized_pv_bundle=realized)
    step = rt.advance_execution(episode, obs)                       # epsilon
    handoff = rt.build_layer1_transition_handoff(step)
    new_actual = rt.apply_layer1_transition(actual, handoff).next_state  # Layer 1
    return {"selected": license.selected_policy_id, "native": result.status,
            "epsilon": step.status, "return_upstream": step.return_upstream,
            "reuse": reuse, "calls": machine.calls, "actual": new_actual}

# ------------------------------------------------------------------ reporting
def show(label, out):
    print(f"\n== {label}")
    print("  selected:      ", out["selected"])
    if "refused" in out:
        print("  call-through:   refused before the function ran")
        print("  reason:        ", out["refused"])
        print("  function calls:", out["calls"])
        return
    print("  native result: ", out["native"], "| authorization reused:", out["reuse"])
    print("  epsilon:       ", out["epsilon"], "| return upstream:", out["return_upstream"])
    a = out["actual"]
    items = f" {list(a.context['open_items'])}" if a.context["open_items"] else ""
    print("  actual state:  ", f"cups={a.context['cups']}",
          f"revenue={a.spv['revenue_captured']:.2f}",
          f"unresolved={a.avs['unresolved_buyers']}{items}")

def start(machine):
    return envelope(machine, "s0", 0.0)

if __name__ == "__main__":
    for label, fault in (("A. normal sale", None),
                         ("B. card declined", "card_declined"),
                         ("C. capture timed out", "capture_timeout"),
                         ("D. no cup delivered", "no_delivery")):
        m = CoffeeMachine(fault=fault)
        show(label, purchase(m, start(m)))
    m = CoffeeMachine()
    show("E. network fails after authorization, before the call",
         purchase(m, start(m), stale_before_call=True))
    show("E'. next cycle, from the updated facts", purchase(m, start(m)))
