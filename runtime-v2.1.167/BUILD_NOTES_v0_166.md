# PV-PP Runtime 2.2 v0.166 Build Notes

## Status
Bankable round-eleven hostile-review hardening build. Independent retest required before candidate-freeze audit.

## Round-eleven corrections
- Removed arbitrary-object `repr()` fallback from execution-observation identity.
- Supervised observation values are recursively limited to deterministic plain data: `None`, exact `bool`, exact `int`, exact `float`, valid-Unicode `str`, `list`, `tuple`, and `Mapping` with valid-Unicode string keys.
- The same validation executes in `ContinuationService` before intent creation and in `CanonicalRuntimeBridge.validate_advance_preconditions` before canonical call entry.
- Finite floats use exact hexadecimal identity; NaN, +inf, and -inf are encoded explicitly.
- Lone-surrogate event IDs/strings are rejected with typed `ObservationValidationError`.
- Numeric identity is intentionally type-strict: integer `1` and float `1.0` are different observation content.

## Timestamp boundary
Timezone-naive ISO-8601 checkpoint timestamps are accepted and interpreted as UTC. Explicit offsets/Z are also accepted. Timestamp representation is provenance and does not weaken the trusted-clock lease boundary.

## Validation
- Full repository: 1315/1315 passing.
- Successor Phase 1-25: 222/222 passing.
- Round-eleven hardening file: 6/6 collected cases passing.
- Full repository passes with all Python warnings promoted to errors.
- Frozen v0.141 canonical files remain unchanged except `pyproject.toml` successor package metadata/version.
