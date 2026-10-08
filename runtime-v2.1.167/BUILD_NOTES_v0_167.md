# PV-PP Runtime 2.2 v0.167 Build Notes

## Status
Bankable round-twelve hostile-review hardening build. Proposed controlling implementation for a fresh candidate-freeze audit only if independent retest is clean.

## Round-twelve corrections
- Freeze each caller-supplied `ExecutionObservation` exactly once into a supervised plain-data snapshot before intent creation.
- The same frozen snapshot now drives the observation digest, durable intent payload, bridge pre-call validation, and canonical `advance_execution` call. The caller-owned live object is not read again after snapshot creation.
- Materialize caller-owned `Mapping` values once into sorted plain `dict` snapshots; preserve list versus tuple identity recursively.
- Add cycle detection and a maximum supervised observation nesting depth of 64.
- Bound supervised observation integers to 4096 bits and encode supported integer identity in hexadecimal, avoiding Python decimal-string digit limits.
- Deep, cyclic, over-limit integer, invalid-Unicode, unsupported-object, and non-string-key values fail as typed `ObservationValidationError` before intent creation/canonical call entry.

## Identity / timestamp boundaries
- Observation identity remains type-strict: integer `1` and float `1.0` are distinct content.
- NaN, +inf, and -inf use explicit canonical encodings.
- Timezone-naive ISO-8601 checkpoint timestamps are accepted and interpreted as UTC.

## Validation
- Full repository: 1320/1320 passing with all Python warnings promoted to errors.
- Successor Phase 1-26: 227/227 passing with all Python warnings promoted to errors.
- Round-twelve hardening gate: 5/5 passing.
- Frozen v0.141 canonical files remain unchanged except `pyproject.toml` successor package metadata/version.
