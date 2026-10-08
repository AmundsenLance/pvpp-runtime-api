## v0.167 — Round-Twelve Hostile-Review Hardening

Status: bankable hardening build; proposed candidate-freeze controlling implementation only after clean independent hostile retest.

v0.167 responds to the twelfth independent review of v0.166. The review confirmed all prior fixes and found one residual consistency gap: supervision validated and fingerprinted caller-owned observation content, then canonical execution re-read the original live object, allowing mutation or dynamic Mapping behavior to make the stored identity differ from what the runtime actually consumed. Pathological deep/cyclic/huge values could also escape through raw Python exceptions.

Changes:
- freeze each `ExecutionObservation` once into a plain-data snapshot before intent creation;
- use that exact snapshot for digesting, intent payload, bridge validation, and canonical advance;
- never re-read caller-owned observation mappings/containers after snapshot creation;
- add cycle detection and maximum nesting depth 64;
- bound supervised integers to 4096 bits and encode supported integer identity in hexadecimal;
- preserve exact list/tuple and numeric type identity, explicit NaN/+inf/-inf encoding, valid-Unicode enforcement, and string-key mapping rules; and
- keep timezone-naive ISO checkpoint timestamps interpreted as UTC.

Validation before packaging: full repository **1320/1320** passing; successor Phase 1-26 **227/227** passing; all warnings promoted to errors.

## v0.166 — Round-Eleven Hostile-Review Hardening

Status: bankable hardening build; independent hostile retest required before candidate-freeze audit.

v0.166 responds to the eleventh independent review of v0.165. The review confirmed all prior fixes and found one residual observation-identity problem: arbitrary objects nested inside `information` or `realized_pv_bundle` were represented by `repr()`, allowing changed content to alias when display strings matched and equal content to conflict when display strings contained process-specific identity. A lone surrogate in `event_id` could also leak raw `UnicodeEncodeError`.

Changes:
- define the supervised execution-observation value domain as deterministic plain data only: `None`, exact `bool`, exact `int`, exact `float`, valid-Unicode `str`, `list`, `tuple`, and `Mapping` with valid-Unicode string keys, recursively;
- encode finite floats by exact hexadecimal value and NaN/+inf/-inf explicitly;
- remove arbitrary-object `repr()` fallback from observation identity entirely;
- validate the same value domain both before continuation-intent creation and immediately before canonical call entry;
- reject lone-surrogate strings through typed `ObservationValidationError`;
- retain type-strict identity (`1` and `1.0` differ); and
- document that timezone-naive ISO checkpoint timestamps are interpreted as UTC.

Validation before packaging: full repository **1315/1315** passing; successor Phase 1-25 **222/222** passing; full repository passes with **all warnings promoted to errors**.

# PV-PP Runtime 2.2 — Release Notes

## v0.165 — Round-Ten Hostile-Review Hardening

**Status:** bankable hardening build; independent retest required before freeze.

v0.165 responds to the tenth independent hostile review of v0.164. The review confirmed H1/H2 closed and found four issues introduced or exposed by event-id idempotency: materially changed observations could be silently hidden by an old event ID, concurrent identical submissions could both advance before the unique-key collision was detected, replay could mask a current continuation fence, and reconciliation stress could leak raw SQLite lock errors from a worker thread.

Changes:
- persist a deterministic digest of the complete `ExecutionObservation` alongside committed event identity; identical replay is idempotent, changed content under the same event ID raises a typed identity conflict;
- repeat the committed-event identity lookup inside the serialized intent-creation transaction and record event ID/digest on the intent row, preventing concurrent duplicates from reaching canonical advancement;
- check continuation reconciliation/fence state before returning any historical replay assessment;
- translate SQLite busy/locked failures in administrator reconciliation to typed `ConcurrencyConflict`;
- strengthen the round-eight reconciliation stress test so unexpected worker-thread exceptions fail the test and each round proves reconciliation overlaps active checkpoint work;
- defensively close supervisory SQLite connections on store finalization so Python 3.13 does not emit unclosed-connection ResourceWarnings when short-lived stores fall out of scope;
- document that timezone-naive ISO checkpoint timestamps are interpreted as UTC.

Validation before packaging: full repository **1309/1309** passing; successor Phase 1–24 **216/216** passing. The complete repository also passes with **all warnings promoted to errors**.

## v0.164 — Round-Nine Hostile-Review Hardening

**Status:** bankable hardening build; independent retest required before freeze.

v0.164 responds to the ninth independent hostile review of v0.163. The review confirmed G1/G2 closed and identified two remaining issues outside the reconciliation logic: checkpoint audit emission occurred after commit, allowing a caller-visible failure after durable success, and checkpoint timestamps were not validated.

Changes:
- emit `continuation_assessed` inside the same SQLite transaction as assessment persistence and intent close;
- on audit failure before COMMIT, roll back supervisory persistence and enter the existing failed-intent/reconciliation path;
- persist execution-scoped observation event IDs with the assessment and make committed checkpoint replay idempotent;
- validate `checkpoint_at` / `assessed_at` as consequential ISO-8601 timestamps before snapshot capture or intent creation;
- migrate stale successor fixtures that used opaque terminalization timestamps.

Validation before packaging: full repository **1299/1299** passing; successor Phase 1–23 **206/206** passing.

## v0.163 — Round-Eight Hostile-Review Hardening

**Status:** bankable hardening build; independent retest required before freeze.

v0.163 responds to the eighth independent hostile review of v0.162. The review confirmed F1/F2 closed and identified an administrator-reconciliation lost-update race plus misleading retry guidance around unresolved/prepared continuation intents.

Changes:
- execute the full continuation-reconciliation decision under one `BEGIN IMMEDIATE` transaction;
- re-read intent, assessment and bridge state after the write boundary is acquired;
- compare-and-swap every reconciliation status transition and re-evaluate rather than overwrite newer durable state;
- commit the reconciliation row and audit event in the same transaction as the status change;
- make reconciliation/fence status take precedence over historical-assessment retry guidance;
- track locally created/in-flight intents so a stale prepared intent in the creating service requests authorized reconciliation, while other connections receive retryable concurrency guidance that explicitly mentions reconciliation if no checkpoint is live;
- add deterministic administrator-reconciliation/checkpoint race coverage and repeated reconciliation/checkpoint stress coverage.

Validation before packaging: full repository **1293/1293** passing; successor Phase 1–22 **200/200** passing.

## v0.162 — Round-Seven Hostile-Review Hardening

**Status:** bankable hardening build; independent retest required before freeze.

v0.162 responds to the seventh independent hostile review of v0.161. The review confirmed all v0.160 findings closed and identified two remaining defects: incomplete pre-mutation validation for canonical execution observations, and a cross-connection lost-update race in continuation-intent status handling.

Changes:
- Mirror all frozen-v0.141 pre-lineage-write observation checks before Runtime 2.2 records canonical call entry: active episode, `ExecutionObservation` type, non-empty string `event_id`, mapping/dict-convertible realized-PV and information fields, and actual-bool execution flags.
- Run the same validation before `ContinuationService` creates a durable intent and inside `CanonicalRuntimeBridge.advance_execution` before canonical-call entry.
- Serialize pending-intent read/decision under `BEGIN IMMEDIATE`; competing live checkpoints fail with a retryable concurrency conflict rather than mutating another service's prepared intent.
- Use compare-and-swap `WHERE ... status='prepared'` for failed-intent classification and successful intent close; never overwrite a concurrently closed/reconciled intent.
- Reject creation of a second open continuation intent and detect canonical-step movement before a new intent is committed.
- Add deterministic two-service lost-update regression and a repeated 20-round / two-services × 15-successful-checkpoints stress test proving unique committed steps and no false reconciliation/fence residue.

Validation before packaging: full repository **1288/1288** passing; successor Phase 1–21 **195/195** passing.

## v0.161 — Round-Six Hostile-Review Hardening

**Status:** hardening build; independent retest required before candidate freeze  
**Regression:** **1282/1282 passing**  
**Predecessor:** v0.160  
**Frozen canonical baseline:** Runtime V2.1 v0.141, unchanged

v0.161 responds to the sixth independent hostile review of v0.160. All earlier findings remain closed. The new findings were confined to supersession ordering, pre-mutation canonical refusal handling, live-bridge rebinding, and reconciliation/audit evidence.

Primary corrections:

- true divergence (`reconciliation_required` or `terminally_fenced`) is never superseded; supersession applies only to non-divergent `abandoned`/stale-`prepared` intent state and uses a durable cross-table insertion sequence for intents/assessments rather than caller timestamps;
- the v0.141 pre-mutation checks (active episode, `ExecutionObservation`, non-empty `event_id`) run before continuation-intent creation and again before the bridge records canonical call entry; input refusal therefore does not create indeterminate state;
- public `store.bind_canonical_bridge` rebinding is refused; live binding is private to trusted canonical registration, validates exact execution lineage, and cannot be replaced by a different bridge;
- closing abandoned/superseded reconciliation as not required writes both a reconciliation record and append-only audit event.

Boundary statement: live bridge bindings remain non-durable. A reopened store has no public mechanism to rebind an existing historical active execution. Retry-contract registration and other operations that require live canonical status remain fail-closed after reopen until a **new governed execution/attempt** is registered through the normal canonical bridge path.

## v0.160 — Round-Five Hostile-Review Hardening

**Status:** hardening build; independent retest required before candidate freeze  
**Regression:** **1273/1273 passing**  
**Predecessor:** v0.159  
**Frozen canonical baseline:** Runtime V2.1 v0.141, unchanged

v0.160 responds to the fifth independent hostile review of v0.159. All earlier findings remain closed. The remaining defects were confined to the newest continuation-reconciliation and live-canonical-status paths.

Primary corrections:

- `abandoned` intents are proven no-movement outcomes and can never become terminal-fence inputs; late reconciliation of an abandoned/superseded intent reports reconciliation not required;
- a canonical advance call that is entered and then raises marks the episode canonical-state-indeterminate rather than relying on stale bridge cache; indeterminate episodes refuse further governed advancement/authorization and fail closed at reconciliation;
- live canonical bridge bindings are stored per active execution, so registering a second runtime cannot overwrite the first execution's status source;
- retry-contract registration now requires canonical authorization status exactly `issued`; missing binding, unknown status, bridge exception, consumed or invalidated status all fail closed;
- reopened stores contain durable history but no live bridge binding and therefore cannot mint new retry safety until live canonical authority is reconstructed.

Boundary statement: Runtime 2.2 still does not claim durable reconstruction of live canonical object authority across process restart. Per-execution live bridge bindings are in-memory integration state; absence of that state is a fail-closed condition, not permission.


## v0.159 — Round-Four Hostile-Review Hardening

**Status:** hardening build; independent retest required before candidate freeze  
**Regression:** **1268/1268 passing**  
**Predecessor:** v0.158  
**Frozen canonical baseline:** Runtime V2.1 v0.141, unchanged

v0.159 responds to the fourth independent hostile review of v0.158. All earlier findings remain closed. The remaining real defect was false terminal fencing when a continuation intent existed but the canonical episode never advanced.

Primary corrections:

- pre-advance/transient failures classify the intent from actual canonical movement; unchanged step becomes `abandoned`;
- a real two-connection threaded material-change race proves `snapshot_conflict` is harmless when canonical state did not move;
- reconciliation closes an unchanged-step intent regardless of prior prepared/abandoned/reconciliation-required status;
- true advanced-but-unpersisted divergence remains fail-closed and terminally fences when not reconstructable;
- retry-contract registration consults the canonical runtime's public native-authorization status through the live bridge, closing the direct-runtime invocation blind spot.

Boundary statement: canonical-step freshness means bridge-resolved canonical state within the governed Runtime 2.2 path. Direct underlying-runtime mutation is outside that guarantee. A genuinely `terminally_fenced` active execution cannot be revived by Runtime 2.2; the host must reconcile/quarantine and begin a new governed attempt if further action is authorized.

## v0.158 — Round-Three Hostile-Review Hardening

**Status:** hardening build; not a frozen release  
**Regression:** **1261/1261 passing**  
**Predecessor:** v0.157 round-two hardening  
**Frozen canonical baseline:** Runtime V2.1 v0.141, unchanged

v0.158 responds to the third independent hostile review of v0.157. The prior round-two findings remain closed. Eight round-three regressions now cover the alternate native-invocation retry bypass, dispatch-after-divergence, explicit reconciliation closure/terminal fencing, canonical-step-bound assessment authority, guarded direct bridge advancement, issue-time target validation, and trusted-clock companion timestamps.

Primary corrections:

- once a native authorization has an `ActiveExecutionRecord`, direct bridge invocation is refused and execution must pass through `invoke_registered_native`;
- actively supervised canonical episodes can advance only under a prepared continuation intent;
- every `ContinuationAssessment` records its canonical episode step; control issue and dispatch reject stale step bindings;
- dispatch checks continuation reconciliation/fence state even for requests created before a divergence;
- `reconcile_continuation_divergence` is an explicit root-authorized operation that either closes a provably consistent intent or marks the execution `terminally_fenced`, with audit evidence;
- malformed target handles are rejected before durable control-request persistence;
- `ExecutionControlRequest` and `ControlAttemptRecord` retain caller timestamps and also record trusted-clock timestamps;
- documentation now states explicitly that direct in-process mutation access to the store object is inside the trusted computing base.

Boundary statement: the canonical runtime and SQLite supervisor remain separate state systems. v0.158 fences and reconciles detected divergence; it does not claim cross-system atomic rollback.

## v0.157 — Round-Two Hostile-Review Hardening

**Status:** hardening build; not a frozen release  
**Regression:** **1253/1253 passing**  
**Predecessor:** v0.156 round-one hostile-review hardening  
**Frozen canonical baseline:** Runtime V2.1 v0.141, unchanged

v0.157 responds to the second independent hostile review of v0.156. The first nine v0.155 findings remain closed. Six new round-two defects/contract gaps were reproduced against untouched v0.156 before production changes, and permanent regressions were added.

Primary v0.157 corrections:

- lease validity now uses an injectable trusted runtime clock; caller audit timestamps cannot backdate an expired lease into validity, and unparsable consequential timestamps fail closed;
- retry/idempotency contracts must pre-exist supervised native invocation, control dispatch, and effect evidence;
- owner/source/adapter/dependency/recovery registrations require host-configured root authority proof rather than a free-text authority label;
- controller attestation and Layer-1 authority are resolved through host verifier evidence; legacy caller booleans cannot create verified authority;
- continuation evaluation writes a durable intent before canonical mutation and fences reconciliation if persistence fails after in-memory canonical advancement; this detects/contains, but does not eliminate, the cross-system atomicity window;
- target-handle suffixes reject wildcard/path/whitespace forms;
- adapter registration separates no-widening semantic-effect mapping from the exact opaque vendor-command binding that is audited/dispatched;
- the two remaining successor fixtures that privately injected canonical licenses now use the real integrated-cycle license path;
- successor consequential-operation timestamp fixtures use parseable ISO-8601 values.

Boundary statement: Runtime 2.2 does not claim that PV-PP itself authenticates external principals, verifies cryptographic evidence, or makes SQLite and the in-memory canonical runtime one transaction. Those guarantees depend on the configured host trust/verifier mechanisms and the documented reconciliation boundary.

Policy: canonical `continue` remains non-authorizing for control. Operator hold/pause, if later required, must be a separately authorized feature rather than a control derived from `continue`.

## v0.156 — Independent Hostile-Review Hardening

**Status:** hardening build; not yet declared frozen release  
**Regression:** **1241/1241 passing**  
**Predecessor:** rejected candidate v0.155  
**Frozen canonical baseline:** Runtime V2.1 v0.141, unchanged

v0.156 responds to an independent hostile review of v0.155. Nine implementation defects in the additive supervision layer were reproduced on untouched v0.155 and converted into failing regressions before production fixes were applied. The frozen v0.141 canonical core was not modified.

Primary hardening corrections:

- durable governance snapshots and continuation assessments across supervisor-store reopen;
- exact subject-scoped dependency identity and equality lookup, eliminating SQL wildcard/subject-collapse behavior;
- serialized snapshot-validation/canonical-advance/assessment commit boundary;
- closed semantic control vocabulary plus continuation-posture/control consistency;
- structured adapter target namespaces and constrained no-widening semantic mappings;
- trusted canonical finality derived from persisted terminal continuation assessment rather than caller assertion;
- retry/idempotency contracts must pre-exist effect evidence;
- recovery control/world checks resolve from durable authoritative evidence rather than caller `reconciled` strings;
- governed supervisory-owner registration and enforced lease expiry.

Test-strength changes:

- all successor fixtures that formerly injected licenses into the private canonical ledger now obtain licenses through `evaluate_integrated_canonical_cycle` -> `build_execution_license_from_cycle`;
- real crash validation uses spawned child processes plus `os._exit()` rather than clean database close, including an 11-stage durable-boundary death matrix;
- shared-dependency fan-out includes real threaded concurrent assessment;
- the R3 conformance closure now executes a 24-requirement behavioral gate instead of treating test-name existence as proof;
- nine independent v0.155 hostile probes are permanent regressions.

Naming note: `R3-01`–`R3-24` retain the historical Runtime-3.0 design-program identifiers; `R22` test names retain Runtime-2.2 implementation lineage. The packaged runtime is Runtime 2.2.

## v0.155 — Rejected Candidate / Hardening Baseline

v0.155 passed its then-current 1218-test suite but was subsequently rejected as a freeze candidate after independent hostile review exposed nine real supervision-layer defects and several test-strength gaps. It remains a reproducible predecessor for the v0.156 hardening regressions.

---

# Historical Runtime V2.1 Release Notes


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
