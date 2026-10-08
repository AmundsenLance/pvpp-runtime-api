# PV-PP Runtime 2.2 — build v0.159

## Scope

**Phase 18 — Round-four independent hostile-review hardening**

Preserves all v0.158 fixes and closes the false-terminal-fence defect plus the direct-runtime retry-status blind spot.

## Corrections

- continuation failures are classified from observed canonical movement rather than exception occurrence alone;
- a pre-advance failure or harmless snapshot conflict leaves the intent `abandoned`, not `reconciliation_required`;
- reconciliation closes an unchanged-step intent regardless of whether the prior status was prepared, abandoned, or reconciliation-required;
- true post-advance persistence divergence remains reconciliation-required and terminally fences when durable evidence cannot explain the advanced step;
- retry-contract registration now also consults the canonical runtime's native-authorization lifecycle through the live bridge, so a consumed authorization blocks post-hoc retry even when invocation bypassed supervisory markers.

## Boundary claims

Canonical-step freshness is bound to the bridge-resolved canonical episode within the governed Runtime 2.2 path. Direct mutation of the underlying canonical runtime bypasses bridge-cache refresh and is outside that step-freshness guarantee.

A true `terminally_fenced` active execution has no revival operation inside Runtime 2.2. The host must quarantine/terminate external work as appropriate, reconcile actual effect/world state through the existing recovery/effect surfaces, and begin a new governed execution/attempt if further action is authorized.

## Mandatory concurrency regression

A two-connection threaded test commits a continuation intent, admits a material fact change through a second SQLite connection before the second snapshot check, proves `snapshot_conflict` with no canonical movement, and then proves a fresh checkpoint can proceed without terminal fencing.

## Regression

**1268/1268 passing** before packaging. Final packaged-artifact regression is recorded in the external build/test record.

## Framework / baseline boundary

PV-PP Framework Version 2.1 remains the semantic authority. Frozen Runtime V2.1 v0.141 is preserved as the canonical predecessor. No frozen canonical runtime module is intentionally modified.
