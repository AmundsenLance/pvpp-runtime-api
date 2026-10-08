"""Canonical supervised execution-observation value domain for Runtime 2.2.

The supervision layer accepts deterministic plain-data values only and freezes
caller-owned mappings/containers before any durable intent or canonical call.
Identity and canonical execution therefore consume the same supervised snapshot.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

from pvpp_runtime.models import ExecutionObservation


class ObservationValidationError(ValueError):
    """ExecutionObservation is outside the supervised plain-data value domain."""


MAX_OBSERVATION_NESTING = 64
MAX_OBSERVATION_INTEGER_BITS = 4096


def _validate_unicode(value: str, *, path: str) -> None:
    try:
        value.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise ObservationValidationError(
            f"invalid execution observation {path}: string must be valid Unicode"
        ) from exc


def _snapshot_and_encode(
    value: Any,
    *,
    path: str,
    depth: int,
    active_ids: set[int],
) -> tuple[Any, dict]:
    """Freeze one supported value and return its type-strict identity encoding."""
    if depth > MAX_OBSERVATION_NESTING:
        raise ObservationValidationError(
            f"invalid execution observation {path}: nesting depth exceeds {MAX_OBSERVATION_NESTING}"
        )

    if value is None:
        return None, {"type": "none", "value": None}
    if type(value) is bool:
        return value, {"type": "bool", "value": value}
    if type(value) is int:
        # Bound pathological integers before identity encoding.  Within the supported
        # domain, hexadecimal encoding avoids Python's decimal int-to-string digit
        # limit while preserving exact, type-strict integer identity.
        if value.bit_length() > MAX_OBSERVATION_INTEGER_BITS:
            raise ObservationValidationError(
                f"invalid execution observation {path}: integer exceeds {MAX_OBSERVATION_INTEGER_BITS}-bit limit"
            )
        sign = -1 if value < 0 else (1 if value > 0 else 0)
        return value, {"type": "int", "sign": sign, "hex": format(abs(value), "x")}
    if type(value) is float:
        if math.isnan(value):
            encoded = "nan"
        elif math.isinf(value):
            encoded = "+inf" if value > 0 else "-inf"
        else:
            encoded = value.hex()  # exact binary-float identity, including signed zero
        return value, {"type": "float", "value": encoded}
    if type(value) is str:
        _validate_unicode(value, path=path)
        return value, {"type": "str", "value": value}

    is_list = type(value) is list
    is_tuple = type(value) is tuple
    is_mapping = isinstance(value, Mapping)
    if not (is_list or is_tuple or is_mapping):
        raise ObservationValidationError(
            f"invalid execution observation {path}: unsupported value type "
            f"{type(value).__module__}.{type(value).__qualname__}"
        )

    oid = id(value)
    if oid in active_ids:
        raise ObservationValidationError(
            f"invalid execution observation {path}: cyclic value"
        )
    active_ids.add(oid)
    try:
        if is_list or is_tuple:
            snapshot_items = []
            encoded_items = []
            for i, child in enumerate(value):
                snap, enc = _snapshot_and_encode(
                    child,
                    path=f"{path}[{i}]",
                    depth=depth + 1,
                    active_ids=active_ids,
                )
                snapshot_items.append(snap)
                encoded_items.append(enc)
            snapshot = snapshot_items if is_list else tuple(snapshot_items)
            return snapshot, {
                "type": "list" if is_list else "tuple",
                "items": encoded_items,
            }

        # Materialize a caller-owned Mapping exactly once.  From this point forward
        # supervision and canonical execution use the plain-data snapshot only.
        try:
            raw_items = list(value.items())
        except ObservationValidationError:
            raise
        except Exception as exc:
            raise ObservationValidationError(
                f"invalid execution observation {path}: mapping could not be materialized"
            ) from exc

        materialized = []
        for key, child in raw_items:
            if type(key) is not str:
                raise ObservationValidationError(
                    f"invalid execution observation {path}: mapping keys must be str"
                )
            _validate_unicode(key, path=f"{path}.<key>")
            snap, enc = _snapshot_and_encode(
                child,
                path=f"{path}.{key}",
                depth=depth + 1,
                active_ids=active_ids,
            )
            materialized.append((key, snap, enc))
        materialized.sort(key=lambda item: item[0])
        snapshot_mapping = {key: snap for key, snap, _ in materialized}
        encoded_mapping = [[key, enc] for key, _, enc in materialized]
        return snapshot_mapping, {"type": "mapping", "items": encoded_mapping}
    finally:
        active_ids.discard(oid)


def canonical_observation_value(value: Any, *, path: str) -> dict:
    """Validate one value and return its deterministic type-strict encoding."""
    _, encoded = _snapshot_and_encode(
        value,
        path=path,
        depth=0,
        active_ids=set(),
    )
    return encoded


def validate_event_id(event_id: Any) -> str:
    if type(event_id) is not str or not event_id:
        raise ObservationValidationError("execution observation event_id required")
    _validate_unicode(event_id, path="event_id")
    return event_id


def snapshot_execution_observation(observation: Any) -> tuple[ExecutionObservation, dict]:
    """Freeze one caller observation and return (snapshot, canonical identity payload).

    The caller-owned mappings/containers are read only during this function.  The
    returned ExecutionObservation contains only plain-data snapshots and is the object
    that must be used for digesting, intent identity, bridge validation and canonical
    advance.
    """
    if not isinstance(observation, ExecutionObservation):
        raise ObservationValidationError("execution observation required")

    event_id = validate_event_id(observation.event_id)
    flags: dict[str, bool] = {}
    for field_name in (
        "continuation_sufficient",
        "completion_sufficient",
        "completed",
        "staged",
        "failed",
        "emergency",
        "material_policy_class_change_required",
    ):
        value = getattr(observation, field_name)
        if type(value) is not bool:
            raise ObservationValidationError(
                f"execution observation {field_name} must be bool"
            )
        flags[field_name] = value

    realized = observation.realized_pv_bundle
    information = observation.information
    if not isinstance(realized, Mapping):
        raise ObservationValidationError(
            "execution observation realized_pv_bundle must be a mapping"
        )
    if not isinstance(information, Mapping):
        raise ObservationValidationError(
            "execution observation information must be a mapping"
        )

    frozen_realized, encoded_realized = _snapshot_and_encode(
        realized,
        path="realized_pv_bundle",
        depth=0,
        active_ids=set(),
    )
    frozen_information, encoded_information = _snapshot_and_encode(
        information,
        path="information",
        depth=0,
        active_ids=set(),
    )

    snapshot = ExecutionObservation(
        event_id=event_id,
        realized_pv_bundle=frozen_realized,
        information=frozen_information,
        **flags,
    )
    payload = {
        "event_id": event_id,
        **flags,
        "realized_pv_bundle": encoded_realized,
        "information": encoded_information,
    }
    return snapshot, payload


def canonical_execution_observation_payload(observation: Any) -> dict:
    """Return the exact canonical identity payload for one ExecutionObservation."""
    _, payload = snapshot_execution_observation(observation)
    return payload
