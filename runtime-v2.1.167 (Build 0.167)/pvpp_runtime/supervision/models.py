"""Phase-1 durable supervisory records for the Runtime 2.2 successor line."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class SemanticId:
    """Stable semantic identity; identity alone carries no governance authority."""

    value: str

    @classmethod
    def new(cls, prefix: str) -> "SemanticId":
        if not prefix or not prefix.replace("_", "").isalnum():
            raise ValueError("prefix must be non-empty alphanumeric/underscore")
        return cls(f"{prefix}_{uuid4().hex}")

    def __post_init__(self) -> None:
        if not self.value or self.value.strip() != self.value:
            raise ValueError("semantic id must be a non-empty normalized string")


@dataclass(frozen=True, slots=True)
class ConfigurationState:
    """Durable configuration/version record used as a supervisory CAS boundary."""

    configuration_id: str
    version: int
    payload: Mapping[str, Any]
    updated_at: str

    def __post_init__(self) -> None:
        if not self.configuration_id:
            raise ValueError("configuration_id is required")
        if self.version < 1:
            raise ValueError("version must be >= 1")


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Append-only supervisory audit event; an event is evidence, not authority."""

    event_id: str
    event_kind: str
    occurred_at: str
    configuration_id: str | None
    subject_id: str | None
    payload: Mapping[str, Any]

    @classmethod
    def create(
        cls,
        event_kind: str,
        *,
        configuration_id: str | None = None,
        subject_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
        event_id: str | None = None,
    ) -> "AuditEvent":
        if not event_kind:
            raise ValueError("event_kind is required")
        return cls(
            event_id=event_id or SemanticId.new("evt").value,
            event_kind=event_kind,
            occurred_at=_utc_now(),
            configuration_id=configuration_id,
            subject_id=subject_id,
            payload=dict(payload or {}),
        )

@dataclass(frozen=True, slots=True)
class CanonicalExecutionHandle:
    """Trusted supervisory reference to exact canonical lineage; never execution authority."""
    canonical_handle_id: str
    episode_id: str
    license_object_id: int
    selected_policy_id: str
    action_id: str
    decision_cycle_id: str
    configuration_id: str | None
    attempt: int
    binding_id: str
    binding_implementation_version: str
    authorization_id: str
    status: str
    resolved_at: str


@dataclass(frozen=True, slots=True)
class ActiveExecutionRecord:
    """Durable supervisory record for one exact canonical execution attempt."""
    active_execution_id: str
    canonical_handle_id: str
    episode_id: str
    authorization_id: str
    execution_id: str
    action_id: str
    decision_cycle_id: str
    configuration_id: str | None
    attempt: int
    binding_id: str
    status: str
    version: int
    registered_at: str

@dataclass(frozen=True, slots=True)
class SupervisoryOwnershipRecord:
    ownership_id: str; active_execution_id: str; execution_id: str; attempt: int
    owner_id: str; owner_fence: int; acquired_at: str; expires_at: str | None
    store_version: int; status: str

@dataclass(frozen=True, slots=True)
class AdapterRegistration:
    adapter_registration_id: str; adapter_id: str; configuration_id: str | None
    target_handle_namespace: str; supported_semantic_controls: tuple[str, ...]
    command_mapping: Mapping[str, str]; vendor_command_mapping: Mapping[str, str]; controller_attestation_method: str
    control_region_evidence_method: str; status: str; version: int
    registration_authority: str; registered_at: str

@dataclass(frozen=True, slots=True)
class ExecutionControlRequest:
    control_request_id: str; active_execution_id: str; execution_id: str; attempt: int
    owner_id: str; owner_fence: int; governance_snapshot_id: str
    continuation_assessment_id: str; requested_control: str; target_handle: str
    configuration_id: str | None; created_at: str; trusted_created_at: str | None = None

@dataclass(frozen=True, slots=True)
class ControlAttemptRecord:
    control_attempt_id: str; control_request_id: str; adapter_registration_id: str
    adapter_version: int; target_handle: str; requested_control: str; mapped_command: str
    control_region_at_request: str; capability_evidence_ref: str | None
    mapping_identity: str; dispatched_at: str; dispatch_result: str
    owner_id: str; owner_fence: int; trusted_dispatched_at: str | None = None

@dataclass(frozen=True, slots=True)
class EnforcementRecord:
    enforcement_record_id: str; control_request_id: str; control_attempt_id: str
    adapter_registration_id: str; outcome: str; attestation_status: str
    controller_evidence_ref: str | None; observed_control_region: str | None
    recorded_at: str; owner_fence_at_attempt: int
