# PV-PP Runtime API

Reference runtime implementations and programmer documentation for applications built with the **Productive Value–Productive Power (PV-PP) Framework**.

The current frozen runtime is **Runtime V2.1 build v0.167**, located in [`runtime-v2.1.167/`](runtime-v2.1.167/). Earlier frozen builds remain in this repository for provenance, reproducibility, and comparison.

## Start Here — Current Runtime Documentation

The current programmer documentation is organized as three complementary books under [`runtime-v2.1.167/docs/`](runtime-v2.1.167/docs/).

| | Document | Use it for |
|---|---|---|
| **1** | **PVPP Getting Started** | The shortest path into PV-PP runtime programming: verify the frozen build, understand the framework/runtime/host boundary, and build a small runnable application. |
| **2** | **PVPP Programmer's Guide** | Learn the framework and application-design method in depth, including modeling, the canonical decision cycle, execution, supervision, testing, AI-assisted development, and worked examples. |
| **3** | **PVPP Programmer's Reference** | Exact technical reference for frozen build v0.167: public and supported APIs, stage contracts, host protocols, execution, supervision, re-entry, errors, limitations, and compatibility. |

### 1. PVPP Getting Started

- [Browse the Getting Started directory](runtime-v2.1.167/docs/PVPP%20Getting%20Started/)

### 2. PVPP Programmer's Guide

- [Browse the Programmer's Guide directory](runtime-v2.1.167/docs/PVPP%20Programmer%27s%20Guide/)

### 3. PVPP Programmer's Reference

- [Browse the Programmer's Reference directory](runtime-v2.1.167/docs/PVPP%20Programmer%27s%20Reference/)

**Recommended first path:** Getting Started → Guide as needed → Reference when exact runtime behavior or API contracts matter.

> **Documentation links:** The directory links above are intentionally stable while the three books complete final editorial revision. Direct PDF and Word links can be added after the final filenames are frozen.

## Runtime Lineage

| Runtime directory | Frozen build | Status | Regression baseline |
|---|---:|---|---:|
| [`runtime-v1/`](runtime-v1/) | v0.70 | Historical Runtime V1 interface freeze | 496 / 496 |
| [`runtime-v2/`](runtime-v2/) | v0.131 | Historical Runtime V2 frozen baseline | 967 / 967 |
| [`runtime-v2.1/`](runtime-v2.1/) | v0.141 | Preserved prior Runtime V2.1 build | 1093 / 1093 |
| [`runtime-v2.1.167/`](runtime-v2.1.167/) | **v0.167** | **Current frozen Runtime V2.1 build** | **1320 / 1320** |

New Version 2.1 applications should normally target **Runtime V2.1 build v0.167** in `runtime-v2.1.167/`.

## Framework and Runtime Authority

Framework meaning is governed by the authoritative **PV-PP Framework Version 2.1** source set. Runtime source and tests govern implemented runtime behavior. The runtime does not redefine the framework.

Build v0.167 adds **host-driven in-flight supervision** while preserving a synchronous canonical decision core. Host instrumentation supplies observations and host code invokes supervisory checkpoints. The runtime evaluates the admitted evidence and governs continuation; external controllers remain responsible for carrying out stop, pause, rollback, or other enforcement actions in the external world.

The runtime does **not** autonomously sense the environment, schedule its own checkpoints, or by itself guarantee that an external process has stopped. Applications remain responsible for authoritative actual state, domain/world mechanics, domain-specific measurements and projections, external persistence and instrumentation, environmental realization, enforcement, and authoritative Layer-1 state transition.

PV-PP runtime governance does not replace operating-system security, IAM, network enforcement, sandboxing, or other conventional controls required by the deployment environment.

## Repository Organization

```text
PV-PP-Runtime-API/
├── runtime-v1/                         # historical frozen Runtime V1, build v0.70
├── runtime-v2/                         # historical frozen Runtime V2, build v0.131
├── runtime-v2.1/                       # preserved prior Runtime V2.1, build v0.141
└── runtime-v2.1.167/                   # current frozen Runtime V2.1, build v0.167
    ├── benchmarks/
    ├── docs/
    │   ├── PVPP Getting Started/
    │   ├── PVPP Programmer's Guide/
    │   └── PVPP Programmer's Reference/
    ├── examples/
    ├── pvpp_runtime/
    ├── tests/
    └── V0167_FILE_HASHES.sha256
```

The current runtime directory also contains lineage, conformance, hardening, release-note, and hash/provenance records used to identify and reproduce the frozen build.

## Verify Current Runtime v0.167

From `runtime-v2.1.167/`, verify the frozen source set with `V0167_FILE_HASHES.sha256`, then run the frozen regression suite. The expected full regression result is **1320 passed**.

Use the build's own README, release notes, conformance record, and provenance files for the exact verification procedure and frozen-source identity.

## About PV-PP

PV-PP is a productive-system and decision framework centered on Productive Value, Productive Power, actual and perceived state, actor objectives, viability, recovery, governance, candidate construction, selection, consequential execution, and authoritative state transition.

This repository concerns the Runtime API and its programmer documentation. The broader PV-PP framework, proofs, research papers, and benchmark projects are maintained in their respective project repositories.

## License

Runtime source in this repository is licensed under the **Apache License 2.0** unless a file or component states otherwise. Documentation remains subject to the notices contained in the individual documents. See [`LICENSE`](LICENSE).
