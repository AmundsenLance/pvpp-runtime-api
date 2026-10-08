# PV-PP Runtime 2.2 v0.164 — Round-Nine Hardening Build Notes

## Scope
Built prospectively from exact v0.163. Frozen Framework V2.1 and Runtime V2.1 v0.141 canonical modules remain unchanged.

## H1 — Checkpoint audit atomicity and observation idempotency
`continuation_assessed` audit emission now occurs inside the same `BEGIN IMMEDIATE` transaction that persists the continuation assessment and closes the continuation intent. If audit emission fails before COMMIT, the SQLite transaction rolls back and the existing failed-intent classification path applies. If canonical state already moved, the intent becomes `reconciliation_required`; callers are not told that a durable checkpoint succeeded.

Runtime 2.2 also persists an execution-scoped observation-commit identity `(active_execution_id, event_id) -> assessment_id` in the same transaction. Repeating an already committed `ExecutionObservation.event_id` for the same active execution returns the existing assessment and does not advance canonical execution or create another intent.

## H2 — Consequential checkpoint timestamp validation
`checkpoint_at` / `assessed_at` must parse as ISO-8601 consequential timestamps before snapshot capture or intent creation. Invalid values such as `t`, impossible date/time forms, or empty strings are rejected with no continuation residue and no canonical advancement. Valid timezone-offset forms remain accepted.

## Validation
- New v0.164 hardening gate: 6/6.
- Affected hardening/race/crash compatibility slice: 98/98.
- Successor Phase 1–23 slice: 206/206.
- Full repository before release metadata: 1299/1299.
- No freeze declaration; independent hostile retest remains required.
