# PV-PP Runtime 2.2 — build v0.157

## Scope

**Phase 16 — Round-two independent hostile-review hardening**

Preserves all v0.156 fixes and closes the second review findings: trusted-clock lease enforcement, pre-invocation/pre-dispatch retry-contract cutoff, host-configured registration roots and evidence verifiers, durable continuation-intent divergence detection, strict target suffixes, and versioned vendor-command bindings. The `continue` posture remains non-authorizing for control.

## Trust boundary

Runtime 2.2 records and enforces trust decisions supplied by the host-configured `HostTrustProvider`. It does not claim to provide external IAM or cryptographic authentication by itself. Caller labels and booleans are not sufficient to create registered/verified authority.

## Atomicity boundary

The in-memory canonical runtime and supervisory SQLite store are not one atomic transaction. v0.157 persists a continuation intent before canonical advancement and fences reconciliation when canonical state advances without a committed supervisory assessment. This is detection/containment, not rollback of canonical state.

## Regression

**1253/1253 passing** before packaging. Final packaged-artifact regression is recorded in the external build/test record.

## Framework / baseline boundary

PV-PP Framework Version 2.1 remains the semantic authority. Frozen Runtime V2.1 v0.141 is preserved as the canonical predecessor. No v0.141 manifest file is intentionally modified except successor package metadata in `pyproject.toml`.
