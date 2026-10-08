"""Step 6: supervise the recharge while it runs. A site monitor withdraws the charging permit."""

from datetime import datetime, timezone
from types import SimpleNamespace

from step4_decide import decide, make_runtime, request
from step5_act import Layer1Service
from pvpp_runtime import ExecutionBindingRegistry, ExecutionBindingIdentity
from pvpp_runtime import GovernanceInvalidationSignal
from pvpp_runtime.supervision import (
    HostTrustProvider, SQLiteSupervisoryStore, CanonicalRuntimeBridge,
    ObservationService, SourceRegistration, ExternalObservation,
    DependencyService, ContinuationService, ControlService,
)

CFG = "battery-site"          # the configuration the supervised execution belongs to
SENSOR = "sensor-A"           # the subject the monitor reports on
ADMIN, PROOF = "site-admin", "site-admin-proof"   # demonstration credentials only


def at(minute):
    """Timestamps for the example: 12:00 UTC plus the given minute."""
    return f"2026-10-07T12:{minute:02d}:00+00:00"


def trust():
    """Who may register what, and how a controller's report is verified. In a deployment
    these come from your own identity and key systems, not from literals in code."""
    def charger_report_verified(**report):
        return report["attestation_evidence"] == "signed:charger"

    return HostTrustProvider(
        {ADMIN: {"proof": PROOF, "roles": ("*",), "configurations": (CFG,)}},
        controller_attestation_verifier=charger_report_verified,
        clock=lambda: datetime(2026, 10, 7, 12, 30, tzinfo=timezone.utc))


class Charger:
    """An external controller that runs charging jobs. It is not part of PV-PP."""

    def __init__(self):
        self.jobs = {}

    def start(self):                            # returns at once; the job keeps running
        handle = f"charger:job-{len(self.jobs) + 1}"
        self.jobs[handle] = "charging"
        return handle

    def send(self, command, handle):            # carries out a vendor command
        if self.jobs.get(handle) != "charging":
            return "too_late", "signed:charger"
        if command == "stop_charge":
            self.jobs[handle] = "stopped"
        return "completed", "signed:charger"


def start_supervised_charge():
    """Decide, license, register the execution for supervision, and start the charge."""
    s = SimpleNamespace(charger=Charger())
    s.rt, out = decide(5.0, make_runtime(Layer1Service()))
    license = s.rt.build_execution_license_from_cycle(out.decision, request().domain_frame)

    # 1. Open the episode through the bridge and issue the authority for this execution.
    s.bridge = CanonicalRuntimeBridge(s.rt)
    episode = s.bridge.instantiate_execution("episode-1", license, entry_sufficient=True,
                                             max_steps=5).episode
    bindings = ExecutionBindingRegistry(tuple(s.rt.registry.actions))
    bindings.register(ExecutionBindingIdentity("charge", "recharge", "1"), lambda ctx: None)
    s.auth = s.bridge.issue_native_execution_authorization(
        episode, "recharge", bindings, decision_cycle_id="cycle-1", configuration_id=CFG)

    # 2. Register the execution as active in a durable supervisory store.
    s.store = SQLiteSupervisoryStore(":memory:", trust_provider=trust())
    handle = s.bridge.resolve_canonical_execution(s.auth, configuration_id=CFG)
    s.active = s.bridge.register_active_execution(
        s.store, handle, registered_at=at(0),
        execution_id=s.rt.native_execution_authorization_execution_id(s.auth.authorization_id))
    aid = s.active.active_execution_id

    # 3. Register the monitor as a source, admit its first report, declare the dependency.
    s.obs, s.deps = ObservationService(s.store), DependencyService(s.store)
    s.cont = ContinuationService(s.store, s.deps, s.bridge)
    s.obs.register_source(SourceRegistration(
        "reg-monitor-1", "site-monitor", ("observation",), ("charge_permit",), (SENSOR,),
        (CFG,), ("governance",), "site-signature", None, None, "current", ADMIN, 1),
        authority_proof=PROOF)
    report(s, "permit-1", "granted", at(0))
    s.deps.register_dependency_binding(
        active_execution_id=aid, configuration_id=CFG, subject_id=SENSOR,
        fact_kind="charge_permit", fact_id="site", registration_authority=ADMIN,
        authority_proof=PROOF, registered_at=at(0))

    # 4. Take supervisory ownership, and register the charger's control adapter.
    s.ctl = ControlService(s.store, s.deps, s.cont, s.bridge)
    s.ctl.register_supervisory_owner(owner_id="host-1", configuration_id=CFG,
                                     registration_authority=ADMIN, authority_proof=PROOF,
                                     registered_at=at(0))
    s.owner = s.ctl.acquire_ownership(active_execution_id=aid, owner_id="host-1",
                                      acquired_at=at(0))
    s.adapter = s.ctl.register_adapter(
        adapter_id="charger", configuration_id=CFG, target_handle_namespace="charger:",
        supported_semantic_controls=("pause", "cancel"),
        command_mapping={"pause": "pause", "cancel": "cancel"},
        vendor_command_mapping={"pause": "hold_charge", "cancel": "stop_charge"},
        controller_attestation_method="signed", control_region_evidence_method="charger-state",
        registration_authority=ADMIN, authority_proof=PROOF, registered_at=at(0))

    # 5. The host starts the charge by its own means. The episode stays open while it runs.
    s.job = s.charger.start()
    return s


def report(s, observation_id, value, when, source="site-monitor"):
    """One monitor report: submit it, assess its admission, commit the governed change."""
    o = ExternalObservation(observation_id, source, "charge_permit", "site", SENSOR, CFG,
                            value, None, when, when, when, {})
    s.obs.submit_observation(o)
    return s.obs.commit_admission_change(o, s.obs.assess_observation(o, assessed_at=when),
                                         committed_at=when)


def withdraw_permit(s):
    """6-7. The monitor withdraws the permit; the host checkpoints every affected execution."""
    change = report(s, "permit-2", "withdrawn", at(10))
    s.affected = s.deps.resolve_affected_executions(change, configuration_id=CFG)
    # The signal names the stage whose result the change invalidates. The permit is a
    # ceiling, and ceilings are enforced at Constraints.
    signal = GovernanceInvalidationSignal(
        "permit-withdrawn", "Constraints", "charging permit withdrawn", "monitor:site-monitor",
        change.observation_ids, (), s.active.execution_id, CFG)
    s.assessment = s.cont.checkpoint(
        active_execution_id=s.active.active_execution_id, invalidation_signals=(signal,),
        trigger_ids=(change.change_id,), checkpoint_at=at(10))
    return s.assessment


def stop(s, control="cancel"):
    """8. Fence unused authority, issue the stop, dispatch it, and record what happened."""
    aid, fence = s.active.active_execution_id, s.owner.owner_fence
    # Fencing is the owner's act, and the runtime does not gate it: fence only when the
    # checkpoint says the execution's authority must be fenced.
    s.invalidated = ()
    if s.assessment.authority_fence_required:
        s.invalidated = s.ctl.fence_execution_authority(
            active_execution_id=aid, owner_id="host-1", owner_fence=fence,
            reason="charging permit withdrawn")
    req = s.ctl.issue_control_request(
        assessment_id=s.assessment.assessment_id, active_execution_id=aid, owner_id="host-1",
        owner_fence=fence, requested_control=control, target_handle=s.job, created_at=at(10))
    s.attempt = s.ctl.dispatch_control_request(
        control_request_id=req.control_request_id, owner_id="host-1", owner_fence=fence,
        adapter_registration_id=s.adapter.adapter_registration_id, target_handle=s.job,
        control_region_at_request="cancelable", capability_evidence_ref="charger-caps-1",
        mapping_identity="charger-map-1", dispatched_at=at(10))
    outcome, evidence = s.charger.send(s.attempt.mapped_command, s.job)    # the charger acts
    s.enforcement = s.ctl.record_enforcement_outcome(
        control_attempt_id=s.attempt.control_attempt_id, outcome=outcome,
        controller_evidence_ref=f"{s.job}:ack", observed_control_region=s.charger.jobs[s.job],
        recorded_at=at(11), attestation_evidence=evidence)
    return s.enforcement


if __name__ == "__main__":
    s = start_supervised_charge()
    a = withdraw_permit(s)
    e = stop(s)
    print("affected executions:", len(s.affected))
    print("posture:            ", a.continuation_posture,
          "| fence required:", a.authority_fence_required)
    status = s.rt.native_execution_authorization_status(s.auth.authorization_id)
    print("authority:          ", status, f"({len(s.invalidated)} unused authorization fenced)")
    print("control:            ", s.attempt.requested_control, "->", s.attempt.mapped_command)
    print("controller outcome: ", e.outcome, "| attestation:", e.attestation_status)
    print("charging job:       ", s.charger.jobs[s.job])
