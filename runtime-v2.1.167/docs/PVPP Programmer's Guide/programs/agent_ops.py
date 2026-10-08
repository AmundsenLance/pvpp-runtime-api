"""An autonomous operations agent governed by PV-PP Runtime V2.1 (v0.141).

Chapter 10 example. The agent keeps a report service available. Over one shift
its represented world changes in the ways Chapter 5 described:

  * a network scanner confirms a replica route: a reachability refresh of an
    already-represented transformation, followed by Graph-stage re-entry;
  * a change freeze makes that reachable route impermissible (Constraints);
  * an operator revokes the agent's write credential while authority is
    outstanding: the authority is withdrawn before the call;
  * a new tool is obtained: it cannot be bound or authorized until it is
    admitted, atomically, as a new function with its first transformation.

Throughout, the agent's two governing domains are service availability and
control: whether a human override and a rollback point remain available.
"""
import os, sys
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
    GovernanceArtifactDependency, GovernanceDependencyChange,
    derive_dependency_invalidations,
)
from pvpp_runtime.models import (
    ActionProjection, GraphReachabilityObservation, GraphReachabilityRefreshRequest,
    NovelFunctionAdmissionRequest,
)
from pvpp_runtime.reentry import (
    refresh_graph_reachability_and_plan_reentry, admit_novel_function_and_plan_reentry,
)

WRITE_ACTIONS = {"restart", "hotfix", "failover", "reconfigure"}
CHANGE_ACTIONS = {"hotfix", "failover", "reconfigure"}

# ------------------------------------------------------------------------ registry
def build_registry():
    reg = PVPPRegistry()
    reg.register_domain(DomainDefinition("A", "report service available to users", 5.0))
    reg.register_domain(DomainDefinition("C", "human override and rollback available", 5.0))
    for aid, text in (("steady", "baseline: take no action"),
                      ("restart", "restart the service process"),
                      ("hotfix", "patch the running service in place"),
                      ("failover", "route traffic to the replica"),
                      ("escalate", "hand the incident to the on-call human")):
        reg.register_action(ActionDefinition(aid, text, ("A", "C")))
    reg.register_governing_configuration(GoverningConfiguration(epsilon_h=10.0))
    reg.register_regime_configuration(RegimeConfiguration(1, 2, 4, 100, 50, 10))
    for rule, text in (("write_credential", "write actions need a current credential"),
                       ("change_freeze", "no configuration change during a freeze")):
        reg.register_constraint_rule(ConstraintRuleDefinition(rule, "hard", description=text))
    reg.register_graph_instance(
        GraphInstanceDefinition("service", "system", ("A", "C"), "active"))
    for tid, family, cls, reach in (
            ("restart", "continuation", "continuation", "reachable"),
            ("hotfix", "maintenance_local_adjustment", "adjustment", "reachable"),
            ("failover", "substitution", "substitution", "unreachable"),
            ("escalate", "exit_transfer_liquidation", "exit", "reachable")):
        reg.register_graph_transformation(GraphTransformationDefinition(
            tid, "service", "service", family, ("A", "C"), reach, tid, (cls,)))
    for pid, order in (("graph:restart", 10), ("graph:hotfix", 20),
                       ("graph:failover", 30), ("graph:escalate", 40),
                       ("graph:reconfigure", 50)):
        reg.register_sigma_order(SigmaOrderDefinition(pid, order))      # ties only
    return reg

def request():
    return CanonicalDecisionCycleRequest(
        preservation_object=PreliminaryPreservationObject(
            "service-under-control", "the service stays available and under human control"),
        domain_frame=DomainFrame((DomainFrameTarget("A", "availability"),
                                  DomainFrameTarget("C", "control"))),
        required_graph_family_ids=("continuation", "exit_transfer_liquidation"),
        materially_required_policy_class_ids=("continuation", "exit"),
        projection_horizon=30.0)

# ------------------------------------------------------------ perception and adapter
class AgentAdapter:
    """Supplies facts about the service; decides nothing."""

    def perceived_decision_state_from_actual(self, actual):
        facts = {"state_id": actual.state_id, **actual.context}
        return PerceivedDecisionState(
            actual.actor_id, actual.state_id, actual.time,
            WorldState(actual.time, {"A": 10.0 if facts["healthy"] else 8.0, "C": 10.0}, facts),
            ppp={"write": "credentialed" if facts["credential"] else "read-only"},
            x_hat={"diagnosis": facts["diagnosis"]})

    def perceive(self, state): return state
    def domain_value(self, state, d): return float(state.powers[d])
    def project(self, state, action):
        if action.id == "steady":
            p = dict(state.powers); p["A"] -= 1.0; p["C"] -= 0.5
            return ActionProjection(action.id, WorldState(state.time + 1, p, state.metadata), True)
        return ActionProjection(action.id, state, True)
    def pressure_factors(self, state, d, baseline_drift):
        drift = {"A": -1.0, "C": -0.5}[d]
        return PressureFactors(d, self.domain_value(state, d) - 5.0, drift)
    def pressure_value(self, d, f): return 1.0 / max(f.margin, 0.1)
    def expected_deterioration(self, state, d, drift, value, f): return f.local_trajectory
    def compare_constraint_violation_severity(self, a, pa, b, pb, cls): return 0

    def constraint_profile(self, state, policy_id, action_ids, regime, governing):
        m, acts = state.metadata, set(action_ids)
        return PolicyConstraintProfile(policy_id, (
            ConstraintObservation("write_credential",
                                  bool(acts & WRITE_ACTIONS) and not m["credential"]),
            ConstraintObservation("change_freeze",
                                  bool(acts & CHANGE_ACTIONS) and m["freeze"])))


class AgentProjection:
    """PolicyProjectionService: projected consequences Q_t(pi). Never selects."""

    def project(self, req):
        diag = req.represented_state.metadata["diagnosis"]
        a, c = {
            "restart": (20.0 if diag == "memory leak" else 0.5, 30.0),
            "hotfix": (30.0, 0.5),              # fast, but destroys the rollback point
            "failover": (25.0, 30.0),
            "escalate": (12.0, 30.0),           # a human restores service, slowly
            "reconfigure": (30.0 if diag == "bad config" else 0.5, 30.0),
        }[req.action_ids[0]]
        corridors = tuple(
            RecoveryCorridorProjection(k, f, h > 1, h > 1, h > 1,
                                       1.0 if h > 1 else None, None if h > 1 else h)
            for k, f, h in (("A", "availability", a), ("C", "control", c)))
        horizons = {"A": a, "C": c}
        return PolicyProjectionRecord(
            req.policy_id, True, req.represented_state, horizons, corridors,
            projection_horizon=req.projection_horizon,
            right_censored_domain_ids=tuple(k for k, h in horizons.items()
                                            if h >= req.projection_horizon),
            state_id=req.state_id, state_time=req.represented_state.time,
            candidate_mode=req.candidate_mode, model_version="ops-q1",
            projection_input_trace=dict(req.projection_input_trace))

# ------------------------------------------------------------------------ the world
class Service:
    """The external world: the service, its replica, and the agent's tools."""
    def __init__(self):
        self.healthy, self.diagnosis, self.calls = False, "memory leak", []

    def _act(self, name, fixes):
        self.calls.append(name)
        if fixes: self.healthy = True
        return {"done": name}

    def restart(self, ctx):  return self._act("restart", self.diagnosis == "memory leak")
    def hotfix(self, ctx):   return self._act("hotfix", True)
    def failover(self, ctx): return self._act("failover", True)
    def escalate(self, ctx): return self._act("escalate", False)
    def reconfigure(self, ctx): return self._act("reconfigure", self.diagnosis == "bad config")

# ------------------------------------------------------------------------ the agent
class OpsAgent:
    def __init__(self, service):
        self.svc, self.n, self.log = service, 0, []
        self.facts = {"diagnosis": service.diagnosis, "credential": True,
                      "freeze": False, "healthy": False}
        self.version, self.time = 0, 0.0
        self.rt = PVPPRuntime(build_registry(), AgentAdapter(),
                              projection_service=AgentProjection(),
                              layer1_transition_service=self)
        self.rebind()

    # --- actual state (host-owned) and its Layer-1 transition
    def actual(self):
        return ActualPersistentStateEnvelope(
            "ops-agent", f"s{self.version}", self.time,
            pp={"write": self.facts["credential"]}, spv={}, avs={"healthy": self.facts["healthy"]},
            context=dict(self.facts))

    def record(self, why, dt=0.0, **changes):
        self.facts.update(changes); self.version += 1; self.time += dt
        self.log.append(why)

    def transition(self, current, handoff):         # Layer 1: from the service's own state
        self.record(f"{handoff.selected_policy_id}: {handoff.execution_status}", dt=1.0,
                    healthy=self.svc.healthy)
        return Layer1TransitionResult(handoff.episode_id, handoff.selected_policy_id,
                                      current.state_id, self.actual(), True, {})

    def rebind(self):                                # registration only: no authority
        self.bindings = ExecutionBindingRegistry(tuple(self.rt.registry.actions))
        for aid in self.rt.registry.actions:
            if aid != "steady":
                self.bindings.register(
                    ExecutionBindingIdentity(f"{aid}-v1", aid, "1.0"), getattr(self.svc, aid))

    # --- changes to the represented world
    def scanner_reports(self, transformation_id, status, source):
        """Refresh reachability of an already-represented transformation."""
        reg = self.rt.registry
        observation = GraphReachabilityObservation(
            transformation_id, status, self.time, source, f"{source}:{self.time}")
        trig = refresh_graph_reachability_and_plan_reentry(
            reg, GraphReachabilityRefreshRequest(
                reg.graph_substrate_identity(), (observation,), f"refresh-{self.version}"))
        self.record(f"reachability {transformation_id} -> {status}")
        return trig.reentry_plan.recompute_from_stage if trig.reentry_plan else None

    def admit_tool(self, action_id, family, cls, text, source, rationale):
        """Admit a new function atomically with its first transformation."""
        reg = self.rt.registry
        action = ActionDefinition(action_id, text, ("A", "C"))
        transformation = GraphTransformationDefinition(
            action_id, "service", "service", family, ("A", "C"), "reachable",
            action_id, (cls,))
        trig = admit_novel_function_and_plan_reentry(reg, NovelFunctionAdmissionRequest(
            f"admit-{action_id}", reg.action_registry_identity(),
            reg.graph_substrate_identity(), action, transformation,
            "cfg-2", source, f"{source}:{action_id}", rationale))
        self.record(f"admitted tool {action_id}")
        self.rebind()                            # binding becomes possible only now
        return trig.reentry_plan.recompute_from_stage if trig.reentry_plan else None

    # --- one governed episode
    def episode(self, arriving=()):
        self.n += 1; cycle_id = f"cycle-{self.n}"
        actual, req = self.actual(), request()
        cycle = self.rt.evaluate_integrated_canonical_cycle(actual, req).decision
        license = self.rt.build_execution_license_from_cycle(cycle, req.domain_frame)
        ep = self.rt.instantiate_execution(f"ep-{self.n}", license, entry_sufficient=True,
                                           max_steps=1).episode
        auth = self.rt.issue_native_execution_authorization(
            ep, license.action_ids[0], self.bindings, decision_cycle_id=cycle_id)
        deps = (GovernanceArtifactDependency(f"{cycle_id}-cred", f"{cycle_id}:constraints",
                                             "Constraints", "credential", ("write",)),)
        changes = ()
        for fact, value in arriving:                 # reports that arrive before the call
            self.record(f"report: {fact} -> {value}", **{fact: value})
            changes += (GovernanceDependencyChange(f"chg-{self.version}", fact, ("write",),
                                                   f"{fact} changed"),)
        if changes and derive_dependency_invalidations(deps, changes).reentry.return_to_governance:
            self.rt.invalidate_native_execution_authorizations(
                decision_cycle_id=cycle_id, reason="write credential revoked")
            return {"selected": license.selected_policy_id, "why": why(cycle),
                    "regime": cycle.regime_assessment.regime,
                    "graph": cycle.graph_assessment.seed_ids, "withdrawn": True}
        native = self.rt.invoke_authorized_native(auth, self.bindings)
        ctx = ExecutionContext(native.execution_id, auth.action_id, auth.binding_id,
                               auth.decision_cycle_id, auth.attempt)
        step = self.rt.advance_execution(ep, self.bindings.epsilon_observation(
            ctx, native, realized_pv_bundle={"healthy": self.svc.healthy}))
        self.rt.apply_layer1_transition(actual, self.rt.build_layer1_transition_handoff(step))
        return {"selected": license.selected_policy_id, "why": why(cycle),
                "regime": cycle.regime_assessment.regime,
                "graph": cycle.graph_assessment.seed_ids, "epsilon": step.status,
                "healthy": self.facts["healthy"]}

def why(cycle):
    chosen, adequate = cycle.selection.selected_policy_id, set(cycle.adequacy.adequate_policy_ids)
    out = []
    for c in cycle.constraints.candidate_results:
        if c.policy_id == chosen: continue
        name = c.policy_id.split(":")[1]
        if not c.feasible:
            out.append(f"{name}: {', '.join(c.violation_profile.hard_violation_ids)}")
        else:
            out.append(f"{name}: {'Sigma' if c.policy_id in adequate else 'inadequate'}")
    return " | ".join(out)

# ------------------------------------------------------------------------ one shift
def show(label, out):
    tail = "authority withdrawn before the call" if out.get("withdrawn") else \
        f"{out['epsilon']}, service healthy={out['healthy']}"
    print(f"{label}\n  selected: {out['selected'].split(':')[1]:<12} {tail}")
    print(f"  regime: {out['regime']}; in Graph: "
          f"{', '.join(s.split(':')[1] for s in out['graph'])}")
    print(f"  set aside: {out['why']}")

def run_shift():
    svc = Service(); agent = OpsAgent(svc); out = []
    def ep(label, **kw):
        r = agent.episode(**kw); out.append((label, r)); show(label, r)
    ep("1 memory leak")
    svc.healthy = False; svc.diagnosis = "bad config"
    agent.record("monitor: degraded; diagnosis bad config", healthy=False, diagnosis="bad config")
    ep("2 bad config")
    agent.record("change freeze begins", freeze=True)
    stage = agent.scanner_reports("failover", "reachable", "net-scanner")
    print(f"-- scanner: replica route reachable; re-enter at {stage}")
    ep("3 route reachable, freeze on")
    agent.record("change freeze ends", freeze=False)
    ep("4 freeze lifted, credential revoked", arriving=[("credential", False)])
    ep("4' re-decided without credential")
    agent.record("credential restored", credential=True)
    try:
        agent.bindings.register(ExecutionBindingIdentity("reconfigure-v1", "reconfigure", "1.0"),
                                svc.reconfigure)
        print("-- tool bound before admission")
    except ValueError:
        print("-- new tool: binding refused before admission (action not registered)")
    stage = agent.admit_tool("reconfigure", "corrective_repair", "restoration",
                             "correct the service configuration", "vendor-toolkit",
                             "fixes configuration faults; rollback point preserved")
    print(f"-- new tool admitted with its first transformation; re-enter at {stage}")
    ep("5 tool admitted")
    return out, agent

if __name__ == "__main__":
    run_shift()
