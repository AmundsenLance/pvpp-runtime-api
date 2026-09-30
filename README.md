# PV-PP Runtime API

Reference runtime implementations and programmer documentation for applications built with the **Productive Value–Productive Power (PV-PP) Framework**.

The current frozen runtime is **Runtime V2.1 v0.141**. Earlier frozen generations remain in this repository for reproducibility and comparison.

## Start Here — Runtime V2.1 Documentation

The former nine-document runtime documentation set has been replaced by a three-part programmer documentation set under `runtime-v2.1/docs/`.

| | Document | Use it for |
|---|---|---|
| **1** | **PV-PP Runtime: Getting Started** | The shortest path into PV-PP runtime programming: install and verify v0.141, understand the host/runtime boundary, and build a small runnable application. |
| **2** | **PV-PP Framework & Programming Guide** | Learn the framework and application-design method in depth, including modeling, the canonical decision cycle, execution, testing, and worked examples. |
| **3** | **PV-PP Framework & Runtime Programming Reference** | Exact technical reference for frozen runtime v0.141: public API, stage contracts, host protocols, execution, re-entry, errors, limitations, and compatibility. |

### 1. PV-PP Runtime: Getting Started

- [PDF](runtime-v2.1/docs/PVPP%20Getting%20Started/PVPP_Framework_Getting_Started_Ed2.1_rc1.pdf)
- [Word](runtime-v2.1/docs/PVPP%20Getting%20Started/PVPP_Framework_Getting_Started_Ed2.1_rc1.docx)
- Supporting material is in the same directory under `ai-rules-and-prompts/` and `battery/`.

### 2. PV-PP Framework & Programming Guide

- [PDF](runtime-v2.1/docs/PVPP%20Programmer%27s%20Guide/PVPP_Getting_Started_Ed2.1_rc2.pdf)
- [Word](runtime-v2.1/docs/PVPP%20Programmer%27s%20Guide/PVPP_Getting_Started_Ed2.1_rc2.docx)
- Companion programs are under `programs/`.

> **Repository filename note:** the Guide files currently use the filename `PVPP_Getting_Started_Ed2.1_rc2.*`; the directory name identifies them as the Programmer's Guide.

### 3. PV-PP Framework & Runtime Programming Reference

- [PDF](runtime-v2.1/docs/PVPP%20Programmer%27s%20Reference/PVPP_Programmers_Reference_Ed2.1_rc1.pdf)
- [Word](runtime-v2.1/docs/PVPP%20Programmer%27s%20Reference/PVPP_Programmers_Reference_Ed2.1_rc1.docx)
- Reference programs are under `programmers-reference/`.

**Recommended first path:** Getting Started → Guide as needed → Reference when exact runtime behavior or API contracts matter.

## Runtime Generations

| Runtime | Status | Regression baseline | Directory |
|---|---|---:|---|
| **V1 v0.70** | Historical frozen runtime | 496 / 496 | [`runtime-v1/`](runtime-v1/) |
| **V2 v0.131** | Preserved prior successor | 967 / 967 | [`runtime-v2/`](runtime-v2/) |
| **V2.1 v0.141** | **Current frozen runtime** | **1093 / 1093** | [`runtime-v2.1/`](runtime-v2.1/) |

New Version 2.1 applications should normally target **Runtime V2.1 v0.141**.

## Framework and Runtime Authority

Framework meaning is governed by the authoritative **PV-PP Framework Version 2.1** source set. Runtime source and tests govern implemented runtime behavior. The runtime does not redefine the framework.

The frozen v0.141 runtime is synchronous. It does **not** provide asynchronous sensing, external instrumentation hooks, autonomous in-flight environment-change detection, or guaranteed mid-flight cancellation. Applications may provide instrumentation and updated state/evidence around the runtime, but those capabilities must not be attributed to v0.141 itself.

The host/application remains responsible for authoritative actual state, domain/world mechanics, domain-specific measurements and projections, external persistence and instrumentation, environmental realization, and authoritative Layer-1 state transition.

## Repository Organization

```text
PV-PP-Runtime-API/
├── runtime-v1/                 # frozen v0.70 historical generation
├── runtime-v2/                 # frozen v0.131 prior successor
└── runtime-v2.1/               # current frozen v0.141 Version 2.1 successor
    ├── benchmarks/
    ├── docs/
    │   ├── PVPP Getting Started/
    │   ├── PVPP Programmer's Guide/
    │   └── PVPP Programmer's Reference/
    ├── examples/
    ├── pvpp_runtime/
    ├── tests/
    └── V0141_FILE_HASHES.sha256
```

## Verify Runtime V2.1 v0.141

From `runtime-v2.1/`, verify the frozen source set with `V0141_FILE_HASHES.sha256`, then run the frozen regression suite. The expected regression result is **1093 passed**.

## About PV-PP

PV-PP is a productive-system and decision framework centered on Productive Value, Productive Power, actual and perceived state, actor objectives, viability, recovery, governance, candidate construction, selection, consequential execution, and authoritative state transition.

This repository concerns the Runtime API and its programmer documentation. The broader PV-PP framework, proofs, research papers, and benchmark projects are maintained in their respective project repositories.

## License

Runtime source is licensed under the repository license. Documentation remains subject to the notices contained in the individual documents.
