# PV-PP Runtime 2.2 v0.165 Build Notes

## Status
Bankable round-ten hostile-review hardening build. Independent retest required before candidate freeze.

## Round-ten corrections
- Execution-observation idempotency binds `(active_execution_id, event_id)` to a deterministic SHA-256 digest of the complete `ExecutionObservation`. Identical content replays to the existing assessment; changed content under the same ID is an identity conflict.
- The committed-observation lookup is repeated under the same `BEGIN IMMEDIATE` transaction used for continuation-intent creation. Intent rows carry event ID and digest, so a concurrent duplicate is rejected/resolved before canonical advancement.
- Current continuation fence/reconciliation state is evaluated before returning any historical replay assessment.
- Reconciliation converts SQLite busy/locked acquisition failures to typed `ConcurrencyConflict`; raw `sqlite3.OperationalError` is not part of the supervisory API contract.
- The round-eight stress gate records unexpected thread exceptions as failures and proves reconciliation overlaps active checkpoint workers.
- Supervisory-store finalization defensively closes its SQLite connection as a resource-safety backstop; explicit close/context-manager use remains preferred.

## Observation digest boundary
The digest includes every `ExecutionObservation` field. Mapping order is normalized deterministically. Common scalar/container values are encoded structurally; fallback values include qualified type plus `repr`. The digest is an idempotency/identity guard, not a cryptographic attestation of world truth.

## Timestamp boundary
Timezone-naive ISO-8601 checkpoint timestamps are accepted and interpreted as UTC. Explicit offset/Z timestamps are validated as real instants and their supplied string representation is retained as provenance.

## Validation
- Full repository: 1309/1309 passing.
- Successor Phase 1-24: 216/216 passing.
- Round-ten hardening file: 10/10 collected cases passing.
- Full repository passes with all Python warnings promoted to errors.
- Frozen v0.141 canonical files remain unchanged except `pyproject.toml` successor package metadata/version.
