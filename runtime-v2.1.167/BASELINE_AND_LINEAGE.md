# PV-PP Runtime 2.2 — Baseline and Lineage

## Current Successor Line

**Current build:** v0.167  
**Regression:** 1320/1320 passing  
**Status:** round-twelve hostile-review hardening build; proposed candidate-freeze controlling implementation only after clean independent retest  
**Frozen canonical predecessor:** Runtime V2.1 v0.141  
**Framework semantic authority:** PV-PP Framework Version 2.1, unchanged

Runtime 2.2 is a separately controlled successor engineering line derived from frozen Runtime V2.1 v0.141. It adds operational supervision around the canonical core; it does not rewrite the frozen baseline or silently promote prospective framework-permitted capabilities into v0.141.

Lineage:

```text
Runtime V1 / v0.70
  -> Runtime V2 / v0.131
  -> Runtime V2.1 / v0.141 (frozen canonical predecessor)
  -> Runtime 2.2 / v0.142-v0.155 (successor implementation and hardening)
  -> Runtime 2.2 / v0.156 (first independent hostile-review hardening)
  -> Runtime 2.2 / v0.157 (round-two trust/clock/atomicity hardening)
  -> Runtime 2.2 / v0.158 (round-three bridge/fence/reconciliation hardening)
  -> Runtime 2.2 / v0.159 (round-four false-fence/retry-status hardening)
  -> Runtime 2.2 / v0.160 (round-five abandoned-intent/indeterminate-advance/per-execution-bridge hardening)
  -> Runtime 2.2 / v0.161 (round-six supersession/prevalidation/private-binding/audit hardening)
  -> Runtime 2.2 / v0.162 (round-seven pre-mutation-validation/concurrent-intent hardening)
  -> Runtime 2.2 / v0.163 (round-eight administrator-reconciliation/guidance hardening)
  -> Runtime 2.2 / v0.164 (round-nine checkpoint-audit/idempotency/timestamp hardening)
  -> Runtime 2.2 / v0.165 (round-ten observation-identity/concurrent-idempotency/replay-fence hardening)
  -> Runtime 2.2 / v0.166 (round-eleven plain-data observation-identity hardening)
  -> Runtime 2.2 / v0.167 (round-twelve frozen-observation-snapshot/pathological-value hardening)
```

The v0.155 candidate-freeze disposition was superseded when independent hostile review demonstrated nine implementation defects in the additive supervision layer. v0.156 fixed those defects. A second independent review then identified trusted-clock, retry-cutoff, authority-root, cross-system atomicity, target-validation, and vendor-command-boundary issues. v0.157 addresses those findings without modifying Framework V2.1 or the frozen canonical runtime modules. A third independent review then found an alternate invocation bypass plus incomplete continuation-divergence fencing. v0.158 closes those bridge/fence gaps and adds explicit reconciliation/step binding. A fourth independent review found that harmless pre-advance failures could be misclassified as permanent divergence and that direct canonical invocation was not reflected in retry cutoff. v0.159 classifies failures from bridge-resolved canonical movement and consults the canonical native-authorization lifecycle for retry registration. A fifth independent review found that historical abandoned intents could later be reconciled into a false terminal fence, a runtime advance that mutated and then raised could still be misclassified from stale bridge cache, and the store-wide bridge slot made canonical retry status fail open after reopen or multi-runtime registration. v0.160 makes abandoned intents permanently non-fencing, marks entered-then-raised canonical advance state indeterminate, binds live bridges per active execution, and fails retry registration closed unless canonical status is exactly issued. A sixth independent review found that caller timestamp ordering could erase true divergence, pre-mutation canonical input rejection could be misclassified as indeterminate, public bridge rebinding could forge retry status, and not-required reconciliation closure lacked durable reconciliation/audit evidence. v0.161 removes timestamp-based supersession, prevalidates frozen-kernel no-mutation inputs before intent/call entry, makes live binding private to trusted active-execution registration, and records not-required reconciliation closure explicitly. A seventh independent review found that additional frozen-kernel input conversions/flag checks could still fail after call entry and that two SQLite supervisor connections could race a stale prepared-intent status update over a later successful close. v0.162 mirrors the complete known pre-lineage-write input contract and converts continuation-intent state handling to serialized/conditional cross-connection transitions with deterministic and stress concurrency coverage. An eighth independent review found that the administrator reconciliation path itself could race a healthy checkpoint and overwrite a newer `closed` result, and that unresolved/prepared states could emit misleading retry guidance. v0.163 serializes the complete reconciliation decision at the SQLite write boundary, uses compare-and-swap status transitions with atomic reconciliation/audit evidence, and distinguishes live/retryable prepared work from stale prepared state requiring authorized reconciliation. A ninth independent review confirmed those fixes and identified a checkpoint-path atomicity gap: the assessment/intent transaction committed before the `continuation_assessed` audit write, so an audit exception could look like checkpoint failure after durable success and invite a duplicate canonical advance. It also found that consequential checkpoint timestamps were not validated. v0.164 makes checkpoint assessment, intent close, idempotency identity and audit one SQLite transaction, returns existing assessments for replayed committed observation event IDs, and rejects invalid checkpoint timestamps before snapshot or intent creation. A tenth independent review confirmed those fixes and found that event-ID-only idempotency could hide materially changed observations, concurrent duplicate submissions could race past the pre-transaction lookup and double-advance, historical replay could mask a current fence, and reconciliation stress could leak raw SQLite lock errors. v0.165 binds event identity to a deterministic full-observation digest, serializes duplicate detection with intent creation, checks fence state before replay, maps reconciliation lock contention to typed concurrency conflict, and strengthens thread-warning/stress integrity. An eleventh independent review confirmed those fixes and found one residual identity gap: arbitrary nested observation objects were represented through `repr()`, which could hide changed content or create false conflicts, and lone-surrogate event IDs leaked raw Unicode encoding errors. v0.166 removes arbitrary-object fallback, constrains supervised observation identity to recursively validated plain data, uses explicit exact float encodings, and rejects invalid Unicode through typed validation before intent/canonical-call entry. A twelfth independent review confirmed those fixes and found that supervision still fingerprinted caller-owned live containers before passing those same live objects to canonical execution, so mutation/dynamic Mapping reads could separate stored identity from consumed content; it also found raw recursion/integer-limit errors on pathological values. v0.167 freezes one supervised plain-data observation snapshot and uses it throughout digest/intent/bridge/canonical execution, with bounded depth, cycle detection, and bounded integer identity.

`R3-01`–`R3-24` remain the identifiers of requirements developed under the Runtime-3.0 design program. `R22` remains the Runtime-2.2 implementation-test lineage. Both are retained as provenance labels.

---

# Historical Runtime V2.1 Baseline Record


## Current Baseline

**Runtime generation:** Runtime V2.1  
**Frozen build:** v0.141  
**Status:** Frozen Framework Version 2.1 successor baseline  
**Full regression:** 1093/1093 passing  
**Small Economy V2.1 benchmark:** eight-case controlled program PASS

Runtime V2.1 v0.141 is the current frozen successor runtime for the applicable PV-PP Framework Version 2.1 implementation. Future runtime development should branch from this frozen baseline rather than modify it in place.

## Preserved Predecessors

Runtime V2.1 does not replace or rewrite the earlier frozen runtime generations:

- **Runtime V1 / v0.70** remains the preserved first-generation Runtime Interface Freeze 1.
- **Runtime V2 / v0.131** remains the preserved prior second-generation successor baseline.
- **Runtime V2.1 / v0.141** is the current frozen Framework Version 2.1 successor baseline.

Each generation remains separately available for provenance, reproduction, comparison, and compatibility work.

## V2.1 Successor Bootstrap

The Runtime V2.1 development line began at **v0.132** as a controlled bootstrap from preserved Runtime V2 **v0.131**.

The v0.132 baseline identity check established that:

- **143 inherited Python runtime and test files were identical by SHA-256** to the v0.131 baseline;
- **0 inherited Python/test files changed**; and
- the bootstrap normalized the package directory name from `pvpp_runtime-build-v0-131` to `pvpp_runtime`.

Accordingly, v0.132 was a packaging/successor-line bootstrap rather than a semantic runtime revision.

See `BASELINE_CODE_IDENTITY_CHECK.txt` for the banked identity record.

## Version 2.1 Implementation Line

After the non-semantic v0.132 bootstrap, the Version 2.1 implementation proceeded incrementally:

- **v0.133** — Actor Objective Interface `O_i(t)`
- **v0.134** — Objective Responsiveness and bounded objective relevance/discovery
- **v0.135** — Information Governance
- **v0.136** — Transfer History and temporal provenance
- **v0.137** — Replay Sufficiency
- **v0.138** — Transition-Relevant State Sufficiency
- **v0.139** — Objective lifecycle dependency and bounded re-entry
- **v0.140** — Small Economy V2.1 controlled benchmark
- **v0.141** — hardening, validation, and freeze

The implementation program was conservative: validated v0.131 behavior was preserved unless an applicable Framework Version 2.1 requirement required additive support or controlled integration.

## Validation and Freeze Evidence

The frozen v0.141 release directory retains the following evidence records:

- `BASELINE_CODE_IDENTITY_CHECK.txt` — v0.131 → v0.132 inherited-code identity check.
- `BENCHMARK_SMALL_ECONOMY_v0_140.txt` — banked eight-case Small Economy V2.1 benchmark result.
- `HARDENING_SMALL_ECONOMY_v0_141.txt` — benchmark rerun during v0.141 hardening.
- `V0141_FILE_HASHES.sha256` — frozen-tree file hashes.
- `RELEASE_NOTES.md` — v0.132 through v0.141 implementation and release history.

The v0.141 full regression suite closed at **1093/1093 passing**. The Small Economy V2.1 controlled eight-case benchmark also passed during hardening.

## Framework / Runtime Boundary

This lineage record describes the runtime implementation history. It does not create or modify PV-PP framework semantics.

Canonical framework meaning is governed by the authoritative **PV-PP Framework Version 2.1 owner specifications**. Frozen v0.141 source and tests govern the implemented behavior of Runtime V2.1.

Runtime v0.141 remains **synchronous**. It does not implement asynchronous sensing, external instrumentation hooks, or autonomous in-flight environment-change detection. Framework-level permission for applications or future runtimes to govern instrumented changes must not be represented as an implemented v0.141 capability.

## Freeze Rule

**Runtime V2.1 v0.141 is frozen.**

Repository publication, documentation packaging, or future development should not silently alter the frozen source behavior. New runtime development should begin from a new successor branch/build line derived from v0.141 while retaining the frozen v0.141 baseline for reproduction and comparison.
