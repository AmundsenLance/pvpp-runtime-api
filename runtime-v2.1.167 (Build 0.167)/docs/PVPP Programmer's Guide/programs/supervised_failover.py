"""Chapter 12: the operations agent's failover, supervised while it runs.

An identity monitor revokes the agent's write credential while the failover is in progress.
The supervision layer finds the affected execution, the checkpoint decides that it may not
continue, the orchestrator is asked to stop the rollout, the orchestrator's evidence of what
actually happened is reconciled, and the agent is governed again without the credential.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from ops_model import actual_state, decide, make_runtime, request
from pvpp_runtime import ExecutionBindingRegistry, ExecutionBindingIdentity
from pvpp_runtime import ExecutionObservation, GovernanceInvalidationSignal
from pvpp_runtime.supervision import (
    HostTrustProvider, SQLiteSupervisoryStore, CanonicalRuntimeBridge,
    ObservationService, SourceRegistration, ExternalObservation, DependencyService,
    ContinuationService, ControlService, EffectService,
)

CFG, AGENT = "ops-prod", "ops-agent"
ADMIN, PROOF = "platform-admin", "platform-admin-proof"     # demonstration credentials only


def at(minute):
    return f"2026-10-07T09:{minute:02d}:00+00:00"


def trust():
    """The host's trust boundary: registration roots, and how controller reports are checked."""
    def orchestrator_report_verified(**report):
        return report["attestation_evidence"] == "signed:orchestrator"

    return HostTrustProvider(
        {ADMIN: {"proof": PROOF, "roles": ("*",), "configurations": (CFG,)}},
        controller_attestation_verifier=orchestrator_report_verified,
        clock=lambda: datetime(2026, 10, 7, 9, 30, tzinfo=timezone.utc))


class Orchestrator:
    """The deployment orchestrator: runs rollouts and carries out commands; not PV-PP."""

    def __init__(self):
        self.rollouts = {}

    def start(self, plan):
        handle = f"orchestrator:rollout-{len(self.rollouts) + 1}"
        self.rollouts[handle] = "in_progress"
        return handle

    def send(self, command, handle):
        if self.rollouts.get(handle) != "in_progress":
            return "too_late", "signed:orchestrator"
        self.rollouts[handle] = {"abort_rollout": "aborted", "kill_rollout": "killed",
                                 "hold_rollout": "held"}[command]
        return "completed", "signed:orchestrator"


def start_supervised_failover():
    """1-4. Decide, register the execution, its sources, owner, and adapter; start the rollout."""
    s = SimpleNamespace(orch=Orchestrator(), actual=actual_state(credential=True))
    s.rt, out = decide(s.actual)
    s.decision = out.decision.selection.selected_policy_id
    license = s.rt.build_execution_license_from_cycle(out.decision, request().domain_frame)

    # 1. Open the episode through the bridge; issue and register the execution's authority.
    s.bridge = CanonicalRuntimeBridge(s.rt)
    s.episode = s.bridge.instantiate_execution("failover-1", license, entry_sufficient=True,
                                               max_steps=10).episode
    s.bindings = ExecutionBindingRegistry(tuple(s.rt.registry.actions))
    s.bindings.register(ExecutionBindingIdentity("failover-bind", "failover", "1"),
                        lambda ctx: s.orch.start("replica"))
    s.auth = s.bridge.issue_native_execution_authorization(
        s.episode, "failover", s.bindings, decision_cycle_id="cycle-1", configuration_id=CFG)
    s.store = SQLiteSupervisoryStore(":memory:", trust_provider=trust())
    handle = s.bridge.resolve_canonical_execution(s.auth, configuration_id=CFG)
    s.active = s.bridge.register_active_execution(
        s.store, handle, registered_at=at(0),
        execution_id=s.rt.native_execution_authorization_execution_id(s.auth.authorization_id))
    s.aid = s.active.active_execution_id

    # 2. Sources: the identity monitor reports facts; the orchestrator reports effects.
    s.obs, s.deps = ObservationService(s.store), DependencyService(s.store)
    s.cont = ContinuationService(s.store, s.deps, s.bridge)
    s.effects = EffectService(s.store, s.obs)
    for reg_id, source, roles, kinds, uses in (
            ("reg-iam-1", "iam-monitor", ("observation",), ("write_credential",), ("governance",)),
            ("reg-orch-1", "orchestrator", ("effect",), ("rollout",), ("effect_reconciliation",))):
        s.obs.register_source(SourceRegistration(
            reg_id, source, roles, kinds, (AGENT,), (CFG,), uses, "signed-feed", None, None,
            "current", ADMIN, 1), authority_proof=PROOF)
    report_credential(s, "cred-1", "granted", at(0))
    s.deps.register_dependency_binding(
        active_execution_id=s.aid, configuration_id=CFG, subject_id=AGENT,
        fact_kind="write_credential", fact_id="deploy", registration_authority=ADMIN,
        authority_proof=PROOF, registered_at=at(0))

    # 3. Two supervisors may own executions; one does now. The orchestrator's adapter.
    s.ctl = ControlService(s.store, s.deps, s.cont, s.bridge)
    for owner in ("supervisor-1", "supervisor-2"):
        s.ctl.register_supervisory_owner(owner_id=owner, configuration_id=CFG,
                                         registration_authority=ADMIN, authority_proof=PROOF,
                                         registered_at=at(0))
    s.owner = s.ctl.acquire_ownership(active_execution_id=s.aid, owner_id="supervisor-1",
                                      acquired_at=at(0))
    s.adapter = s.ctl.register_adapter(
        adapter_id="orchestrator", configuration_id=CFG, target_handle_namespace="orchestrator:",
        supported_semantic_controls=("hold", "cancel", "terminate"),
        command_mapping={"hold": "hold", "cancel": "cancel", "terminate": "terminate"},
        vendor_command_mapping={"hold": "hold_rollout", "cancel": "abort_rollout",
                                "terminate": "kill_rollout"},
        controller_attestation_method="signed", control_region_evidence_method="rollout-state",
        registration_authority=ADMIN, authority_proof=PROOF, registered_at=at(0))

    # 4. The host starts the rollout by its own means; the episode stays open while it runs.
    s.rollout = s.orch.start("replica")
    s.tick = s.cont.checkpoint(active_execution_id=s.aid, checkpoint_at=at(2),
                               observation=ExecutionObservation("rollout-25pct"))
    return s


def report_credential(s, observation_id, value, when, source="iam-monitor"):
    """One monitor report: submit it, assess its admission, commit the governed change."""
    o = ExternalObservation(observation_id, source, "write_credential", "deploy", AGENT, CFG,
                            value, None, when, when, when, {})
    s.obs.submit_observation(o)
    return s.obs.commit_admission_change(o, s.obs.assess_observation(o, assessed_at=when),
                                         committed_at=when)


def revoke_credential(s):
    """5. The credential is revoked mid-rollout; the host checkpoints every affected execution."""
    change = report_credential(s, "cred-2", "revoked", at(5))
    s.affected = s.deps.resolve_affected_executions(change, configuration_id=CFG)
    s.assessments = {}
    for aid in s.affected:
        signal = GovernanceInvalidationSignal(
            "credential-revoked", "Constraints", "write credential revoked",
            "monitor:iam-monitor", change.observation_ids, (), s.active.execution_id, CFG)
        s.assessments[aid] = s.cont.checkpoint(active_execution_id=aid, checkpoint_at=at(5),
                                               invalidation_signals=(signal,),
                                               trigger_ids=(change.change_id,))
    return s.assessments[s.aid]


def stop(s, assessment, control, owner_id="supervisor-1", fence=None):
    """6. Fence unused authority, request the stop, and record what the orchestrator reports."""
    fence = s.owner.owner_fence if fence is None else fence
    s.fenced = ()
    if assessment.authority_fence_required:
        s.fenced = s.ctl.fence_execution_authority(
            active_execution_id=s.aid, owner_id=owner_id, owner_fence=fence,
            reason="authority withdrawn")
    req = s.ctl.issue_control_request(
        assessment_id=assessment.assessment_id, active_execution_id=s.aid, owner_id=owner_id,
        owner_fence=fence, requested_control=control, target_handle=s.rollout,
        created_at=at(5))
    s.attempt = s.ctl.dispatch_control_request(
        control_request_id=req.control_request_id, owner_id=owner_id, owner_fence=fence,
        adapter_registration_id=s.adapter.adapter_registration_id, target_handle=s.rollout,
        control_region_at_request="interruptible", capability_evidence_ref="orch-caps-1",
        mapping_identity="orch-map-1", dispatched_at=at(5))
    outcome, evidence = s.orch.send(s.attempt.mapped_command, s.rollout)   # the orchestrator acts
    return s.ctl.record_enforcement_outcome(
        control_attempt_id=s.attempt.control_attempt_id, outcome=outcome,
        controller_evidence_ref=f"{s.rollout}:ack",
        observed_control_region=s.orch.rollouts[s.rollout], recorded_at=at(6),
        attestation_evidence=evidence)


def reconcile(s, state="no_material_effect_evidenced"):
    """7. Enforcement is not effect: reconcile what the orchestrator says the world shows."""
    e = s.effects.submit_effect_evidence(
        active_execution_id=s.aid, source_id="orchestrator", configuration_id=CFG, state=state,
        realized_bundle_ref=None, evidence_ref=f"{s.rollout}:traffic-report",
        provenance="orchestrator traffic report", observed_at=at(7), effective_at=at(6),
        received_at=at(7))
    return s.effects.reconcile_effect(active_execution_id=s.aid,
                                      effect_evidence_id=e.effect_evidence_id, updated_at=at(7))


def govern_again():
    """8. Govern again from the new facts: the agent no longer holds the credential."""
    _, out = decide(actual_state(credential=False, time=1.0), make_runtime())
    return out.decision.selection.selected_policy_id


if __name__ == "__main__":
    s = start_supervised_failover()
    print("decision:        ", s.decision, "| rollout", s.rollout, s.orch.rollouts[s.rollout])
    print("checkpoint 09:02:", s.tick.continuation_posture, f"(epsilon {s.tick.epsilon_status})")
    a = revoke_credential(s)
    print("credential revoked at 09:05; affected executions:", len(s.affected))
    print("checkpoint 09:05:", a.continuation_posture, "| fence required:",
          a.authority_fence_required)
    e = stop(s, a, "cancel")
    print("unused authority:", len(s.fenced), "fenced;",
          s.rt.native_execution_authorization_status(s.auth.authorization_id))
    print("stop:            ", s.attempt.requested_control, "->", s.attempt.mapped_command,
          "|", e.outcome, "| attestation", e.attestation_status, "|", s.orch.rollouts[s.rollout])
    w = reconcile(s)
    print("world effect:    ", w.state, "| unresolved:", w.unresolved)
    print("governed again:  ", govern_again())
