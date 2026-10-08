# PVPP Runtime 2.2 v0.167 — Programmer Documentation

This directory contains the **current programmer documentation set for PVPP Framework Version 2.1 and frozen Runtime 2.2 v0.167**.

The documentation is organized as three complementary books, in the order a programmer is most likely to use them: start quickly, learn and build, then look up exact runtime behavior.

## Where to Start

### 1. PVPP Getting Started

**Directory:** [`PVPP Getting Started/`](./PVPP%20Getting%20Started/)

The shortest path into PVPP and frozen Runtime 2.2 v0.167.

Use this first if you are new to the project. It introduces the framework/runtime/host boundary, shows how to verify the frozen runtime, walks through a small runnable application, and introduces the v0.167 host-driven supervision model.

### 2. PVPP Programmer's Guide

**Directory:** [`PVPP Programmer's Guide/`](./PVPP%20Programmer%27s%20Guide/)

The main learning and application-development guide.

Use it to understand PVPP concepts, model productive systems, build applications, work through the canonical decision architecture, handle execution and state transition, integrate host-driven supervision, test models, and use the supplied development workflow and examples.

### 3. PVPP Programmer's Reference

**Directory:** [`PVPP Programmer's Reference/`](./PVPP%20Programmer%27s%20Reference/)

The detailed technical reference for frozen Runtime 2.2 v0.167.

Use it when exact behavior matters: runtime types and methods, stage contracts, host protocols, validation, execution licensing, governed re-entry, supervision contracts, control and enforcement boundaries, errors, limitations, compatibility, and the supported application-facing surface.

## Recommended Reading Path

**New programmer**

`PVPP Getting Started → PVPP Programmer's Guide → PVPP Programmer's Reference as needed`

**Experienced developer integrating v0.167**

`PVPP Getting Started → PVPP Programmer's Reference`

**Model/application designer**

`PVPP Getting Started → PVPP Programmer's Guide`

The three books are complementary. Getting Started provides orientation and a runnable entry point; the Programmer's Guide teaches the framework and application method; the Programmer's Reference provides precise runtime lookup.

## Authority and Scope

These programmer documents explain and document PVPP, but they do not replace the underlying sources of authority.

- **Framework authority:** the canonical PVPP Framework Version 2.1 owner specifications control framework meaning.
- **Runtime authority:** the frozen Runtime 2.2 v0.167 source, tests, and controlling file manifest govern implemented runtime behavior.
- **Frozen canonical predecessor:** Runtime V2.1 v0.141 remains preserved as the canonical predecessor from which the Runtime 2.2 successor line was developed.
- **PVPP Getting Started:** introductory and application-facing guidance.
- **PVPP Programmer's Guide:** explanatory and application-development guidance.
- **PVPP Programmer's Reference:** detailed description of the frozen v0.167 application surface; it does not redefine the framework.

If explanatory documentation conflicts with a controlling framework owner specification or the frozen v0.167 runtime source, the controlling source prevails.

## Framework and Runtime Are Distinct

PVPP Framework Version 2.1 and Runtime 2.2 v0.167 are related but separately versioned.

The framework defines the architecture and semantics. Runtime 2.2 v0.167 is the current frozen implementation. Its frozen full regression closed at **1320/1320 passing**. Runtime V2.1 v0.141 remains the frozen canonical predecessor and is retained separately for provenance, reproduction, and compatibility work.

Runtime 2.2 adds an operational supervisory layer around the canonical governance core. The canonical decision core remains synchronous. The runtime does not autonomously sense the external world, schedule its own checkpoints, or guarantee physical preemption of external work. Host instrumentation supplies observations, host code invokes the supervisory path, the runtime governs continuation and control authority through its implemented interfaces, and external controllers perform actual enforcement and world effects.

Do not attribute host instrumentation, controller behavior, or external world effects to the runtime itself.

## Documentation and Release Relationship

The books in this directory document **frozen Runtime 2.2 v0.167**.

The documentation may explain preserved v0.141 behavior where that behavior remains part of the canonical predecessor lineage, but references to v0.141 should not be read as making v0.141 the current release. For historical reproduction of v0.141 itself, use the preserved `runtime-v2.1/` tree and its associated documentation/evidence.

The current runtime tree is `runtime-v2.1.167/`.

## Directory Layout

```text
docs/
├── PVPP Getting Started/
├── PVPP Programmer's Guide/
├── PVPP Programmer's Reference/
└── README.md
```

Each book directory contains the applicable publication files and supporting material for that volume. File names inside those directories may change as publication drafts are finalized; the three directory names above are the stable documentation entry points.

## Historical Documentation

The former numbered reader-document set is no longer the current programmer documentation in this directory. Historical and superseded materials may still be retained elsewhere for provenance and development history, but they should not override the current Framework Version 2.1 authority, frozen Runtime 2.2 v0.167 source and tests, or this three-book documentation organization.

The preserved runtime generations remain separate:

- **Runtime V1 / v0.70** — historical first-generation frozen interface.
- **Runtime V2 / v0.131** — preserved second-generation successor.
- **Runtime V2.1 / v0.141** — frozen canonical predecessor for Runtime 2.2.
- **Runtime 2.2 / v0.167** — **current frozen runtime**.

---

**Framework baseline:** PVPP Framework Version 2.1  
**Current frozen runtime:** PVPP Runtime 2.2 v0.167  
**Full regression:** 1320/1320 passing  
**Programmer documentation:** PVPP Getting Started · PVPP Programmer's Guide · PVPP Programmer's Reference
