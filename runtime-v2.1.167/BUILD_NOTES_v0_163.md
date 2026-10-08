# PV-PP Runtime 2.2 v0.163 — Round-Eight Hardening Build Notes

## Scope
Built prospectively from exact v0.162. Frozen Framework V2.1 and Runtime V2.1 v0.141 canonical modules remain unchanged.

## G1 — Transactional administrator reconciliation
`reconcile_continuation_divergence` now acquires one `BEGIN IMMEDIATE` write transaction before reading the target intent, latest assessment, supersession state, and bridge-resolved canonical step. A reconciliation call racing a checkpoint therefore waits for the checkpoint transaction and re-reads the durable post-commit state rather than acting on an obsolete `prepared` row.

Every intent status write made by reconciliation is compare-and-swap against the status actually read. The reconciliation record and append-only audit event are written in the same SQLite transaction as the status transition. A changed row is never unconditionally overwritten.

## G2 — State-specific retry/reconciliation guidance
`reconciliation_required` and `terminally_fenced` take precedence over historical assessment/retry hints. A prepared intent created by the same `ContinuationService` but no longer tracked as in flight reports authorized reconciliation required. A different connection receives a retryable conflict stating that authorized reconciliation is required if no checkpoint is actually in flight.

The creating service tracks owned and currently in-flight continuation intent IDs only in memory; this is liveness guidance, not authority.

## Validation
- New v0.163 hardening gate: 5/5.
- Affected continuation/control/race/crash/hardening compatibility slice: 99/99.
- Successor Phase 1–22 slice: 200/200.
- Full repository before release metadata: 1293/1293.
- No freeze declaration; independent hostile retest remains required.
