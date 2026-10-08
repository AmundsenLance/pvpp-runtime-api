# PV-PP Runtime API — Runtime 2.2

Runtime 2.2 is the operational-supervision successor line built from the frozen **Runtime V2.1 v0.141** canonical baseline for the **PV-PP Framework Version 2.1**. Framework Version 2.1 remains the semantic authority and is not modified by this runtime line.

## Current Status

- **Runtime generation:** Runtime 2.2
- **Current build:** v0.167
- **Status:** **FROZEN** — current Runtime 2.2 implementation
- **Full regression:** **1320/1320 passing**
- **Frozen canonical predecessor:** Runtime V2.1 v0.141, preserved and independently reproducible
- **v0.155 status:** rejected freeze candidate; retained as reproducible hardening baseline
- **v0.156 status:** successful first hostile-review hardening build; superseded after round-two findings
- **v0.157 status:** successful round-two hardening build; superseded by v0.158 after round-three findings
- **v0.158 status:** successful round-three hardening build; superseded for candidate purposes by v0.159 after round-four false-fence findings
- **v0.159 status:** successful round-four hardening build; superseded by v0.160 after round-five reconciliation/bridge-binding findings
- **v0.160 status:** successful round-five hardening build; superseded by v0.161 after round-six supersession/prevalidation/private-binding findings
- **v0.161 status:** successful round-six hardening build; superseded by v0.162 after round-seven pre-mutation-validation/concurrent-intent findings
- **v0.162 status:** successful round-seven hardening build; superseded by v0.163 after round-eight administrator-reconciliation/guidance findings
- **v0.163 status:** successful round-eight hardening build; superseded by v0.164 after round-nine checkpoint-audit/idempotency/timestamp findings
- **v0.165 status:** successful round-ten hardening build; superseded by v0.166 after residual observation-value identity findings
- **v0.166 status:** successful round-eleven hardening build; superseded by v0.167 after live-observation snapshot/pathological-value findings
- **Framework:** Version 2.1 unchanged

Runtime 2.2 adds an operational supervisory layer for live observation intake, active-execution/dependency correlation, continuation governance, ownership/fencing, external control/enforcement evidence, effect reconciliation, recovery, simulation, and audit. The canonical governance core remains synchronous/serializable; Runtime 2.2 does not claim universal physical preemption, exactly-once external effects, automatic dependency discovery, or ownership of actual world state.

### Requirement/Test Lineage Names

`R3-01` through `R3-24` are preserved identifiers from the **Runtime 3.0 design program** that specified the successor operational requirements. `R22` in test filenames denotes the **Runtime 2.2 implementation/hardening line**. These identifiers are retained for provenance and do not mean the packaged runtime is named Runtime 3.0.

The frozen v0.141 runtime is not modified in place. Runtime 2.2 is a separately versioned successor implementation.

## Directory Layout

```text
runtime-v2.1.167/
├── BASELINE_CODE_IDENTITY_CHECK.txt
├── BASELINE_AND_LINEAGE.md
├── BENCHMARK_SMALL_ECONOMY_v0_140.txt
├── HARDENING_SMALL_ECONOMY_v0_141.txt
├── benchmarks/
├── docs/
├── examples/
├── pvpp_runtime/
├── pyproject.toml
├── README.md
├── RELEASE_NOTES.md
├── tests/
└── V0141_FILE_HASHES.sha256
```

The source package is `pvpp_runtime/`. Runtime 2.2 is additive around the preserved v0.141 canonical core. The v0.141 hash manifest remains in the tree as predecessor provenance; `V0167_FILE_HASHES.sha256` is the current Runtime 2.2 source-tree manifest.









## Runtime 2.2 Round-Twelve Frozen Observation Snapshot Hardening (v0.167)

v0.167 closes the residual live-object observation identity gap found by the twelfth independent hostile review of v0.166. Runtime 2.2 now freezes each caller-supplied `ExecutionObservation` exactly once into a recursively validated plain-data snapshot before any continuation intent is created. That exact snapshot drives the identity digest, durable intent payload, bridge validation, and canonical `advance_execution` call; caller-owned mappings or containers are not read again after snapshot creation.

The supervised value domain remains plain data only. Mapping content is materialized once into sorted plain dictionaries, list/tuple type identity is preserved, strings require valid Unicode, floats keep exact/special-value encodings, nesting is limited to 64 levels with cycle detection, and integers above 4096 bits are rejected through typed `ObservationValidationError` rather than leaking Python digit-limit errors.

Identity remains intentionally type-strict (`1` and `1.0` differ). Timezone-naive ISO-8601 checkpoint timestamps are accepted and interpreted as UTC.

Validation: full repository **1320/1320** passing; successor Phase 1-26 **227/227** passing; round-twelve hardening gate **5/5**; all warning-gated runs pass with `-W error`. Following clean independent hostile retest and freeze closeout, v0.167 is the frozen controlling Runtime 2.2 implementation.

## Runtime 2.2 Round-Eleven Plain-Data Observation Identity Hardening (v0.166)

v0.166 closes the residual observation-identity gap found by the eleventh independent hostile review of v0.165. Supervised `ExecutionObservation` identity no longer falls back to `repr()` for arbitrary Python objects. `information` and `realized_pv_bundle` are restricted recursively to deterministic plain data: `None`, exact `bool`, exact `int`, exact `float` (including explicit NaN/+inf/-inf encodings), valid-Unicode `str`, `list`, `tuple`, and `Mapping` with valid-Unicode string keys. Unsupported objects are rejected with `ObservationValidationError` before intent creation and before canonical call entry.

The observation digest is type-strict and structural. `1` and `1.0` are intentionally different content. Mapping order is normalized, list/tuple identity is preserved, and arbitrary-object `repr()` is never part of execution-observation identity. Lone-surrogate strings are rejected as invalid supervised observation data rather than leaking a raw `UnicodeEncodeError`.

Timezone-naive ISO-8601 checkpoint timestamps remain accepted and are interpreted as UTC. This is an explicit provenance boundary.

Validation: full repository **1315/1315** passing; successor Phase 1-25 **222/222** passing; round-eleven hardening gate **6/6**; full repository passes with all Python warnings promoted to errors.

## Runtime 2.2 Round-Ten Observation Identity and Concurrent Idempotency Hardening (v0.165)

v0.165 closes four findings from the tenth independent hostile review of v0.164. Checkpoint idempotency is now an identity binding over `(active_execution_id, event_id, observation_digest)`, not an event-ID-only shortcut. The digest covers every `ExecutionObservation` field and deterministically normalizes mapping content. Identical replays return the existing assessment; reusing an event ID with changed emergency/failure/completion flags, realized-PV content, information content, or any other observation field raises `ObservationIdentityConflict` before intent creation or canonical advancement.

Concurrent duplicate detection is serialized with continuation-intent creation. The committed-event lookup is repeated inside the same `BEGIN IMMEDIATE` transaction that may create the new intent, and the intent records the event ID and digest. A second concurrent submission either resolves to the already committed identical assessment or receives a retryable pre-advance concurrency conflict; the unique commit constraint is no longer the first duplicate detector.

Current continuation fence state is checked before idempotent replay is returned. A historical `continue` assessment therefore cannot mask a current `reconciliation_required` or `terminally_fenced` execution. Administrator reconciliation now maps SQLite busy/locked failures to typed `ConcurrencyConflict` rather than leaking raw `sqlite3.OperationalError`. The round-eight reconciliation stress test treats any unexpected thread exception as failure and proves reconciliation attempts overlap active checkpoint workers. Supervisory stores also defensively close their SQLite connection if garbage-collected without an explicit `close()`, eliminating Python 3.13 resource warnings; explicit close/context-manager use remains preferred.

The complete repository passes with **all Python warnings promoted to errors**.

**Timestamp boundary:** timezone-naive ISO-8601 checkpoint timestamps are accepted and interpreted as UTC. Explicit offset/Z forms preserve their supplied provenance representation while being validated as real instants.

## Runtime 2.2 Round-Nine Checkpoint Atomicity and Idempotency Hardening (v0.164)

v0.164 closes two findings from the ninth independent hostile review of v0.163. First, checkpoint audit emission is now part of the same SQLite transaction as assessment persistence and intent close. An audit failure therefore rolls back the supervisory success record and enters the existing reconciliation-required path if canonical execution already moved; callers are never told a checkpoint failed after a durable supervisory success.

Checkpoint idempotency is also explicit. A committed `ExecutionObservation.event_id` is recorded per active execution in the same transaction as the assessment. Replaying that same event returns the existing assessment without creating a new intent or advancing canonical execution again.

Second, `checkpoint_at` / `assessed_at` use the same ISO-8601 consequential timestamp discipline as control operations. Invalid timestamps are rejected before snapshot capture and before any continuation intent exists; valid timezone-offset forms remain accepted.

## Runtime 2.2 Round-Eight Reconciliation Transaction and Guidance Hardening (v0.163)

v0.163 closes two findings from the eighth independent hostile review of v0.162. Administrator continuation reconciliation now performs its entire decision inside one `BEGIN IMMEDIATE` transaction, re-reading the intent, latest durable assessment and bridge step only after acquiring the write boundary. Every reconciliation status transition is compare-and-swap on the status actually read, and the reconciliation row plus audit event commit in the same transaction. A reconciliation call racing a healthy checkpoint therefore waits for the checkpoint commit, observes the now-closed durable state, and reports reconciliation not required rather than overwriting `closed` with `terminally_fenced`.

Continuation guidance is also state-specific. `reconciliation_required` and `terminally_fenced` always report authorized reconciliation/fence state before any historical-assessment retry hint. Each `ContinuationService` tracks the intent IDs it created and those currently in flight: a prepared intent created by the same service but no longer live reports authorized reconciliation required, while a different connection receives a retryable concurrency conflict that explicitly says reconciliation is required if no checkpoint is actually in flight.

A repeated administrator-reconciliation stress gate interleaves reconciliation with two supervisor connections and healthy checkpoints; no healthy execution may retain `reconciliation_required` or `terminally_fenced` residue.

## Runtime 2.2 Round-Seven Pre-Mutation Validation and Concurrent-Intent Hardening (v0.162)

v0.162 closes two findings from the seventh independent hostile review of v0.161. First, Runtime 2.2 now mirrors every frozen-v0.141 operation known to occur before the canonical lineage write: the episode must be active; the input must be an `ExecutionObservation`; `event_id` must be a non-empty string; `realized_pv_bundle` and `information` must be `Mapping` instances that materialize through `dict()`; and all seven execution flags must be actual `bool` values. These checks run in both `ContinuationService` before intent creation and `CanonicalRuntimeBridge.advance_execution` before call-entry uncertainty is recorded. Deterministic caller/input errors therefore do not create continuation residue or canonical-state-indeterminate fencing, while exceptions after actual canonical call entry remain fail-closed.

Second, continuation-intent inspection and status mutation are now serialized across SQLite connections. A live `prepared` intent is never relabeled by another supervisor; a competing service receives a retryable concurrency conflict. Failed-intent classification and normal close use compare-and-swap transitions from `prepared`, and intent preparation refuses an already-open continuation intent. The pending-intent check uses a `BEGIN IMMEDIATE` write boundary and never applies a decision based on an obsolete row. A deterministic two-service race and a repeated 20-round, two-connection stress test prove that successful commits remain `closed`, committed canonical steps are unique, and no `reconciliation_required` or `terminally_fenced` residue is left by healthy concurrency.

A stale or crashed `prepared` intent is no longer auto-reclassified by another live checkpoint. Recovery of that state remains explicit through the authorized continuation-reconciliation path. This avoids confusing an in-progress live checkpoint with a crashed one.


## Runtime 2.2 Round-Six Supersession, Prevalidation, and Private Live-Bridge Boundary (v0.161)

v0.161 closes four findings from the sixth independent hostile review of v0.160. A true continuation divergence can no longer be erased by caller-supplied timestamp ordering: supersession is based only on a durable cross-table insertion sequence for continuation intents and persisted assessments, and it applies only to non-divergent historical states (`abandoned` or stale `prepared`). `reconciliation_required` and `terminally_fenced` intents are never superseded.

Canonical pre-mutation checks that frozen v0.141 performs before changing execution state are now repeated before Runtime 2.2 creates a continuation intent and again inside `CanonicalRuntimeBridge.advance_execution` before the bridge records canonical-call entry. A terminal episode, a non-`ExecutionObservation`, or an empty `event_id` therefore fails without creating indeterminate canonical state. Exceptions raised after canonical call entry remain indeterminate/fail-closed.

Live canonical bridge binding is now private to trusted `CanonicalRuntimeBridge.register_active_execution`. The public `store.bind_canonical_bridge` surface refuses rebinding; the private binding verifies an actual `CanonicalRuntimeBridge`, matching active-execution lineage, and refuses replacement by a different bridge. Code with arbitrary private in-process mutation rights remains inside the trusted computing base.

Closing an abandoned or superseded continuation intent as “reconciliation not required” now still creates a `continuation_reconciliations` record and append-only `continuation_divergence_reconciled` audit event. Historical closure is therefore explicit rather than silent.

**Restart boundary:** live canonical bridge bindings are deliberately non-durable and v0.161 exposes no public rebind operation for an existing active execution. After a supervisory-store reopen, retry-contract registration remains fail-closed for that historical active execution. To regain operations requiring live canonical status, the host must create/register a **new governed execution/attempt** through the normal canonical bridge path; durable history alone cannot recreate live authority.


## Runtime 2.2 Round-Five Reconciliation and Live-Bridge Boundary (v0.160)

v0.160 closes three defects found by the fifth independent hostile review of v0.159. First, an `abandoned` continuation intent is now permanently non-fencing: reconciling it closes/ignores it as not required, even after a later successful checkpoint. Historical abandoned intents and intents superseded by later closed work cannot become terminal-fence inputs.

Second, `CanonicalRuntimeBridge` records that the canonical advance call was entered before invoking `runtime.advance_execution`. If that call raises, the bridge marks the episode **canonical-state-indeterminate** because the runtime may have mutated before raising. An indeterminate supervised episode refuses further bridge advancement, authorization issuance, and supervised native invocation. Failed-intent classification therefore becomes `reconciliation_required`, never `abandoned`, and reconciliation fails closed to `terminally_fenced` unless actual canonical state can be established. This is stricter than bridge-cache comparison alone.

Third, live canonical bridge bindings are maintained **per active execution**, not in one store-wide slot. Retry-contract registration now fails closed unless the bound live bridge returns exactly canonical authorization status `issued`. Missing binding after reopen, unknown authorization, bridge exceptions, or any non-issued lifecycle status all refuse a new retry contract.

The binding remains deliberately in-memory. Reopening a supervisory store does not recreate live canonical authority. There is no public live-bridge rebind path for an existing active execution after reopen; operations requiring live canonical status remain fail-closed until a new governed execution/attempt is registered through the normal bridge path.

## Runtime 2.2 Round-Four Reconciliation Boundary (v0.159)

v0.159 corrects a false-terminal-fence defect in the v0.158 continuation-intent path. A failure after intent creation is now classified from **actual bridge-resolved canonical movement**: if the exact episode remains at the expected step, the intent is abandoned and does not fence the execution; if the canonical step changed without a durable matching assessment, explicit reconciliation remains required. Authorized reconciliation closes an unchanged-step intent regardless of its prior prepared/abandoned/reconciliation-required label.

The canonical-step guarantee is deliberately scoped: assessments are bound to the canonical step resolved by `CanonicalRuntimeBridge` inside the governed Runtime 2.2 path. Direct calls that mutate the underlying canonical runtime bypass bridge-cache refresh and remain outside this step-freshness guarantee. Runtime 2.2 does not claim to sandbox arbitrary in-process access to the underlying runtime.

Retry-contract registration now also checks the canonical runtime's native authorization lifecycle through the live bridge. A canonical authorization that is already consumed/invalidated is sufficient to refuse a late retry contract even when no supervisory invocation marker exists.

A true `terminally_fenced` active execution is not revivable inside Runtime 2.2. The host must quarantine or terminate external work as appropriate, reconcile actual effect/world state through the existing effect/recovery surfaces, and start a new governed execution/attempt if further productive action is authorized.

## Runtime 2.2 Trust, Reconciliation, and In-Process Boundary (v0.158)

Runtime 2.2 does **not** manufacture external identity, cryptographic trust, controller truth, or Layer-1 authority. The host-configured `HostTrustProvider` remains the explicit integration trust boundary. Code with direct in-process mutation access to the `SQLiteSupervisoryStore` object, including the ability to replace `store.trust`, is therefore inside the trusted computing base. Runtime 2.2 is not a sandbox against arbitrary Python code already holding the store object.

For supervised native execution, once an authorization has been registered as an `ActiveExecutionRecord`, direct `CanonicalRuntimeBridge.invoke_authorized_native` is refused; the invocation must use the registered path so the pre-call invocation marker cannot be bypassed. Direct runtime calls made outside the supervisory bridge remain outside Runtime 2.2 operational guarantees.

Continuation assessments are bound to the canonical episode step on which they were committed. Control issue and dispatch both reject stale assessments whose canonical step no longer matches. A direct bridge advance is also refused for actively supervised episodes unless `ContinuationService` has first committed the matching continuation intent.

The in-memory canonical runtime and SQLite supervisor are still **not one atomic transaction**. v0.158 retains the durable continuation intent and adds explicit `reconcile_continuation_divergence`: a consistent prepared intent may be closed; a divergence that cannot be reconstructed is marked `terminally_fenced`. Dispatch honors the fence even for a request created before divergence. This is detection, containment, and governed reconciliation—not rollback of already-mutated canonical state.

Consequential control records carry both caller-reported timestamps and a trusted-clock timestamp. Caller timestamps remain provenance claims and do not establish current lease validity. Target handles are validated before request persistence and again against the exact registered adapter namespace at dispatch. Vendor-command bindings remain auditable declared mappings; proof of actual external execution still depends on configured controller attestation.

A canonical `continue` posture remains non-authorizing for control. An operator hold/pause of an otherwise healthy execution would require a separate explicitly authorized operator-control path.

## Historical v0.141 Reference — What Runtime V2.1 Added

Relative to the preserved v0.131 Runtime V2 baseline, the V2.1 line adds the applicable Framework Version 2.1 runtime surfaces while preserving the established canonical governance architecture.

### Actor Objective Interface

Runtime V2.1 adds a typed `O_i(t)` objective surface adjacent to `P_i(t)`.

Objectives carry identity, lifecycle/status, temporal applicability, scope, authority/provenance, version information, and declared relations where supplied. Objective-free operation remains valid.

Objectives are **not** inserted as a canonical operator and do not become:

- a hidden utility function;
- a policy selector;
- an authority source;
- an adequacy override;
- a viability condition; or
- a source of nonexistent future capability.

### Objective Responsiveness and Bounded Discovery

Runtime V2.1 provides typed Objective Responsiveness `Resp(pi,o)` using the bounded labels:

- `supports`
- `neutral`
- `conflicts`
- `unresolved`

Responsiveness is descriptive. The runtime does not infer objective-policy relations on its own.

Objective-directed discovery is bounded to registered/authorized surfaces. Objective relevance does not create Graph reachability, bypass Π completeness, remove otherwise represented policies, override Constraints or Adequacy, or confer execution authority.

### Information Governance

Memory/retrieval support now separates evidentiary quality from governance.

V2.1 governance metadata can represent:

- source authority;
- applicability scope;
- permitted-use scope;
- authorized surfaces;
- disposition;
- supersession;
- valid time;
- record/knowledge time; and
- provenance/source version.

Quality or confidence does not confer authority. Relevance does not confer permitted use. Rejected, superseded, defective, prohibited-for-use, historically-valid-noncurrent, unresolved, or contradicted material is not silently resurrected as ordinary current positive evidence.

### Transfer History

Runtime V2.1 adds typed Transfer History event, reference, package, validation, and host-service boundaries.

Transfer History remains distinct from:

- memory;
- expectation;
- current state;
- Productive Power;
- replay evidence; and
- authority.

The existence of a historical event does not itself make the event a current state fact or capability.

### Replay Sufficiency

Runtime V2.1 provides typed replay-evidence packages and replay-sufficiency assessment for historical decision reconstruction.

Replay material can retain decision-time state/perceived state, objective identity/version, admitted retrieval and governance evidence, history/expectation references, configuration/rule identities, pipeline results, and execution/transition evidence where applicable.

Replay evidence confers no live-state, selection, operator, or execution authority. A completed execution may still be replay-insufficient.

### Transition-Relevant State Sufficiency

Runtime V2.1 adds host/application-owned transition-relevant state-basis declarations and runtime validation/assessment surfaces.

The application remains responsible for the **semantic completeness** of domain-specific state. The runtime can validate the declared contract and associated invariants; it cannot infer every domain fact that should have been modeled.

Transfer History, confidence, evidence quality, or PP alone cannot substitute for a missing material current-state consequence.

### Objective Lifecycle and Bounded Re-entry

Objective-only lifecycle change is not automatically an actual-state or perceived-state change.

Runtime V2.1 invalidates only artifacts with explicit registered dependencies on the changed objective identity/objective-set version and then follows the existing bounded re-entry architecture. It does not automatically invalidate the viability prefix or represented Graph merely because an objective changed.

Independent `S_i(t)` or `P_i(t)` changes remain governed through their ordinary dependency/invalidation paths.

### Capability Development

Runtime V2.1 preserves the evidence-bound capability path inherited from Runtime V2 and applies it to capability-development objectives.

A desired, predicted, trained-for, or planned capability is not current Productive Power merely because an objective names it.

The required conceptual path is:

```text
objective / plan
    ↓
action or investment
    ↓
realized transition
    ↓
capability evidence
    ↓
represented reachability refresh
    ↓
current Productive Power
```

This prevents future-capability laundering.

## Canonical Decision Architecture

A compact Version 2.1 orientation view is:

```text
(P_i(t), O_i(t))
    ↓
Φ → H → G → ℛ → Graph / seed substrate → Π → completeness
    ↓
Constraints → Domain Framing → Adequacy → Σ → ε
    ↓
attempted execution / environmental realization
    ↓
authoritative Layer-1 state transition
```

`O_i(t)` is adjacent to `P_i(t)` but is not a canonical operator.

Information governance, Transfer History, replay evidence, and transition-relevant state sufficiency are supporting/governance surfaces. They should not be reinterpreted as additional Layer-2 operators.

Developers should use the integrated runtime interfaces rather than manually reproducing canonical operator semantics.

## Host / Runtime Boundary

The host/application remains responsible for:

- authoritative actual state and world mechanics;
- domain-specific measurements and interpretation;
- semantic completeness of transition-relevant state;
- application-specific objective content;
- external persistence;
- sensors and instrumentation;
- empirical evidence and capability measurements;
- external enforcement mechanisms and environmental effects; and
- the authoritative Layer-1 state transition.

The runtime governs the represented decision and execution process through the interfaces it actually implements.

Adapters must not silently replace runtime-owned governance or smuggle policy selection, adequacy judgments, Σ ordering, canonical re-entry decisions, or execution authority into host-supplied projections.

## Authority-Bound Native Call-Through

Runtime V2.1 preserves the synchronous authority-bound native call-through inherited from Runtime V2.

A consequential invocation through the runtime requires current runtime-issued authority derived from the canonical execution lineage. Registration of a callable is representation, not execution authority.

Authorizations are single-use and runtime-ledger-backed. Stale lineage, fabricated/reconstructed authority artifacts, binding/version mismatch, configuration mismatch, pause, abort, or reauthorization requirements fail closed before callable entry.

This protects the **PV-PP runtime-interface authority boundary**. It is not a Python sandbox, operating-system security boundary, network firewall, IAM replacement, or proof that host code cannot invoke its own function outside PV-PP.

## Synchronous Runtime Limitation

Frozen Runtime V2.1 v0.141 is **synchronous**.

It does **not** implement:

- asynchronous sensing;
- external instrumentation hooks;
- autonomous in-flight environment-change detection;
- a distributed execution framework; or
- guaranteed mid-flight cancellation in response to an external change the runtime has not been told about.

The Framework Version 2.1 architecture can permit governance around such changes when suitable instrumentation and execution architecture exist. That framework-level possibility must not be attributed to v0.141.

## Quick Start

Runtime V2.1 requires Python 3.

From the `runtime-v2.1` directory:

```bash
python3 -m pip install pytest
python3 -m pytest -q
```

Expected frozen-baseline result:

```text
1093 passed
```

## Small Economy V2.1 Benchmark

The Version 2.1 Small Economy benchmark is under `benchmarks/`.

The controlled benchmark program covers:

1. attainable objective;
2. conflicting objectives;
3. objective-versus-viability conflict;
4. impossible objective;
5. capability-development objective;
6. objective lifecycle change;
7. prohibited evidence; and
8. no-objective control.

The benchmark verifies that objective perturbations affect only authorized dependent surfaces and do not rewrite Graph admission or the controlled candidate substrate, fabricate impossible policies, override information governance, or convert desired future capability into current reachability.

See `BENCHMARK_SMALL_ECONOMY_v0_140.txt` and `HARDENING_SMALL_ECONOMY_v0_141.txt` for the banked benchmark/hardening records.

## Baseline, Hardening, and Integrity Records

- `BASELINE_AND_LINEAGE.md` records the successor-line baseline.
- `BASELINE_CODE_IDENTITY_CHECK.txt` records baseline code-identity evidence.
- `BENCHMARK_SMALL_ECONOMY_v0_140.txt` records the V2.1 benchmark closeout.
- `HARDENING_SMALL_ECONOMY_v0_141.txt` records the candidate-freeze hardening rerun.
- `V0141_FILE_HASHES.sha256` records file hashes for the frozen v0.141 tree.

These records support provenance and reproducibility; they do not create framework semantics.

## Documentation

Documentation under `runtime-v2.1.167/docs/` should be read as documentation for the frozen v0.167 Runtime 2.2 implementation.

Framework meaning remains governed by the authoritative PV-PP Framework Version 2.1 owner specifications. Frozen v0.141 source and tests govern implemented runtime behavior. Documentation explains those surfaces but does not redefine the framework.

Historical Runtime V2/v0.131 and Runtime V1/v0.70 documentation remains with those preserved generations and should be used for historical reproduction rather than as authority for v0.141 behavior.

## Versioning and Compatibility

The repository preserves the historical runtime generations and the current frozen Runtime 2.2 release:

- **Runtime V1 — v0.70:** frozen historical first-generation interface.
- **Runtime V2 — v0.131:** frozen prior second-generation successor.
- **Runtime V2.1 — v0.141:** frozen canonical predecessor for Runtime 2.2.
- **Runtime 2.2 — v0.167:** current frozen implementation.

Runtime V2.1 is a controlled successor rather than an in-place rewrite of either prior generation.

## Deliberate Scope Boundaries

Runtime V2.1 v0.141 does not claim to provide a universal:

- persistent runtime database;
- autonomous semantic-discovery engine;
- automatic PP-domain invention mechanism;
- LLM semantic adapter;
- learning algorithm;
- unrestricted runtime self-modification mechanism;
- operating-system/IAM/network/sandbox enforcement replacement;
- asynchronous sensing or external instrumentation layer;
- distributed execution framework; or
- guarantee of mid-flight cancellation.

Reachability-at-scale optimization remains a separate engineering concern rather than a change to the governance semantics.

## Release Notes

See `RELEASE_NOTES.md` for the v0.132–v0.141 Version 2.1 build history and frozen-release summary.

## License

See the repository-root `LICENSE` file for terms of use.

## Author

Lance Amundsen  
Amundsen Research & Development LLC
