# PV-PP Runtime API

Public software repository for the **Productive Value–Productive Power (PV-PP) framework** runtime.

PV-PP is a productive-system and decision framework for representing Productive Value, Productive Power, actual and perceived state, actor objectives, viability, recovery, information governance, candidate construction, selection, consequential execution, and authoritative state transition.

This repository preserves **three runtime generations side by side**. They are intentionally separate so that earlier frozen interfaces remain reproducible while the current Runtime V2.1 line implements the applicable Framework Version 2.1 changes without rewriting historical releases.

## Current Runtime

For new Version 2.1 applications, use **Runtime V2.1 — v0.141** in `runtime-v2.1/`.

- **Status:** frozen Version 2.1 successor baseline
- **Regression:** **1093/1093 tests passing**
- **Execution model:** synchronous
- **Small Economy V2.1:** controlled eight-case objective-perturbation benchmark passes
- **Important limitation:** v0.141 has **no asynchronous sensing, external instrumentation hooks, or autonomous in-flight environment-change detection**

Applications may provide instrumentation and updated state/evidence around the runtime, but those capabilities must not be attributed to v0.141 itself.

## Runtime Generations

### Runtime V1 — v0.70

`runtime-v1/` contains the frozen **Runtime Interface Freeze 1**, build **v0.70**.

Runtime V1 established the common executable PV-PP interface and remains preserved as the historical first-generation runtime. Its source, tests, examples, benchmarks, and documentation should be treated as a frozen release line rather than updated to match later generations.

The v0.70 regression suite closed at **496/496 tests passing**. The Small Economy external integration suite also completed **77/77 tests passing**.

Use Runtime V1 for historical reproduction, existing v0.70 integrations, or study of the first frozen common runtime interface.

### Runtime V2 — v0.131

`runtime-v2/` contains the preserved second-generation runtime, build **v0.131**.

Runtime V2 is the frozen prior successor baseline from which the Version 2.1 implementation line was developed. It remains preserved separately and should not be modified to match V2.1.

The v0.131 regression suite closed at **967/967 tests passing**.

Major V2 capabilities include broader typed state, governed re-entry, dynamic represented structure, evidence/control provenance, capability evolution, architecture-invariance instrumentation, execution licensing, and authority-bound native call-through.

Use Runtime V2 for reproduction or comparison with the pre-V2.1 second-generation runtime.

### Runtime V2.1 — v0.141

`runtime-v2.1/` contains the current frozen **Framework Version 2.1 successor runtime**, build **v0.141**.

Runtime V2.1 is a conservative successor to v0.131. It preserves validated prior behavior while adding the applicable Version 2.1 interfaces and governance requirements.

Major additions include:

- typed actor objective interface `O_i(t)` adjacent to perceived decision state `P_i(t)`;
- Objective Responsiveness and bounded objective-directed discovery;
- information-governance metadata separating quality/confidence from authority, applicability, permitted use, disposition, and temporal provenance;
- Transfer History interfaces;
- Replay Sufficiency;
- Transition-Relevant State Sufficiency declarations and validation;
- objective lifecycle dependency and bounded re-entry; and
- controlled capability-development handling that prevents future-capability laundering.

The v0.141 regression suite closes at **1093/1093 tests passing**.

The Small Economy V2.1 benchmark also passes its controlled eight-case program covering attainable objectives, conflicting objectives, objective-versus-viability conflict, impossible objectives, capability development, objective lifecycle change, prohibited evidence, and a no-objective control.

## Objective Boundary

Framework Version 2.1 makes actor purpose explicit without turning purpose into hidden runtime authority.

`O_i(t)` may affect only authorized objective-responsive or bounded discovery surfaces. An objective does **not** become:

- a hidden utility function;
- a selector;
- an authority source;
- an adequacy override;
- a viability condition; or
- a source of nonexistent future Productive Power.

A capability-development objective may motivate a path toward capability. Desired or predicted capability becomes current PP only after a realized and evidenced capability/state transition.

## Repository Layout

```text
PV-PP-Runtime-API/
├── .git/
├── .gitignore
├── index.html
├── LICENSE
├── README.md
├── runtime-v1/       # frozen v0.70 historical generation
├── runtime-v2/       # frozen v0.131 prior successor
└── runtime-v2.1/     # current frozen v0.141 Version 2.1 successor
```

Runtime-specific source, tests, examples, benchmarks, release records, and documentation should remain with the generation they describe. Intermediate development builds are engineering history rather than additional top-level runtime generations.

## Which Runtime Should I Use?

For new Version 2.1 applications, use **Runtime V2.1 / v0.141**.

Use **Runtime V2 / v0.131** when reproducing or comparing against the preserved pre-V2.1 successor runtime.

Use **Runtime V1 / v0.70** when reproducing earlier PV-PP runtime work, validating software written specifically against v0.70, or examining the first frozen common runtime interface.

The three directories are preserved architectural/runtime generations, not merely build-number archives.

## Framework and Runtime Authority

The runtime implements portions of PV-PP; it does not define the entire framework.

Canonical **PV-PP Framework Version 2.1 owner specifications** govern framework meaning. Runtime source and tests govern implemented runtime behavior for the stated generation. Runtime documentation explains the public software interface but does not silently redefine canonical framework semantics.

A central design rule is that downstream stages do not repair upstream defects. Material invalidation must be handled at the appropriate governing stage, including governed re-entry where the runtime supports it.

## Version 2.1 Decision Surface

A compact orientation view is:

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

`O_i(t)` is shown adjacent to `P_i(t)` because objectives are explicit Version 2.1 inputs. It is not inserted as a canonical operator.

Information governance, Transfer History, replay evidence, and transition-relevant state sufficiency are supporting/governance surfaces and should not be mistaken for additional Layer-2 operators.

## Host / Runtime Boundary

PV-PP does not attempt to replace the host application or the external world being governed.

Applications remain responsible for:

- authoritative actual state and domain/world mechanics;
- semantic completeness of domain-specific transition-relevant state;
- application-specific measurements and objective content;
- external persistence and enforcement;
- sensors and instrumentation;
- environmental realization; and
- the authoritative Layer-1 state transition.

The runtime applies implemented PV-PP governance to the represented decision and execution process.

Runtime selection, licensing, or a successful callable return does not itself prove that the authoritative external world reached the intended successor state.

## Native Call-Through and Security Boundary

Runtime V2.1 preserves authority-bound **synchronous** native call-through. Consequential invocation through the runtime must derive from the applicable runtime-issued governance lineage rather than from host-created or reconstructed authority-looking objects.

Registration of a callable is representation, not execution authority.

Native call-through through the PV-PP interface is not a Python sandbox, operating-system security boundary, network firewall, IAM replacement, or proof that host code cannot invoke the same external function by another path. Production deployments should combine PV-PP governance with conventional enforcement appropriate to the environment.

## Synchronous Runtime Limitation

Frozen Runtime V2.1 v0.141 is synchronous.

It does **not** implement:

- asynchronous sensing;
- external instrumentation hooks;
- autonomous in-flight environment-change detection; or
- automatic cancellation/re-authorization in response to an external change that the runtime has not been told about.

The Framework Version 2.1 architecture may permit applications or future runtimes to govern such changes when suitable instrumentation and execution architecture exist. That framework-level possibility must not be described as a capability of v0.141.

## Documentation

Documentation should be read with the runtime generation it describes.

The current Version 2.1 documentation set uses the V2.1 framework and frozen v0.141 runtime as its implementation reference. Historical V1 and V2 documentation remains useful for reproduction and provenance but should not override current V2.1 semantics or be used to infer current implementation behavior.

When framework meaning and runtime implementation differ in scope, preserve the distinction explicitly.

## Project Status

- **Runtime V1 / v0.70:** frozen historical first-generation release.
- **Runtime V2 / v0.131:** frozen prior second-generation successor.
- **Runtime V2.1 / v0.141:** current frozen Version 2.1 successor baseline.
- **v0.141 regression:** **1093/1093 passing**.
- **Future runtime work:** should branch from frozen v0.141 rather than modify it in place.

## License

See the repository-root `LICENSE` file for terms of use.

## Project

PV-PP / Selfish Cooperation research  
Lance Amundsen / Amundsen Research & Development LLC
