# PV-PP Runtime V2 --- v0.131 Release Notes

## Release Status

**Runtime generation:** Runtime V2\
**Build:** v0.131\
**Status:** Freeze candidate / public beta\
**Regression suite:** 967 passed

Runtime V2 v0.131 is the current successor to Runtime V1 build v0.70,
which remains preserved as **Runtime Interface Freeze 1**.

v0.131 completes the planned post-v0.70 successor-runtime functional
program within the declared synchronous scope and incorporates the
authority-bound call-through repairs identified during independent
hostile testing.

## Release Lineage

Runtime V2 was developed incrementally from the complete mature v0.70
runtime rather than as a replacement implementation built from scratch.

Major checkpoints in the final development sequence were:

-   **v0.129** --- completed the planned post-v0.70 functional additions
    and became the first functional-closeout candidate.
-   **v0.130** --- introduced authority-bound native call-through,
    closing the public `ExecutionContext` / registry invocation bypass.
-   **v0.131** --- repaired the upstream canonical-lineage provenance
    defect found by independent hostile testing of v0.130.

Runtime V1/v0.70 remains unchanged in the repository for historical
compatibility, reproducibility, and comparison.

## Major Runtime V2 Additions

Relative to Runtime V1/v0.70, Runtime V2 adds or substantially extends
the following runtime capabilities.

### Version 2 State and Adapter Foundations

Runtime V2 preserves broader actual and perceived state separately from
Productive Power and supports typed distinctions including access,
possession, permission, control, operability, configuration-dependent
productive capability, recovery resources, and productive-role
qualification.

Portable adapter and configuration-provenance interfaces preserve the
boundary between application/world semantics and runtime-owned
governance.

### Canonical Governance Re-entry

Runtime V2 supports earliest-invalidated-stage governance re-entry
across the canonical decision architecture.

Depending on the invalidated authority, bounded re-entry can begin at
fresh perception/PPP processing, Φ, H, G, R, Graph/seed, Π, Π
completeness, Joint Recovery, Constraints, Domain Framing, Adequacy, or
Σ and then follow the normal downstream lineage.

Reusable artifacts and deterministic substrate identities prevent stale
structure or configuration from being silently reused.

### Dynamic Graph and Structural Governance

Runtime V2 adds provenance-bearing represented-Graph reachability
refresh, structural-coverage qualification, controlled Graph
transformation admission/revision/removal, controlled novel
action/function admission, and recovery-necessity topology lifecycle
support.

These mechanisms provide governed structural extension without
introducing autonomous semantic discovery or unrestricted runtime
self-modification.

### Evidence, Epistemic Authority, and Control Topology

Runtime V2 adds provenance-bearing observations, evidence-source
authority/control state, explicit fact/source and artifact dependencies,
epistemic invalidation, and controlled governance re-entry.

Dynamic control/provenance topology can represent relationships such as
creation, control, delegation, revocation, termination, and descent
while preserving explicit dependency and provenance boundaries.

### Capability Evolution

Runtime V2 adds typed capability-change observations, cumulative
non-scalar capability trajectories, capability-driven represented-Graph
reachability, controlled capability-supported Graph constructibility,
and capability-formation prediction-error handling.

Capability remains non-scalar and evidence-bound; the runtime does not
infer new action semantics merely from observed capability change.

### Architecture-Invariance Instrumentation

Runtime V2 includes cross-configuration
architecture-invariance/adaptation assessment intended to distinguish
legitimate application/adapter specialization from hidden replacement of
runtime-owned governance semantics.

## Authority-Bound Native Call-Through

The final v0.131 call-through design makes native invocation authority
depend on runtime-private provenance across the canonical:

`decision cycle → Σ → execution license → active ε episode → native execution authorization → invocation`

lineage.

Registration of a callable or possession of public runtime dataclasses
does not confer execution authority.

### v0.130 Repair

v0.130 removed the prior public native-call bypass by making
`ExecutionBindingRegistry.invoke(context, ...)` fail closed and
requiring a runtime-issued, ledger-backed
`NativeExecutionAuthorization`.

Native authorizations are single use and are consumed immediately before
callable entry. Replay, binding/version mismatch, configuration
mismatch, pause, abort, reauthorization requirements, and explicit
lineage invalidation fail closed.

### v0.131 Canonical-Lineage Repair

Independent hostile testing of v0.130 found that a host could construct
a plausible `ExecutionLicenseEnvelope` and active `ExecutionEpisode` and
use those public objects to obtain a genuine native authorization
without traversing the canonical decision/Sigma lineage.

v0.131 closes that defect.

The runtime now maintains private provenance for canonical execution
licenses and execution episodes:

-   `build_execution_license_from_cycle()` registers the exact
    runtime-issued canonical license;
-   `instantiate_execution()` accepts only a current runtime-recognized
    canonical license and registers the resulting execution episode;
-   `issue_native_execution_authorization()` accepts only the current
    runtime-issued episode backed by that canonical license lineage; and
-   reconstructed or merely equal license/episode dataclasses are
    non-authorizing.

The v0.130 single-use authorization ledger, consume-before-call
behavior, control gates, binding/configuration validation, failure
normalization, and conservative Layer-1 return behavior remain intact.

This mechanism protects the **PV-PP runtime interface authority
boundary**. It is not a Python sandbox or cryptographic security
mechanism. Host code that directly owns a callable can still invoke its
own callable outside PV-PP; such an invocation is not representable as
PV-PP-authorized execution.

## Validation

The final v0.131 runtime regression suite reports:

``` text
967 passed
```

The validation set includes the inherited Runtime V2 suite, the v0.130
authority-bound call-through tests, and additional v0.131
canonical-lineage hostile tests.

The hostile lineage tests verify rejection of:

-   directly fabricated executable licenses;
-   fabricated active execution episodes;
-   reconstructed copies of genuine canonical artifacts;
-   stale authority after lineage invalidation; and
-   native execution attempts that do not derive from a legitimate
    canonical lineage.

The legitimate canonical decision → license → ε episode → native
authorization → invocation path remains executable.

## Release-Package Cleanup

The cleaned v0.131 distribution contains the same runtime source and
regression suite as the banked v0.131 development package.

Packaging cleanup removed historical per-build `BUILD_Vxxx_NOTICE.md`
files, Finder metadata, Python cache artifacts, and test-cache
artifacts. Historical development information remains in the project
change/test reports and runtime change register rather than being
duplicated as dozens of build-marker files in the release directory.

`BASELINE_NOTICE.md` and the v0.70 reference hashes are retained where
useful for lineage and integrity reference.

## Compatibility

Runtime V2 is a controlled successor to Runtime V1 rather than an
in-place modification of the frozen V1 runtime.

Applications that depend on Runtime V1/v0.70 should continue to use the
`runtime-v1` directory unless deliberately migrated.

New applications should normally target Runtime V2 and its documented
canonical integration path.

Interfaces retained for historical or regression compatibility should
not automatically be treated as recommended interfaces for new Runtime
V2 applications.

## Deliberate Scope Boundaries

Runtime V2 v0.131 does not add or claim:

-   asynchronous/concurrent/distributed execution;
-   guaranteed mid-flight cancellation;
-   reachability-at-scale optimization;
-   autonomous semantic discovery;
-   automatic invention of PP domains;
-   unrestricted runtime self-modification;
-   a universal persistent runtime database;
-   replacement of operating-system, IAM, network, sandbox, credential,
    or other conventional enforcement mechanisms; or
-   new framework, Σ, Adequacy, re-entry-stage, or Layer-1 semantics.

These omissions are deliberate scope boundaries rather than unresolved
v0.131 defects.

## Freeze-Candidate Position

v0.131 is the current Runtime V2 freeze candidate.

The planned post-v0.70 functional-addition program is closed. Further
runtime code changes should be driven by reproducible defects, failed
integration/adversarial tests, or separately governed future
requirements rather than by opportunistic redesign.

Independent hardening, integration, adversarial, cross-domain, and
performance testing remain appropriate before final freeze designation.
