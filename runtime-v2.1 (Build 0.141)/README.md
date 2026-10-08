# PV-PP Runtime API — Runtime V2.1

Runtime V2.1 is the current frozen successor runtime for applications built with the **Productive Value–Productive Power (PV-PP) Framework Version 2.1**.

## Status

- **Runtime generation:** Runtime V2.1
- **Frozen build:** v0.141
- **Status:** Frozen Version 2.1 successor baseline
- **Full regression:** **1093/1093 passing**
- **Small Economy V2.1 benchmark:** eight-case controlled program PASS
- **Prior preserved runtime:** Runtime V2 / v0.131
- **Historical first-generation runtime:** Runtime V1 / v0.70

Runtime V2.1 was developed as a conservative successor line from preserved Runtime V2 v0.131. Neither v0.131 nor v0.70 is modified by this release line.

Future runtime development should branch from frozen v0.141 rather than modify the frozen baseline in place.

## Directory Layout

```text
runtime-v2.1/
├── BASELINE_CODE_IDENTITY_CHECK.txt
├── V2_1_BASELINE_AND_LINEAGE.md
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

The source package is `pvpp_runtime/`. Tests, examples, benchmarks, documentation, baseline records, hardening evidence, and v0.141 file hashes remain with this runtime generation.

## What Runtime V2.1 Adds

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

- `V2_1_BASELINE_AND_LINEAGE.md` records the successor-line baseline.
- `BASELINE_CODE_IDENTITY_CHECK.txt` records baseline code-identity evidence.
- `BENCHMARK_SMALL_ECONOMY_v0_140.txt` records the V2.1 benchmark closeout.
- `HARDENING_SMALL_ECONOMY_v0_141.txt` records the candidate-freeze hardening rerun.
- `V0141_FILE_HASHES.sha256` records file hashes for the frozen v0.141 tree.

These records support provenance and reproducibility; they do not create framework semantics.

## Documentation

Documentation under `runtime-v2.1/docs/` should be read as Runtime V2.1 documentation.

Framework meaning remains governed by the authoritative PV-PP Framework Version 2.1 owner specifications. Frozen v0.141 source and tests govern implemented runtime behavior. Documentation explains those surfaces but does not redefine the framework.

Historical Runtime V2/v0.131 and Runtime V1/v0.70 documentation remains with those preserved generations and should be used for historical reproduction rather than as authority for v0.141 behavior.

## Versioning and Compatibility

The repository preserves three runtime generations:

- **Runtime V1 — v0.70:** frozen historical first-generation interface.
- **Runtime V2 — v0.131:** frozen prior second-generation successor.
- **Runtime V2.1 — v0.141:** current frozen Framework Version 2.1 successor baseline.

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
