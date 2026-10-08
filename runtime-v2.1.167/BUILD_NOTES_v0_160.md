# PV-PP Runtime 2.2 — build v0.160

## Scope

**Phase 19 — Round-five independent hostile-review hardening**

Preserves all v0.159 fixes and closes the late-abandoned-intent reconciliation defect, the entered-then-raised canonical-advance fault path, and retry fail-open caused by missing/overwritten live canonical bridge bindings.

## Corrections

- `abandoned` intents are non-fencing historical outcomes; reconciliation closes/ignores them as not required regardless of later canonical step;
- an abandoned intent superseded by later closed continuation work or later durable assessment is not eligible for divergence reconciliation;
- the bridge records canonical advance-call entry before invoking the runtime and marks the episode canonical-state-indeterminate if that call raises;
- indeterminate episodes refuse further bridge advancement, authorization issuance, and supervised native invocation; failed-intent classification becomes reconciliation-required and reconciliation fails closed;
- live canonical bridges are bound per active execution rather than in one store-wide slot;
- retry-contract registration requires live canonical authorization status exactly `issued`; missing/unknown status or bridge error fails closed.

## Regression gates

New phase-19 regressions cover:

1. late reconciliation after transient abandonment followed by a successful checkpoint;
2. late reconciliation after the real two-connection threaded snapshot-conflict path followed by successful progress;
3. runtime advance mutates and then raises, producing canonical-state-indeterminate and terminal fencing;
4. reopened-store retry registration with no live bridge binding;
5. two live runtimes sharing one store without bridge-binding overwrite.

## Boundary claims

Per-active-execution bridge bindings are deliberately in-memory. Durable supervisor history is not live canonical authority after restart. Missing live canonical status fails closed for retry registration.

A bridge-marked indeterminate episode means the canonical advance call was entered and the bridge cannot prove whether or how far the underlying runtime mutated before raising. Runtime 2.2 does not classify such an attempt as abandoned from cache equality alone.

## Regression

**1273/1273 passing** before packaging. Final packaged-artifact regression is recorded in the external build/test record.

## Framework / baseline boundary

PV-PP Framework Version 2.1 remains semantic authority. Frozen Runtime V2.1 v0.141 remains the canonical predecessor. No frozen canonical runtime module is intentionally modified.
