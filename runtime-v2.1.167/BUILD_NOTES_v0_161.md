# PV-PP Runtime 2.2 v0.161 — Build Notes

## Status

Round-six hostile-review hardening build. **Not frozen.** Independent retest is required before candidate-freeze work resumes.

## Predecessor

Built from the exact v0.160 package. Frozen Runtime V2.1 v0.141 canonical modules remain unchanged; only `pyproject.toml` differs within the v0.141 manifest set for successor package metadata/version.

## Corrections

1. **Divergence supersession:** caller timestamps are removed from continuation supersession. Only `abandoned` or stale `prepared` intents may be superseded, based on durable cross-table intent/assessment insertion order. `reconciliation_required` and `terminally_fenced` are never superseded.
2. **Pre-mutation refusal:** `ContinuationService` validates v0.141 no-mutation preconditions before intent creation, and `CanonicalRuntimeBridge.advance_execution` repeats them before recording canonical call entry. Invalid/empty observations therefore do not create indeterminate state.
3. **Live bridge binding:** public rebinding is refused. Trusted registration uses a private binding operation that requires an actual `CanonicalRuntimeBridge`, matching canonical handle/episode/authorization lineage, and refuses a different replacement bridge.
4. **Not-required reconciliation evidence:** abandoned/superseded closure creates a `continuation_reconciliations` row and `continuation_divergence_reconciled` audit event with an explicit not-required outcome.

## Boundary Claims

- Live canonical bridge bindings are intentionally in-memory and non-durable.
- A reopened store has **no public rebind path for an existing active execution**. Operations requiring live canonical status remain fail-closed. A new governed execution/attempt must be registered through the normal bridge path.
- Code with arbitrary private mutation access inside the process remains part of the trusted computing base.
- Canonical exceptions raised after call entry still produce canonical-state-indeterminate fail-closed handling; only prevalidated no-mutation refusal is excluded.

## Validation

- New round-six hardening gate: 9/9 passing.
- Affected bridge/continuation/retry/crash compatibility slice: 73/73 passing.
- Complete successor Phase 1–20 slice: 189/189 passing.
- Full regression before release metadata: 1282/1282 passing.

Final packaged-artifact results and SHA-256 values are recorded in the v0.161 build/test record.
