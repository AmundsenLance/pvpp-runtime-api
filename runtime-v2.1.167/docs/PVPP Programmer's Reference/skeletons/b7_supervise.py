"""B.7 Supervised execution: one licensed recharge, governed while it runs (Chapter 16)."""

from datetime import datetime, timezone

from pvpp_runtime import ExecutionBindingRegistry, ExecutionBindingIdentity
from pvpp_runtime import ExecutionObservation, GovernanceInvalidationSignal
from pvpp_runtime.supervision import (
    HostTrustProvider, SQLiteSupervisoryStore, CanonicalRuntimeBridge, ObservationService,
    SourceRegistration, ExternalObservation, DependencyService, ContinuationService,
    ControlService, EffectService,
)
from b2_cycle import run_cycle, make_request

CFG, SUBJECT = "site-1", "sensor-A"
ROOT, PROOF = "site-admin", "proof-from-host-vault"  # stands in for the host's identity system


def at(minute):  # every time in one fixed ISO-8601 form: times are compared as written (16.4)
    return f"2026-10-07T12:{minute:02d}:00+00:00"


def trust():  # 16.2: registration roots, controller and Layer-1 verifiers, trusted clock
    return HostTrustProvider(
        {ROOT: {"proof": PROOF, "roles": ("*",), "configurations": (CFG,)}},
        controller_attestation_verifier=lambda **r: r["attestation_evidence"] == "dock-signed",
        layer1_authority_verifier=lambda **r: r["authority_evidence"] == "ledger-signed",
        clock=lambda: datetime(2026, 10, 7, 12, 30, tzinfo=timezone.utc))


class Supervisor:
    def __init__(self):
        rt, integrated = run_cycle()  # selects graph:restore_battery (B.2)
        license = rt.build_execution_license_from_cycle(integrated.decision,
                                                        make_request().domain_frame)
        self.rt, self.bridge = rt, CanonicalRuntimeBridge(rt)  # 16.3
        episode = self.bridge.instantiate_execution("episode-s1", license, entry_sufficient=True,
                                                    max_steps=5).episode
        bindings = ExecutionBindingRegistry(tuple(rt.registry.actions))
        action = license.action_ids[0]
        bindings.register(ExecutionBindingIdentity("recharge-v1", action, "1.0"), lambda c: None)
        self.auth = self.bridge.issue_native_execution_authorization(
            episode, action, bindings, decision_cycle_id="cycle-1", configuration_id=CFG)
        self.store = SQLiteSupervisoryStore(":memory:", trust_provider=trust())  # 16.10
        handle = self.bridge.resolve_canonical_execution(self.auth, configuration_id=CFG)
        self.aid = self.bridge.register_active_execution(
            self.store, handle, registered_at=at(0),
            execution_id=rt.native_execution_authorization_execution_id(
                self.auth.authorization_id)).active_execution_id
        self.obs, self.deps = ObservationService(self.store), DependencyService(self.store)
        self.cont = ContinuationService(self.store, self.deps, self.bridge)
        self.ctl = ControlService(self.store, self.deps, self.cont, self.bridge)
        self.eff = EffectService(self.store, self.obs)
        for reg, source, role, kind, use in (  # 16.4: who may report what, for what use
                ("reg-m", "permit-monitor", "observation", "charge_permit", "governance"),
                ("reg-d", "dock", "effect", "charge_job", "effect_reconciliation")):
            self.obs.register_source(SourceRegistration(
                reg, source, (role,), (kind,), (SUBJECT,), (CFG,), (use,), "signed", None, None,
                "current", ROOT, 1), authority_proof=PROOF)
        self.report("permit-1", "granted", at(0))
        self.deps.register_dependency_binding(  # 16.5: declared, never discovered
            active_execution_id=self.aid, configuration_id=CFG, subject_id=SUBJECT,
            fact_kind="charge_permit", fact_id="site", registration_authority=ROOT,
            authority_proof=PROOF, registered_at=at(0))
        self.eff.register_retry_contract(  # 16.8: only before anything can have happened
            active_execution_id=self.aid, idempotent=False, reconciliation_required=True,
            registered_at=at(0))
        self.ctl.register_supervisory_owner(owner_id="sup-1", configuration_id=CFG,
                                            registration_authority=ROOT, authority_proof=PROOF,
                                            registered_at=at(0))
        self.owner = self.ctl.acquire_ownership(active_execution_id=self.aid, owner_id="sup-1",
                                                acquired_at=at(0))  # 16.7
        self.adapter = self.ctl.register_adapter(
            adapter_id="dock", configuration_id=CFG, target_handle_namespace="dock:",
            supported_semantic_controls=("hold", "cancel"),
            command_mapping={"hold": "hold", "cancel": "cancel"},
            vendor_command_mapping={"hold": "dock_hold", "cancel": "dock_stop"},
            controller_attestation_method="signed", control_region_evidence_method="dock-state",
            registration_authority=ROOT, authority_proof=PROOF, registered_at=at(0))
        self.job = "dock:job-1"  # the host starts the charge by its own means (16.12)

    def report(self, observation_id, value, when, source="permit-monitor"):
        o = ExternalObservation(observation_id, source, "charge_permit", "site", SUBJECT, CFG,
                                value, None, when, when, when, {})
        self.obs.submit_observation(o)
        admission = self.obs.assess_observation(o, assessed_at=when)
        return self.obs.commit_admission_change(o, admission, committed_at=when)

    def tick(self, event_id, minute, **flags):  # 16.6: progress reported at a checkpoint
        return self.cont.checkpoint(active_execution_id=self.aid, checkpoint_at=at(minute),
                                    observation=ExecutionObservation(event_id, **flags))

    def withdraw(self, minute=5):  # the monitor reports; the host checkpoints each execution
        change = self.report("permit-2", "withdrawn", at(minute))
        signal = GovernanceInvalidationSignal(
            "permit-withdrawn", "Constraints", "charging permit withdrawn",
            "monitor:permit-monitor", change.observation_ids, (), None, CFG)
        return [self.cont.checkpoint(active_execution_id=aid, invalidation_signals=(signal,),
                                     trigger_ids=(change.change_id,), checkpoint_at=at(minute))
                for aid in self.deps.resolve_affected_executions(change, configuration_id=CFG)]

    def stop(self, assessment, control="cancel", owner=None):  # 16.7
        owner = owner or self.owner
        who = dict(owner_id=owner.owner_id, owner_fence=owner.owner_fence)
        if assessment.authority_fence_required:
            self.ctl.fence_execution_authority(active_execution_id=self.aid, reason="withdrawn",
                                               **who)
        req = self.ctl.issue_control_request(
            assessment_id=assessment.assessment_id, active_execution_id=self.aid,
            requested_control=control, target_handle=self.job, created_at=at(6), **who)
        attempt = self.ctl.dispatch_control_request(
            control_request_id=req.control_request_id, target_handle=self.job,
            adapter_registration_id=self.adapter.adapter_registration_id,
            control_region_at_request="interruptible", capability_evidence_ref="dock-caps",
            mapping_identity="dock-map-1", dispatched_at=at(6), **who)
        # The dock carries out attempt.mapped_command and reports; its report is evidence.
        return attempt, self.ctl.record_enforcement_outcome(
            control_attempt_id=attempt.control_attempt_id, outcome="completed",
            controller_evidence_ref="dock:job-1:ack", observed_control_region="stopped",
            recorded_at=at(7), attestation_evidence="dock-signed")

    def reconcile(self, state, minute=8):  # 16.8: what the world shows, from the dock
        e = self.eff.submit_effect_evidence(
            active_execution_id=self.aid, source_id="dock", configuration_id=CFG, state=state,
            realized_bundle_ref=None, evidence_ref=f"dock:job-1:report-{minute}",
            provenance="dock report", observed_at=at(minute), effective_at=at(minute),
            received_at=at(minute))
        return self.eff.reconcile_effect(active_execution_id=self.aid,
                                         effect_evidence_id=e.effect_evidence_id,
                                         updated_at=at(minute))


def interrupted():
    s = Supervisor()
    s.tick("charge-10pct", 2)
    (assessment,) = s.withdraw()
    attempt, enforcement = s.stop(assessment)
    return s, assessment, attempt, enforcement, s.reconcile("no_material_effect_evidenced")


def completed():
    s = Supervisor()
    s.tick("charge-10pct", 2)
    done = s.tick("charge-done", 9, completed=True)
    finality = s.eff.accept_canonical_finality(active_execution_id=s.aid, terminalized_at=at(9),
                                               continuation_assessment_id=done.assessment_id)
    effect = s.reconcile("completed_effect", minute=10)
    layer1 = s.eff.record_layer1_transition(  # the host applied it; this records it (16.8)
        active_execution_id=s.aid, effect_reconciliation_ref=effect.effect_record_id,
        prior_actual_state_ref="state-0", next_actual_state_ref="state-0:next",
        transition_time=at(11), evidence_ref="ledger:entry-7", provenance="host ledger",
        configuration_id=CFG, authority_evidence="ledger-signed")
    return s, done, finality, effect, layer1


if __name__ == "__main__":
    s, a, attempt, enf, eff = interrupted()
    print("interrupted:", a.continuation_posture, a.authority_fence_required,
          s.rt.native_execution_authorization_status(s.auth.authorization_id))
    print("  stop:", attempt.mapped_command, enf.outcome, enf.attestation_status)
    safe = s.eff.assert_retry_safe(active_execution_id=s.aid)
    print("  effect:", eff.state, eff.unresolved, safe)
    s, done, fin, eff, l1 = completed()
    print("completed:", done.epsilon_status, fin.epsilon_terminal_status, eff.state,
          l1.next_actual_state_ref)
