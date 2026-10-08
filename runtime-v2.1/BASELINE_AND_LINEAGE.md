# PV-PP Runtime V2.1 — Baseline and Lineage

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
