# PVPP Runtime V2.1 — Programmer Documentation

This directory contains the **current programmer documentation set for PVPP Framework Version 2.1 and frozen Runtime V2.1 v0.141**.

The former numbered 01–09 reader documents have been replaced here by three complementary books. They are organized by how a programmer is likely to use them: start quickly, learn and build, then look up exact runtime behavior.

## Where to Start

### 1. PVPP Getting Started

**Directory:** [`PVPP Getting Started/`](./PVPP%20Getting%20Started/)

The shortest path into PVPP and Runtime v0.141.

Use this first if you are new to the project. It introduces the framework/runtime/host boundary, shows how to verify the frozen runtime, and walks through a small runnable application.

### 2. PVPP Programmer's Guide

**Directory:** [`PVPP Programmer's Guide/`](./PVPP%20Programmer%27s%20Guide/)

The main learning and application-development guide.

Use it to understand PVPP concepts, model productive systems, build applications, work through the canonical decision architecture, handle execution and state transition, test models, and use the supplied development workflow and examples.

### 3. PVPP Programmer's Reference

**Directory:** [`PVPP Programmer's Reference/`](./PVPP%20Programmer%27s%20Reference/)

The detailed technical reference for frozen Runtime V2.1 v0.141.

Use it when exact behavior matters: runtime types and methods, stage contracts, host protocols, validation, execution licensing, governed re-entry, errors, limitations, compatibility, and the supported application-facing surface.

## Recommended Reading Path

**New programmer**

`PVPP Getting Started → PVPP Programmer's Guide → PVPP Programmer's Reference as needed`

**Experienced developer integrating v0.141**

`PVPP Getting Started → PVPP Programmer's Reference`

**Model/application designer**

`PVPP Getting Started → PVPP Programmer's Guide`

The three books are complementary. The Getting Started book is orientation and a runnable entry point; the Programmer's Guide teaches the framework and application method; the Programmer's Reference is for precise runtime lookup.

## Authority and Scope

These programmer documents explain and document PVPP, but they do not replace the underlying sources of authority.

- **Framework authority:** the canonical PVPP Framework Version 2.1 owner specifications control framework meaning.
- **Runtime authority:** the frozen Runtime V2.1 v0.141 source, tests, and frozen file manifest control implemented runtime behavior.
- **PVPP Getting Started:** introductory and application-facing guidance.
- **PVPP Programmer's Guide:** explanatory and application-development guidance.
- **PVPP Programmer's Reference:** detailed description of the frozen v0.141 application surface; it does not redefine the framework.

If explanatory documentation conflicts with a controlling framework owner specification or the frozen runtime source, the controlling source prevails.

## Framework and Runtime Are Distinct

PVPP Framework Version 2.1 and Runtime V2.1 v0.141 are related but separately versioned.

The framework defines the architecture. Runtime v0.141 is the frozen Version 2.1-aligned implementation and passed its frozen **1093/1093 regression suite**.

Runtime v0.141 is **synchronous**. It does not provide asynchronous sensing, external instrumentation hooks, autonomous in-flight environment-change detection, or guaranteed mid-flight cancellation. Applications may provide external instrumentation, state/evidence updates, and enforcement around the runtime, but those capabilities must not be attributed to v0.141 itself.

## Directory Layout

```text
docs/
├── PVPP Getting Started/
│   ├── ai-rules-and-prompts/
│   ├── battery/
│   ├── PVPP_Framework_Getting_Started_Ed2.1_rc1.docx
│   ├── PVPP_Framework_Getting_Started_Ed2.1_rc1.pdf
│   └── README.md
├── PVPP Programmer's Guide/
│   ├── programs/
│   ├── PVPP_Programmers_Guide_Ed2.1_rc1.docx
│   ├── PVPP_Programmers_Guide_Ed2.1_rc1.pdf
│   └── README.md
├── PVPP Programmer's Reference/
│   ├── programmers-reference/
│   ├── PVPP_Programmers_Reference_Ed2.1_rc1.docx
│   ├── PVPP_Programmers_Reference_Ed2.1_rc1.pdf
│   └── README.md
└── README.md
```

## Historical Documentation

The former numbered reader-document set is no longer the current programmer documentation in this directory. Historical and superseded materials may still be retained elsewhere for provenance and development history, but they should not be used to override the current Version 2.1 framework, frozen v0.141 runtime, or this three-book documentation organization.

---

**Framework baseline:** PVPP Framework Version 2.1  
**Frozen runtime baseline:** PVPP Runtime V2.1 v0.141  
**Programmer documentation:** PVPP Getting Started · PVPP Programmer's Guide · PVPP Programmer's Reference
