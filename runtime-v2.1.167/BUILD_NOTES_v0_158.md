# PV-PP Runtime 2.2 — build v0.158

## Scope

**Phase 17 — Round-three independent hostile-review hardening**

Preserves all v0.157 fixes and closes the third review findings in the newest supervision/bridge surfaces.

## Corrections

- registered active executions cannot invoke through the alternate unsupervised bridge path;
- supervised canonical advancement requires a prepared continuation intent;
- continuation assessments record exact canonical step and stale assessments cannot issue or dispatch control;
- dispatch honors continuation-divergence fences even for pre-existing control requests;
- explicit root-authorized continuation divergence reconciliation either closes a consistent prepared intent or terminally fences an unreconstructable divergence;
- target syntax is validated before control-request persistence;
- caller timestamps are retained as provenance while trusted-clock timestamps are recorded separately on consequential request/dispatch records.

## Boundary claims

The in-memory canonical runtime and supervisory SQLite store are not one transaction. v0.158 provides durable intent, detection, dispatch fencing and an explicit reconciliation outcome; it does not provide rollback of canonical state.

Any code with direct mutation access to the in-process store object is part of the trusted computing base and can replace `store.trust`. Runtime 2.2 protects API-boundary callers; it is not an isolation sandbox against arbitrary in-process Python mutation.

## Regression

**1261/1261 passing** before packaging. Final packaged-artifact regression is recorded in the external build/test record.

## Framework / baseline boundary

PV-PP Framework Version 2.1 remains the semantic authority. Frozen Runtime V2.1 v0.141 is preserved as the canonical predecessor. No frozen canonical runtime module is intentionally modified.
