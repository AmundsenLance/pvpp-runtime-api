# PV-PP Runtime 2.2 v0.162 — Round-Seven Hardening Build Notes

## Scope
Built prospectively from exact v0.161. Frozen Framework V2.1 and Runtime V2.1 v0.141 canonical modules remain unchanged.

## F1 — Complete pre-mutation observation validation
Runtime 2.2 now validates every operation known to occur in frozen v0.141 `advance_execution` before the lineage write: active episode, exact `ExecutionObservation` input, non-empty string `event_id`, mapping/dict-convertible `realized_pv_bundle` and `information`, and actual-boolean execution flags. Validation runs before durable continuation-intent creation and again inside `CanonicalRuntimeBridge.advance_execution` before call-entry uncertainty is recorded. Input failures create no indeterminate canonical state and a subsequent valid checkpoint may proceed. The existing mutate-then-raise fault remains canonical-state-indeterminate and fail-closed.

## F2 — Cross-connection continuation-intent serialization
Continuation pending-intent inspection now runs inside a `BEGIN IMMEDIATE` boundary. A second supervisor never relabels a live `prepared` intent; it receives a retryable concurrency conflict. Intent creation refuses a concurrent open intent. Failed-intent classification and successful close are compare-and-swap transitions from `prepared`, preventing a delayed connection from overwriting a later `closed` result.

A deterministic two-service regression recreates the former lost-update schedule. A repeated 20-round stress test runs two supervisor connections with 15 successful checkpoints each per round and requires unique canonical steps plus zero `reconciliation_required`/`terminally_fenced` residue.

## Recovery boundary
A stale/crashed `prepared` intent is no longer auto-abandoned by another live checkpoint. It remains explicit state that must be handled through authorized continuation reconciliation. This is conservative by design: Runtime 2.2 cannot infer that a prepared intent is abandoned merely because another live process observes the expected canonical step.

## Validation
- New v0.162 hardening gate: 6/6.
- Prior race/crash/hardening compatibility slice: 96/96.
- Successor Phase 1–21 slice: 195/195.
- Full repository before packaging: 1288/1288.
- No freeze declaration; independent hostile retest remains required.
