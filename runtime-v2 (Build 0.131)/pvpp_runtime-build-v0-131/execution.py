from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping
from uuid import uuid4

from .models import ExecutionBindingAssessment, ExecutionBindingIdentity, ExecutionContext


@dataclass(frozen=True)
class _ExecutionBinding:
    identity: ExecutionBindingIdentity
    callable: Callable[..., Any]


class ExecutionBindingRegistry:
    """Separate registry for host callables associated with registered actions.

    Registration is not authorization.  This Phase-2 foundation deliberately has
    no invoke/execute method; a later build will resolve and invoke a binding only
    after canonical execution authority has been established.
    """

    def __init__(self, action_ids: tuple[str, ...] | list[str] | set[str]):
        self._action_ids = frozenset(str(x) for x in action_ids)
        self._bindings_by_id: dict[str, _ExecutionBinding] = {}
        self._binding_id_by_action: dict[str, str] = {}
        self._control_by_execution_id: dict[str, Any] = {}
        self._control_events_by_execution_id: dict[str, list[Any]] = {}

    def assess_identity(self, identity: ExecutionBindingIdentity) -> ExecutionBindingAssessment:
        violations: list[str] = []
        if not identity.binding_id.strip():
            violations.append("binding_id_required")
        if not identity.action_id.strip():
            violations.append("action_id_required")
        elif identity.action_id not in self._action_ids:
            violations.append("action_not_registered")
        if not identity.implementation_version.strip():
            violations.append("implementation_version_required")
        if len(set(identity.provenance_ids)) != len(identity.provenance_ids):
            violations.append("duplicate_provenance_identity")
        return ExecutionBindingAssessment(
            valid=not violations,
            binding_id=identity.binding_id,
            action_id=identity.action_id,
            violations=tuple(violations),
            notes=("binding registration does not confer execution authority",),
        )

    def register(self, identity: ExecutionBindingIdentity, target: Callable[..., Any]) -> ExecutionBindingAssessment:
        assessment = self.assess_identity(identity)
        if not assessment.valid:
            raise ValueError(f"invalid execution binding: {assessment.violations}")
        if not callable(target):
            raise TypeError("execution binding target must be callable")
        if identity.binding_id in self._bindings_by_id:
            raise ValueError(f"execution binding already registered: {identity.binding_id}")
        if identity.action_id in self._binding_id_by_action:
            raise ValueError(f"execution binding already registered for action: {identity.action_id}")
        self._bindings_by_id[identity.binding_id] = _ExecutionBinding(identity, target)
        self._binding_id_by_action[identity.action_id] = identity.binding_id
        return assessment

    def identity_for_action(self, action_id: str) -> ExecutionBindingIdentity | None:
        binding_id = self._binding_id_by_action.get(action_id)
        if binding_id is None:
            return None
        return self._bindings_by_id[binding_id].identity

    def identity(self, binding_id: str) -> ExecutionBindingIdentity | None:
        binding = self._bindings_by_id.get(binding_id)
        return None if binding is None else binding.identity

    def registered_identities(self) -> tuple[ExecutionBindingIdentity, ...]:
        return tuple(x.identity for x in self._bindings_by_id.values())

    def create_context(
        self,
        *,
        action_id: str,
        decision_cycle_id: str,
        attempt: int = 1,
        correlation_id: str | None = None,
        configuration_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> ExecutionContext:
        identity = self.identity_for_action(action_id)
        if identity is None:
            raise KeyError(f"no execution binding registered for action: {action_id}")
        if not decision_cycle_id.strip():
            raise ValueError("decision_cycle_id required")
        if attempt < 1:
            raise ValueError("execution attempt must be >= 1")
        return ExecutionContext(
            execution_id=execution_id or f"exec-{uuid4()}",
            action_id=action_id,
            binding_id=identity.binding_id,
            decision_cycle_id=decision_cycle_id,
            attempt=attempt,
            correlation_id=correlation_id,
            configuration_id=configuration_id,
            metadata={} if metadata is None else dict(metadata),
        )

    def control_state(self, execution_id: str):
        from .models import NativeExecutionControlState
        return self._control_by_execution_id.get(execution_id, NativeExecutionControlState(execution_id))

    def set_control_state(self, execution_id: str, state: str, *, reason: str | None = None, requested_by: str | None = None, evidence_ids: tuple[str, ...] = ()):
        from .models import NativeExecutionControlEvent, NativeExecutionControlState
        allowed={"ready","paused","aborted","reauthorization_required"}
        if state not in allowed:
            raise ValueError(f"unsupported execution control state: {state}")
        if not execution_id.strip():
            raise ValueError("execution_id required")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("duplicate execution-control evidence identity")
        prior=self.control_state(execution_id)
        control=NativeExecutionControlState(execution_id,state,reason,requested_by,(
            "control posture is a synchronous pre-invocation gate; no asynchronous cancellation is implied",
        ))
        self._control_by_execution_id[execution_id]=control
        event=NativeExecutionControlEvent(
            event_id=f"ctl-{uuid4()}", execution_id=execution_id, prior_state=prior.state, new_state=state,
            reason=reason or ("ready" if state == "ready" else "unspecified"), requested_by=requested_by, evidence_ids=tuple(evidence_ids),
            notes=("bookkeeping only; canonical re-entry stage is not determined here",),
        )
        self._control_events_by_execution_id.setdefault(execution_id,[]).append(event)
        return control

    def control_history(self, execution_id: str):
        return tuple(self._control_events_by_execution_id.get(execution_id, ()))

    def build_reauthorization_handoff(self, context: ExecutionContext, *, reason: str | None = None, requested_by: str | None = None, evidence_ids: tuple[str, ...] = (), handoff_id: str | None = None):
        from .models import NativeReauthorizationHandoff
        control=self.control_state(context.execution_id)
        if control.state != "reauthorization_required":
            raise ValueError("execution is not in reauthorization_required state")
        resolved_reason=(reason or control.reason or "").strip()
        if not resolved_reason:
            raise ValueError("reauthorization handoff requires a reason")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("duplicate reauthorization evidence identity")
        return NativeReauthorizationHandoff(
            handoff_id or f"reauth-{uuid4()}", context.execution_id, context.action_id, context.binding_id,
            context.decision_cycle_id, resolved_reason, requested_by or control.requested_by, tuple(evidence_ids),
            context.correlation_id, context.configuration_id, True,
            ("return to canonical governance for fresh authorization",
             "earliest-invalidated-stage determination is intentionally deferred",),
        )

    def telemetry(self, context: ExecutionContext, result, *, telemetry_id: str | None = None):
        from .models import NativeExecutionResult, NativeExecutionTelemetry
        if not isinstance(result, NativeExecutionResult):
            raise TypeError("native execution result required")
        if (result.execution_id,result.action_id,result.binding_id) != (context.execution_id,context.action_id,context.binding_id):
            raise ValueError("native result identity does not match execution context")
        return NativeExecutionTelemetry(
            telemetry_id or f"tel-{uuid4()}", context.execution_id, context.action_id, context.binding_id,
            context.decision_cycle_id, context.attempt, result.status, result.external_effect_possible,
            result.completed, result.failure_stage, result.error_type, result.error_message,
            context.correlation_id, context.configuration_id, tuple(result.notes)+(
                "telemetry is execution evidence, not a Layer-1 transition",
            )
        )

    def _invoke_authorized_context(self, context: ExecutionContext, *args: Any, **kwargs: Any):
        """Invoke exactly the binding named by ``context`` and normalize outcome.

        Internal callable-entering primitive. Runtime authorization must already
        have been validated and consumed before this method is called.
        """
        from .models import (
            CleanExecutionFailure,
            CompletedInvalidExecution,
            IndeterminateExecutionFailure,
            NativeExecutionResult,
        )

        control = self.control_state(context.execution_id)
        if control.state == "paused":
            raise RuntimeError("native execution is paused")
        if control.state == "aborted":
            raise RuntimeError("native execution is aborted")
        if control.state == "reauthorization_required":
            raise RuntimeError("native execution requires reauthorization")

        binding = self._bindings_by_id.get(context.binding_id)
        if binding is None:
            raise KeyError(f"execution binding not registered: {context.binding_id}")
        if binding.identity.action_id != context.action_id:
            raise ValueError("execution context action/binding mismatch")

        try:
            value = binding.callable(context, *args, **kwargs)
            return NativeExecutionResult(
                execution_id=context.execution_id,
                action_id=context.action_id,
                binding_id=context.binding_id,
                status="succeeded",
                return_value=value,
                external_effect_possible=True,
                completed=True,
                transition_valid=None,
                notes=("native invocation completed; Layer-1 realization remains separately authoritative",),
            )
        except CleanExecutionFailure as exc:
            return NativeExecutionResult(
                context.execution_id, context.action_id, context.binding_id,
                "failed_cleanly", failure_stage="local_callable",
                error_type=type(exc).__name__, error_message=str(exc),
                external_effect_possible=False, completed=False,
                notes=("binding supplied clean-failure evidence",),
            )
        except CompletedInvalidExecution as exc:
            return NativeExecutionResult(
                context.execution_id, context.action_id, context.binding_id,
                "completed_invalid", failure_stage="validation",
                error_type=type(exc).__name__, error_message=str(exc),
                external_effect_possible=True, completed=True, transition_valid=False,
            )
        except (IndeterminateExecutionFailure, TimeoutError, ConnectionError) as exc:
            return NativeExecutionResult(
                context.execution_id, context.action_id, context.binding_id,
                "indeterminate", failure_stage="transport" if isinstance(exc, (TimeoutError, ConnectionError)) else "external_unknown",
                error_type=type(exc).__name__, error_message=str(exc),
                external_effect_possible=True, completed=False,
                notes=("absence of response is not evidence of absence of external effect",),
            )
        except Exception as exc:
            # An arbitrary exception cannot prove that a callable produced no
            # external effect before failing; default conservatively to unknown.
            return NativeExecutionResult(
                context.execution_id, context.action_id, context.binding_id,
                "indeterminate", failure_stage="local_callable",
                error_type=type(exc).__name__, error_message=str(exc),
                external_effect_possible=True, completed=False,
                notes=("unclassified callable failure; external effect status unknown",),
            )

    def invoke(self, context: ExecutionContext, *args: Any, **kwargs: Any):
        """Deprecated public route: contexts carry no native invocation authority."""
        raise RuntimeError(
            "native execution authorization required; public registry.invoke is fail-closed"
        )

    def build_layer1_handoff(
        self,
        context: ExecutionContext,
        result,
        *,
        selected_policy_id: str,
        realized_pv_bundles: tuple[Mapping[str, Any], ...] = (),
        execution_information: tuple[Mapping[str, Any], ...] = (),
        mandatory_recovery_action_ids: tuple[str, ...] = (),
    ):
        """Build a host-owned Layer-1 transition packet after native invocation.

        This method performs no state mutation and does not call a transition
        service.  It only translates one normalized native result into the
        existing immutable Layer1TransitionHandoff boundary while preserving
        execution identity as explicit execution information.

        ``indeterminate`` outcomes always request upstream return.  Clean
        failures have no asserted external effect and therefore are not eligible
        for a Layer-1 transition handoff.  A succeeded invocation is only
        technical completion; the host-owned Layer-1 transition remains the
        authority for actual persistent-state realization.
        """
        from .models import Layer1TransitionHandoff, NativeExecutionResult
        if not isinstance(result, NativeExecutionResult):
            raise TypeError("native execution result required")
        if result.execution_id != context.execution_id:
            raise ValueError("native result execution_id does not match context")
        if result.action_id != context.action_id or result.binding_id != context.binding_id:
            raise ValueError("native result action/binding identity does not match context")
        if not selected_policy_id.strip():
            raise ValueError("selected_policy_id required for Layer-1 handoff")
        if result.status == "failed_cleanly":
            raise ValueError("clean failure has no material external effect to transition")
        if result.status not in {"succeeded", "indeterminate", "completed_invalid"}:
            raise ValueError(f"unsupported native execution status: {result.status}")

        status_map = {
            "succeeded": "completed",
            "indeterminate": "partial_realization",
            "completed_invalid": "failed",
        }
        return_upstream = result.status in {"indeterminate", "completed_invalid"}
        identity_event = {
            "kind": "native_execution_identity",
            "execution_id": context.execution_id,
            "action_id": context.action_id,
            "binding_id": context.binding_id,
            "decision_cycle_id": context.decision_cycle_id,
            "attempt": context.attempt,
            "correlation_id": context.correlation_id,
            "configuration_id": context.configuration_id,
            "native_status": result.status,
            "external_effect_possible": result.external_effect_possible,
            "completed": result.completed,
        }
        return Layer1TransitionHandoff(
            episode_id=context.execution_id,
            selected_policy_id=selected_policy_id,
            execution_status=status_map[result.status],
            execution_path=(context.action_id,),
            realized_pv_bundles=tuple(dict(x) for x in realized_pv_bundles),
            execution_information=(identity_event,) + tuple(dict(x) for x in execution_information),
            return_upstream=return_upstream,
            notes=(
                "native invocation handoff only; Layer-1 host remains transition authority",
                "technical callable completion is not proof of valid persistent-state realization",
            ),
            licensed_action_ids=(context.action_id,),
            mandatory_recovery_action_ids=tuple(mandatory_recovery_action_ids),
        )

    def epsilon_observation(
        self,
        context: ExecutionContext,
        result,
        *,
        telemetry=None,
        event_id: str | None = None,
        realized_pv_bundle: Mapping[str, Any] | None = None,
        information: Mapping[str, Any] | None = None,
    ):
        """Translate one native result into the canonical epsilon observation path.

        This is an evidence adapter only.  It neither advances epsilon nor mutates
        Layer-1 state.  The caller supplies the returned ExecutionObservation to
        ``PVPPRuntime.advance_execution`` so the existing epsilon trace remains the
        single canonical execution-evidence chain.
        """
        from .models import ExecutionObservation, NativeExecutionResult, NativeExecutionTelemetry
        if not isinstance(result, NativeExecutionResult):
            raise TypeError("native execution result required")
        if (result.execution_id, result.action_id, result.binding_id) != (context.execution_id, context.action_id, context.binding_id):
            raise ValueError("native result identity does not match execution context")
        if telemetry is None:
            telemetry = self.telemetry(context, result)
        if not isinstance(telemetry, NativeExecutionTelemetry):
            raise TypeError("native execution telemetry required")
        if (telemetry.execution_id, telemetry.action_id, telemetry.binding_id) != (context.execution_id, context.action_id, context.binding_id):
            raise ValueError("native telemetry identity does not match execution context")
        if telemetry.status != result.status:
            raise ValueError("native telemetry status does not match native result")
        if result.status not in {"succeeded", "failed_cleanly", "indeterminate", "completed_invalid"}:
            raise ValueError(f"unsupported native execution status: {result.status}")

        info = {
            "kind": "native_execution_telemetry",
            "telemetry_id": telemetry.telemetry_id,
            "execution_id": context.execution_id,
            "action_id": context.action_id,
            "binding_id": context.binding_id,
            "decision_cycle_id": context.decision_cycle_id,
            "attempt": context.attempt,
            "correlation_id": context.correlation_id,
            "configuration_id": context.configuration_id,
            "native_status": result.status,
            "external_effect_possible": result.external_effect_possible,
            "native_completed": result.completed,
            "failure_stage": result.failure_stage,
            "error_type": result.error_type,
            "error_message": result.error_message,
        }
        if information:
            info.update(dict(information))
        common = dict(
            event_id=event_id or telemetry.telemetry_id,
            realized_pv_bundle={} if realized_pv_bundle is None else dict(realized_pv_bundle),
            information=info,
        )
        if result.status == "succeeded":
            return ExecutionObservation(completed=True, completion_sufficient=True, **common)
        if result.status == "failed_cleanly":
            return ExecutionObservation(failed=True, **common)
        if result.status == "indeterminate":
            # Unknown external effect is not laundered into a known failure.
            # Epsilon must terminate and return upstream; any observed realized
            # bundle makes that posture partial_realization rather than abort.
            return ExecutionObservation(continuation_sufficient=False, **common)
        # Technical completion with invalid realization must return upstream
        # through epsilon's completion-sufficiency boundary.
        return ExecutionObservation(completed=True, completion_sufficient=False, **common)
