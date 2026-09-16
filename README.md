# PV-PP Runtime API

Public software repository for the **Productive Value-Productive Power (PV-PP) framework** runtime.

PV-PP is a formal framework for representing productive value, productive capability, perceived state, viability, recovery, governance, selection, and consequential execution. This repository contains the public runtime implementations that expose portions of that framework through a common software interface.

The repository preserves two runtime generations side by side. They are intentionally separate so that the frozen first-generation interface remains reproducible while Runtime V2 can incorporate the subsequent framework and runtime work without rewriting the historical release.

## Runtime Generations

### Runtime V1 — v0.70

`runtime-v1/` contains the frozen **Runtime Interface Freeze 1**, build **v0.70**.

Runtime V1 established the common executable PV-PP interface and remains preserved as the historical first-generation runtime. Its source, tests, examples, benchmarks, and documentation should be treated as a frozen release line rather than updated to match Runtime V2.

The v0.70 regression suite closed at **496/496 tests passing**. The Small Economy external integration suite also completed **77/77 tests passing**.

See:

- `runtime-v1/README.md`
- `runtime-v1/docs/`
- `runtime-v1/pvpp-runtime-build-v0-70/`

### Runtime V2 — v0.131

`runtime-v2/` contains the current second-generation runtime, build **v0.131**.

Runtime V2 preserves the mature v0.70 engineering baseline while incorporating the subsequent PV-PP framework and runtime requirements. Major additions include broader typed state, access/control/operability distinctions, configuration-dependent productive capability, richer recovery representation, qualified and nested productive units, dynamic represented structure, provenance-bearing evidence, capability evolution, governed re-entry, architecture-invariance instrumentation, and authority-bound native call-through.

The v0.131 regression suite closes at **967/967 tests passing**.

Runtime V2 native execution is bound to canonical governance lineage:

`decision cycle → Σ selection → execution license → active ε episode → native execution authorization → runtime-mediated invocation`

Registration of a callable is representation, not execution authority. Runtime V2 requires current runtime-issued authority before a consequential callable may be invoked through its native execution interface.

See:

- `runtime-v2/README.md`
- `runtime-v2/RELEASE_NOTES.md`
- `runtime-v2/docs/`
- `runtime-v2/pvpp-runtime-build-v0-131/`

## Repository Layout

```text
PV-PP-Runtime-API/
├── README.md
├── LICENSE
├── index.html
├── .gitignore
├── runtime-v1/
│   ├── benchmarks/
│   ├── docs/
│   ├── examples/
│   ├── pvpp-runtime-build-v0-70/
│   ├── pyproject.toml
│   ├── README.md
│   └── tests/
└── runtime-v2/
    ├── BASELINE_NOTICE.md
    ├── benchmarks/
    ├── docs/
    ├── examples/
    ├── pvpp-runtime-build-v0-131/
    ├── pyproject.toml
    ├── README.md
    ├── RELEASE_NOTES.md
    ├── tests/
    └── V070_REFERENCE_FILE_HASHES.sha256
```

## Which Runtime Should I Use?

For new applications, use **Runtime V2** unless you specifically need to reproduce or study the frozen v0.70 interface.

Use **Runtime V1** when reproducing earlier PV-PP runtime work, validating software written specifically against v0.70, or examining the first frozen common runtime interface.

The two directories are architectural generations, not merely build-number archives. Development builds between the frozen/current endpoints are preserved through repository history rather than represented as additional top-level runtime generations.

## Documentation

Each runtime generation carries documentation appropriate to that generation.

The `docs/General Introduction/` material provides an accessible introduction to PV-PP and its applications. The Scenario and Model Architecture Guide explains how to define a bounded PV-PP scenario before implementation. Volume Six, the Runtime API Reference, documents the developer-facing runtime interface.

Runtime V1 documentation should be read with v0.70. Runtime V2 documentation should be read with v0.131. Do not use a V2 document as authority for historical v0.70 behavior or assume a V1 implementation limitation still applies to V2.

## Framework and Runtime Authority

The runtime implements portions of PV-PP; it does not define the entire theory.

Canonical PV-PP framework documents govern framework meaning. Runtime documentation governs the public software interface for its stated runtime generation. Runtime source and tests provide executable implementation evidence.

No application, adapter, benchmark, or convenience interface should silently redefine canonical PV-PP operator semantics.

A central design rule is that downstream stages do not repair upstream defects. Material invalidation must be handled at the appropriate governing stage, including governed re-entry where supported by Runtime V2.

## Host / Runtime Boundary

PV-PP does not attempt to replace the host application or the external world being governed.

Applications remain responsible for supplying scenario state, measurements, neutral world mechanics, registered actions and structures, evidence, constraints, and host-owned consequential functions. The runtime applies PV-PP governance to the represented decision and execution process.

In Runtime V2, native call-through governs invocation **through the PV-PP runtime interface**. It is not a Python sandbox, operating-system security boundary, network firewall, IAM replacement, or proof that host code cannot invoke the same external function by another path. Production deployments should combine PV-PP governance with conventional enforcement appropriate to the environment.

## Security and Viability

PV-PP security can be viewed as a dual-corridor problem.

On the upper side, governance must constrain the capabilities, authority, reachability, and consequential actions that an agent or other productive system can accumulate or exercise.

On the lower side, governance must preserve the productive capacities, governing thresholds, reserves, and recovery routes that the larger system cannot afford to lose.

Runtime V2 provides machinery for governing consequential action within this broader viability structure. It does not claim to replace conventional cybersecurity controls; it provides a governance layer concerned with whether a represented productive successor state remains authorized, viable, and recoverable.

## Project Status

- **Runtime V1 / v0.70:** frozen historical release.
- **Runtime V2 / v0.131:** current successor runtime and freeze candidate.
- **Framework V2 integration:** completed for the current successor-runtime program.
- **Further runtime work:** should proceed as controlled successor development or hardening rather than modification of frozen v0.70.

The V2 `BASELINE_NOTICE.md` records the engineering lineage from v0.70. `V070_REFERENCE_FILE_HASHES.sha256` provides reference hashes for that baseline. `RELEASE_NOTES.md` records the V2 successor changes.

## License

See the repository-root `LICENSE` file for terms of use.

## Project

PV-PP / Selfish Cooperation research  
Lance Amundsen / Amundsen Research & Development LLC
