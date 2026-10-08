"""Host-configured trust boundary for Runtime 2.2 supervisory integration.

PV-PP does not invent external identity or cryptographic trust. The host supplies
root registration credentials and verifier callbacks. Runtime services resolve
caller claims through this provider before treating them as authoritative.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Callable, Mapping, Iterable, Any


class HostTrustProvider:
    """Out-of-band host trust configuration.

    roots maps authority_id -> {"proof": opaque, "roles": iterable[str],
    "configurations": iterable[str] | None}. A role/configuration wildcard '*'
    is supported. Opaque proof comparison is for the reference implementation;
    production deployments may supply stronger host/IAM wrappers around this API.
    """
    def __init__(self, roots: Mapping[str, Mapping[str, Any]] | None = None, *,
                 controller_attestation_verifier: Callable[..., bool] | None = None,
                 layer1_authority_verifier: Callable[..., bool] | None = None,
                 clock: Callable[[], datetime] | None = None):
        self._roots = {k: dict(v) for k, v in (roots or {}).items()}
        self._controller_verifier = controller_attestation_verifier
        self._layer1_verifier = layer1_authority_verifier
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def now(self) -> datetime:
        dt = self._clock()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def authorize_registration(self, authority_id: str, *, role: str, configuration_id: str | None, proof: Any) -> bool:
        root = self._roots.get(authority_id)
        if not root:
            return False
        if proof != root.get("proof"):
            return False
        roles = set(root.get("roles") or ())
        if "*" not in roles and role not in roles:
            return False
        configs = root.get("configurations")
        if configs is not None:
            configs = set(configs)
            if "*" not in configs and configuration_id not in configs:
                return False
        return True

    def verify_controller_attestation(self, *, adapter_registration, control_attempt, outcome: str,
                                      controller_evidence_ref: str | None, attestation_evidence: Any) -> bool:
        if self._controller_verifier is None:
            return False
        return bool(self._controller_verifier(
            adapter_registration=adapter_registration,
            control_attempt=control_attempt,
            outcome=outcome,
            controller_evidence_ref=controller_evidence_ref,
            attestation_evidence=attestation_evidence,
        ))

    def verify_layer1_authority(self, *, active_execution, effect_state, transition_time: str,
                                evidence_ref: str, authority_evidence: Any) -> bool:
        if self._layer1_verifier is None:
            return False
        return bool(self._layer1_verifier(
            active_execution=active_execution,
            effect_state=effect_state,
            transition_time=transition_time,
            evidence_ref=evidence_ref,
            authority_evidence=authority_evidence,
        ))
