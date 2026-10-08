# PV-PP Runtime V2.1 — Release Notes

## Frozen Release Status

**Runtime generation:** Runtime V2.1  
**Frozen build:** v0.141  
**Status:** Frozen Framework Version 2.1 successor baseline  
**Full regression:** **1093/1093 passing**  
**Small Economy V2.1 benchmark:** eight-case controlled program PASS  
**Preserved predecessor:** Runtime V2 / v0.131

Runtime V2.1 was developed incrementally from the preserved v0.131 Runtime V2 baseline. The v0.131 line remains unchanged. The Version 2.1 work is a conservative successor program: it adds the applicable V2.1 interfaces and governance requirements while preserving validated prior runtime behavior unless Version 2.1 required a change.

Future runtime development should branch from frozen v0.141 rather than modify the frozen baseline in place.

## Release Lineage

```text
Runtime V1 / v0.70
    ↓
Runtime V2 / v0.131  (preserved prior successor)
    ↓
v0.132  V2.1 successor bootstrap
v0.133  Objective Interface
v0.134  Objective Responsiveness / bounded relevance
v0.135  Information Governance
v0.136  Transfer History
v0.137  Replay Sufficiency
v0.138  Transition-Relevant State Sufficiency
v0.139  Objective lifecycle dependency / bounded re-entry
v0.140  Small Economy V2.1 benchmark
v0.141  Hardening and freeze
```

## v0.132 — Successor Bootstrap and Regression Baseline

v0.132 is intentionally a non-semantic bootstrap build derived from preserved Runtime V2 v0.131.

Changes:

- normalized the Python package directory to `pvpp_runtime`, matching the public import surface;
- updated package metadata to build 0.132;
- preserved v0.131 runtime semantics and inherited tests;
- established the mandatory pre-V2.1 regression gate.

Regression: **967 passed**.

No Framework V2.1 semantic feature is claimed by v0.132. It does not yet implement `O_i(t)`, Objective Responsiveness, V2.1 information-governance qualifiers, Transfer History, Replay Sufficiency, or Transition-Relevant State Sufficiency.

## v0.133 — V2.1 Objective Interface Foundation

Added:

- typed `ObjectiveSet` / qualified objective-record surface;
- temporal bounds and declared objective relations;
- validation of actor/time identity, objective identity, lifecycle status, temporal applicability, authority/provenance, and version identity;
- objective set adjacent to perceived decision state in the canonical snapshot;
- optional objectives input to integrated canonical-cycle preparation/evaluation;
- `ObjectiveInterfaceAdapter` for host/application-owned objective supply;
- objective-free viability operation.

Objectives do not become a canonical operator or acquire Graph admission, Π, Constraints, Adequacy, Σ, ε, or execution authority.

Regression: **980 passed**.

## v0.134 — Objective Responsiveness and Bounded Objective Relevance

Added:

- typed `Resp(pi,o)` records with `supports`, `neutral`, `conflicts`, and `unresolved`;
- application-owned responsiveness adapter;
- bounded objective-discovery hints restricted to registered Graph identifiers and application retrieval cues;
- hostile tests proving objective relevance does not alter Graph admission/reachability, Π completeness, policy retention, or fabricate support for impossible objectives.

Objective Responsiveness is informational/descriptive. The runtime does not infer objective-policy relations or convert responsiveness into selection authority.

Regression: **995 passed**.

## v0.135 — Information Governance

Added:

- `InformationTemporalProvenance`;
- `InformationGovernanceMetadata`;
- `InformationGovernanceAssessment`;
- additive optional governance metadata on `MemoryRetrievalPackage`;
- runtime validation separating quality/confidence from authority, applicability, permitted use, and disposition.

The runtime preserves rejected, superseded, defective, prohibited-for-use, historically-valid-noncurrent, unresolved, and contradicted dispositions against semantic resurrection as ordinary current positive evidence.

Regression: **1011 passed**.

## v0.136 — Transfer History

Added:

- typed Transfer History event, reference, package, and validation objects;
- host-owned `TransferHistoryService` boundary;
- runtime validation and record handoff;
- reuse of the narrow V2.1 temporal-provenance model.

Transfer History remains distinct from memory, expectation, Productive Power, current state, replay, and authority.

Regression: **1028 passed**.

## v0.137 — Replay Sufficiency and Historical Decision Reconstruction

Added:

- typed decision replay-evidence package;
- replay-sufficiency assessment;
- replay-package construction and validation surfaces.

Replay packages can retain decision-time state/perceived state, objectives, admitted retrieval/governance evidence, expectation/Transfer History references, pipeline/gate results, execution/transition evidence, and provenance where supplied.

Replay evidence confers no live-state, operator, selection, or execution authority. Prospective current-state sufficiency remains distinct from historical replay sufficiency.

Regression: **1046 passed**.

## v0.138 — Transition-Relevant State Sufficiency

Added:

- host/application-owned transition-relevant state-basis declaration;
- state-sufficiency assessment;
- paired hostile-invariant assessment;
- `StateSufficiencyAdapter`;
- runtime declaration validation.

The application owns semantic completeness. The runtime validates the declaration and associated invariants rather than inferring all domain facts.

Transfer History, replay material, confidence, evidence quality, or PP alone cannot substitute for a missing material current-state consequence.

This build does not add a Context Graph, a new Layer-1 primitive, or a new canonical operator.

Regression: **1064 passed**.

## v0.139 — Objective Lifecycle Dependency and Bounded Re-entry

Added:

- explicit objective-lifecycle change/invalidation records;
- dependency-scoped objective invalidation;
- bounded re-entry through the existing stage order.

Objective-only change is not automatically a state/perception change and does not automatically invalidate the viability prefix or represented Graph. Only explicitly registered dependencies on the changed objective identity/objective-set version are invalidated.

Independent actual-state or perceived-state changes remain governed through their ordinary dependency/invalidation paths.

Regression: **1082 passed**.

## v0.140 — Small Economy V2.1 Integration Benchmark

Added `benchmarks/benchmark_small_economy_v2_1_v0140.py`.

The benchmark adds eight controlled `O_i(t)` perturbation cases:

1. attainable objective;
2. conflicting objectives;
3. objective-versus-viability conflict;
4. impossible objective;
5. capability development;
6. objective lifecycle change;
7. prohibited evidence; and
8. no-objective control.

The benchmark confirms that:

- objective perturbations do not rewrite Graph admission or the controlled candidate substrate;
- impossible objectives do not fabricate policies;
- desired future capability does not become current reachability;
- reachable training remains a current capability-development path;
- objective relevance does not override information governance; and
- objective lifecycle re-entry begins at the explicit registered dependency and preserves the viability prefix.

No canonical operator or execution semantics changed in v0.140.

Regression: **1093 passed**.

## v0.141 — Hardening and Freeze

v0.141 introduces **no new canonical runtime semantics** relative to v0.140.

Hardening included:

- fresh full regression;
- Small Economy V2.1 benchmark rerun;
- API/package review;
- source/test/benchmark provenance and hash review;
- framework/runtime-boundary review;
- objective-authority-leakage review.

Results:

- **1093/1093 tests passed**;
- Small Economy V2.1 eight-case benchmark: **PASS**;
- no undeferred functional blocker identified.

Following owner freeze decision, **Runtime V2.1 v0.141 is the frozen successor baseline**.

## Major Version 2.1 Additions

Relative to preserved Runtime V2/v0.131, the V2.1 release line adds:

- typed adjacent actor objective interface `O_i(t)`;
- Objective Responsiveness;
- bounded objective-directed discovery;
- information governance separating evidentiary quality from authority/applicability/permitted use/disposition;
- temporal provenance;
- Transfer History;
- Replay Sufficiency;
- Transition-Relevant State Sufficiency;
- objective lifecycle dependency and bounded re-entry; and
- Version 2.1 Small Economy objective-perturbation validation.

The release preserves the established Graph/Π/completeness, Constraints, framing, Adequacy, Σ, execution licensing, ε, native call-through, capability-evolution, and Layer-1 boundaries except where additive Version 2.1 integration was required.

## Objective and Capability Boundary

Version 2.1 makes objectives explicit without making them sovereign.

An objective does not become:

- hidden utility;
- policy selection;
- authority;
- adequacy override;
- viability;
- Graph reachability; or
- current Productive Power.

Capability-development intent must proceed through a realized and evidenced capability/state transition before new capability can become current PP or support represented reachability.

## Preserved Native Call-Through Boundary

Runtime V2.1 preserves the v0.131 authority-bound synchronous native-call design.

Consequential invocation through the PV-PP runtime interface requires runtime-issued authority derived from the canonical execution lineage. Registration alone grants no execution authority. Runtime authorizations remain single-use and provenance-bound.

This is a runtime-interface authority invariant, not a Python sandbox or replacement for operating-system, IAM, network, credential, or other conventional enforcement.

## Deliberate Scope Boundaries

Frozen Runtime V2.1 v0.141 does not add or claim:

- asynchronous sensing;
- external instrumentation hooks;
- autonomous in-flight environment-change detection;
- asynchronous/concurrent/distributed execution;
- guaranteed mid-flight cancellation;
- reachability-at-scale optimization;
- autonomous semantic discovery;
- automatic invention of PP domains;
- unrestricted runtime self-modification;
- a universal persistent runtime database; or
- replacement of conventional security/enforcement mechanisms.

These are scope boundaries, not capabilities that should be inferred from Framework Version 2.1.

## Validation and Integrity Records

The release directory includes:

- `BASELINE_CODE_IDENTITY_CHECK.txt`
- `BASELINE_NOTICE.md`
- `BENCHMARK_SMALL_ECONOMY_v0_140.txt`
- `HARDENING_SMALL_ECONOMY_v0_141.txt`
- `V0141_FILE_HASHES.sha256`

These records preserve the baseline, benchmark/hardening evidence, and frozen-tree integrity information.

## Compatibility

Runtime V2.1 is a controlled successor to Runtime V2/v0.131, not an in-place modification.

Applications requiring historical Runtime V2 behavior should continue to use `runtime-v2/`. Applications requiring the original v0.70 interface should continue to use `runtime-v1/`.

New Framework Version 2.1 applications should normally target `runtime-v2.1/`.

## Freeze Rule

Runtime V2.1 v0.141 is frozen.

Publication or repository packaging should not silently alter frozen source behavior. Future runtime development should begin as a new successor branch/build line from the frozen v0.141 baseline.
