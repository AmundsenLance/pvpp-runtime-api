"""Phase-2 trusted canonical bridge for Runtime 2.2 supervision.

The bridge observes exact objects returned by supported v0.141 operations.  It does
not inspect or mutate v0.141 private ledgers.  Handles are supervisory references,
not substitutes for NativeExecutionAuthorization.
"""
from __future__ import annotations
from dataclasses import replace
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from pvpp_runtime.models import ExecutionEpisode, ExecutionObservation, NativeExecutionAuthorization
from .models import CanonicalExecutionHandle, SemanticId
from .observation_value import canonical_execution_observation_payload


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CanonicalResolutionError(RuntimeError): pass
class ConfigurationConflict(CanonicalResolutionError): pass


class CanonicalRuntimeBridge:
    """Trusted wrapper that records exact canonical objects as they cross public APIs."""
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self._episodes: dict[str, ExecutionEpisode] = {}
        self._authorizations: dict[str, NativeExecutionAuthorization] = {}
        self._handles: dict[str, CanonicalExecutionHandle] = {}
        self._active_by_authorization: dict[str, str] = {}
        self._active_by_episode: dict[str, str] = {}
        self._advance_permits: dict[str, tuple[str, str]] = {}
        self._advance_calls_entered: set[str] = set()
        self._indeterminate_episodes: set[str] = set()

    def instantiate_execution(self, episode_id: str, license, **kwargs):
        result = self.runtime.instantiate_execution(episode_id, license, **kwargs)
        self._episodes[result.episode.episode_id] = result.episode
        return result

    def authorize_supervised_advance(self, store, *, active_execution_id: str, intent_id: str) -> None:
        rec = store.get_active_execution(active_execution_id)
        if rec is None:
            raise CanonicalResolutionError("stale_lineage: active execution missing")
        if self._active_by_episode.get(rec.episode_id) != active_execution_id:
            raise CanonicalResolutionError("canonical_resolution_failed: supervised episode registration unavailable")
        if self.episode_is_indeterminate(rec.episode_id):
            raise CanonicalResolutionError("canonical_state_indeterminate: supervised episode requires terminal recovery")
        episode = self.current_episode(rec.episode_id)
        if not store.continuation_intent_is_prepared(active_execution_id=active_execution_id, intent_id=intent_id, expected_step=episode.step_count):
            raise CanonicalResolutionError("continuation_intent_required")
        self._advance_permits[episode.episode_id] = (active_execution_id, intent_id)


    @staticmethod
    def validate_advance_preconditions(episode: ExecutionEpisode, observation: ExecutionObservation) -> None:
        """Mirror every frozen-v0.141 operation known to occur before lineage mutation.

        The bridge records canonical call entry only after this validation succeeds.
        This prevents deterministic caller/input errors from being misclassified as
        indeterminate canonical mutation.
        """
        if not isinstance(episode, ExecutionEpisode):
            raise TypeError("execution episode required")
        if not episode.active:
            raise ValueError("execution episode is already terminal")
        if not isinstance(observation, ExecutionObservation):
            raise TypeError("execution observation required")
        # Validate the entire supervised observation identity/value domain before
        # recording canonical call entry. This is stricter than frozen v0.141's
        # generic Mapping acceptance by design: Runtime 2.2 idempotency requires
        # deterministic plain-data identity and never falls back to object repr().
        canonical_execution_observation_payload(observation)

    def advance_execution(self, episode: ExecutionEpisode, observation):
        if self.episode_is_indeterminate(episode.episode_id):
            raise CanonicalResolutionError("canonical_state_indeterminate: canonical episode state is unknown")
        current = self._episodes.get(episode.episode_id)
        if current is not episode:
            raise CanonicalResolutionError("canonical_resolution_failed: episode is not current bridge object")
        # Validate the frozen-kernel pre-mutation contract before consuming a
        # supervised permit or recording that the canonical call was entered.
        self.validate_advance_preconditions(episode, observation)
        supervised = self._active_by_episode.get(episode.episode_id)
        if supervised is not None:
            permit = self._advance_permits.pop(episode.episode_id, None)
            if permit is None or permit[0] != supervised:
                raise CanonicalResolutionError("supervised_advance_required: actively supervised episode must advance through ContinuationService")
        self._advance_calls_entered.add(episode.episode_id)
        try:
            result = self.runtime.advance_execution(episode, observation)
        except Exception:
            # Once the canonical call was entered, an exception does not prove that the
            # runtime failed before mutation.  Preserve that uncertainty explicitly.
            self._indeterminate_episodes.add(episode.episode_id)
            raise
        finally:
            self._advance_calls_entered.discard(episode.episode_id)
        self._episodes[result.episode.episode_id] = result.episode
        return result

    def issue_native_execution_authorization(self, episode: ExecutionEpisode, action_id: str, binding_registry, **kwargs):
        if self.episode_is_indeterminate(episode.episode_id):
            raise CanonicalResolutionError("canonical_state_indeterminate: cannot issue authorization")
        current = self._episodes.get(episode.episode_id)
        if current is not episode:
            raise CanonicalResolutionError("canonical_resolution_failed: episode is not current bridge object")
        auth = self.runtime.issue_native_execution_authorization(episode, action_id, binding_registry, **kwargs)
        self._authorizations[auth.authorization_id] = auth
        return auth

    def resolve_canonical_execution(self, authorization: NativeExecutionAuthorization, *, configuration_id: str | None = None) -> CanonicalExecutionHandle:
        exact = self._authorizations.get(authorization.authorization_id)
        if exact is not authorization:
            raise CanonicalResolutionError("canonical_resolution_failed: authorization is not exact bridge object")
        status = self.runtime.native_execution_authorization_status(authorization.authorization_id)
        if status != "issued":
            raise CanonicalResolutionError(f"canonical_resolution_failed: authorization status is {status}")
        if self.episode_is_indeterminate(authorization.episode_id):
            raise CanonicalResolutionError("canonical_state_indeterminate: canonical episode state is unknown")
        episode = self._episodes.get(authorization.episode_id)
        if episode is None or not episode.active:
            raise CanonicalResolutionError("canonical_resolution_failed: episode is stale or terminal")
        if configuration_id != authorization.configuration_id:
            raise ConfigurationConflict("configuration_conflict")
        if authorization.action_id not in episode.license.action_ids:
            raise CanonicalResolutionError("canonical_resolution_failed: action is not in canonical license")
        handle = CanonicalExecutionHandle(
            canonical_handle_id=SemanticId.new("ch").value,
            episode_id=episode.episode_id,
            license_object_id=id(episode.license),
            selected_policy_id=authorization.selected_policy_id,
            action_id=authorization.action_id,
            decision_cycle_id=authorization.decision_cycle_id,
            configuration_id=authorization.configuration_id,
            attempt=authorization.attempt,
            binding_id=authorization.binding_id,
            binding_implementation_version=authorization.binding_implementation_version,
            authorization_id=authorization.authorization_id,
            status="current",
            resolved_at=_now(),
        )
        self._handles[handle.canonical_handle_id] = handle
        return handle

    def refresh_canonical_handle(self, handle: CanonicalExecutionHandle) -> CanonicalExecutionHandle:
        auth = self._authorizations.get(handle.authorization_id)
        if auth is None:
            raise CanonicalResolutionError("canonical_resolution_failed")
        fresh = self.resolve_canonical_execution(auth, configuration_id=handle.configuration_id)
        refreshed = replace(fresh, canonical_handle_id=handle.canonical_handle_id)
        self._handles.pop(fresh.canonical_handle_id, None)
        self._handles[handle.canonical_handle_id] = refreshed
        return refreshed

    def register_active_execution(self, store, handle: CanonicalExecutionHandle, *, execution_id: str, registered_at: str):
        """Register only a handle produced and still owned by this trusted bridge."""
        exact = self._handles.get(handle.canonical_handle_id)
        if exact is not handle:
            raise CanonicalResolutionError("canonical_resolution_failed: handle is not exact bridge object")
        self.current_handle(handle.canonical_handle_id)
        rec = store._register_resolved_active_execution(handle, execution_id=execution_id, registered_at=registered_at)
        store._bind_canonical_bridge(rec.active_execution_id, self, handle)
        self._active_by_authorization[handle.authorization_id] = rec.active_execution_id
        self._active_by_episode[handle.episode_id] = rec.active_execution_id
        return rec

    def invoke_registered_native(self, store, active_execution_id: str, authorization: NativeExecutionAuthorization, binding_registry, *args, **kwargs):
        record = store.get_active_execution(active_execution_id)
        if record is None:
            raise CanonicalResolutionError("pre_entry_registration_required")
        if record.authorization_id != authorization.authorization_id:
            raise CanonicalResolutionError("active_execution_authorization_mismatch")
        if self.episode_is_indeterminate(record.episode_id):
            raise CanonicalResolutionError("canonical_state_indeterminate: native invocation fenced")
        handle = self._handles.get(record.canonical_handle_id)
        if handle is None:
            raise CanonicalResolutionError("canonical_resolution_failed: handle unavailable")
        self.refresh_canonical_handle(handle)
        exact = self._authorizations.get(authorization.authorization_id)
        if exact is not authorization:
            raise CanonicalResolutionError("canonical_resolution_failed: exact native authorization required")
        store.record_supervised_native_invocation(active_execution_id=active_execution_id, started_at=_now())
        return self.runtime.invoke_authorized_native(authorization, binding_registry, *args, **kwargs)

    def invoke_authorized_native(self, authorization: NativeExecutionAuthorization, binding_registry, *args, **kwargs):
        if self.episode_is_indeterminate(authorization.episode_id):
            raise CanonicalResolutionError("canonical_state_indeterminate: native invocation fenced")
        exact = self._authorizations.get(authorization.authorization_id)
        if exact is not authorization:
            raise CanonicalResolutionError("canonical_resolution_failed: exact native authorization required")
        if authorization.authorization_id in self._active_by_authorization:
            raise CanonicalResolutionError("registered execution requires invoke_registered_native")
        return self.runtime.invoke_authorized_native(authorization, binding_registry, *args, **kwargs)

    def current_handle(self, canonical_handle_id: str) -> CanonicalExecutionHandle:
        handle = self._handles.get(canonical_handle_id)
        if handle is None:
            raise CanonicalResolutionError("canonical_resolution_failed: handle unavailable")
        return self.refresh_canonical_handle(handle)

    def authorization_status(self, authorization_id: str) -> str | None:
        """Return the canonical runtime's authoritative native-authorization lifecycle status."""
        return self.runtime.native_execution_authorization_status(authorization_id)


    def episode_is_indeterminate(self, episode_id: str) -> bool:
        return episode_id in self._indeterminate_episodes

    def advance_call_was_entered(self, episode_id: str) -> bool:
        """Diagnostic surface: true only while the bridge is inside runtime.advance_execution."""
        return episode_id in self._advance_calls_entered

    def episode_state(self, episode_id: str) -> ExecutionEpisode:
        episode = self._episodes.get(episode_id)
        if episode is None:
            raise CanonicalResolutionError("stale_lineage: episode unavailable")
        return episode

    def episode_step(self, episode_id: str) -> int:
        return self.episode_state(episode_id).step_count

    def current_episode(self, episode_id: str) -> ExecutionEpisode:
        episode = self.episode_state(episode_id)
        if not episode.active:
            raise CanonicalResolutionError("stale_lineage: episode is not current and active")
        return episode
