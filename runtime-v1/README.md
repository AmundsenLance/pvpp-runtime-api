# PV-PP Runtime API

A runtime API for building applications with the Productive
Value--Productive Power (PV-PP) framework.

## Status

**Current runtime:** v0.70\
**Interface status:** Runtime Interface Freeze 1\
**Documentation status:** Public beta developer documentation

PV-PP Runtime v0.70 is the current frozen runtime interface.

Before the interface freeze:

-   the internal runtime regression suite passed 496/496 tests;
-   an independently maintained Small Economy integration suite passed
    77/77 tests unchanged against v0.70; and
-   approximately 50 subsequent Small Economy simulation builds exposed
    no additional framework/runtime defects.

The runtime is therefore being treated as a stable beta interface rather
than an architecture under active redesign.

The freeze rule is simple: the runtime should not be changed merely
because an alternative design appears cleaner or more convenient.
Changes should be considered only when a reproducible application or
benchmark failure demonstrates a genuine implementation or architectural
defect that cannot reasonably be handled compatibly.

## What This Repository Is

This repository provides the common runtime interface for developers
building applications using the PV-PP framework.

The basic integration model is:

1.  The application registers its PV-PP model structure.
2.  The host owns the actual world and authoritative state.
3.  The runtime evaluates the represented decision state through the
    PV-PP decision architecture.
4.  The runtime selects and licenses an action.
5.  Bounded execution occurs through epsilon.
6.  The host explicitly performs the authoritative Layer-1 state
    transition.
7.  Transition provenance can be carried into subsequent processing.

The runtime does **not** take ownership of the application's world model
or silently mutate authoritative application state.

## Developer Starting Point

New applications should normally begin with:

-   `PVPPRegistry`
-   `WorldAdapter`
-   `PVPPRuntime`
-   the canonical decision-cycle interface
-   execution licensing
-   epsilon execution
-   explicit Layer-1 transition
-   transition provenance

The repository includes a small v0.70-native reference application
intended to demonstrate this integration from beginning to end.

Developers should use the current runtime API and reference examples
rather than older PV-PP sample programs. Earlier applications were often
custom implementations created before the common runtime API existed and
are not authoritative descriptions of the frozen interface.

## Quick Start

PV-PP Runtime v0.70 requires Python 3.

From the repository root:

``` bash
python3 -m pip install pytest
python3 -m pytest -q
```

The frozen v0.70 regression suite should report:

``` text
496 passed
```

### Run the First Native Example

The recommended starting example is:

`examples/minimal_battery_service/`

Run its tests:

``` bash
python3 -m pytest -q examples/minimal_battery_service/test_minimal_battery_service.py
```

Expected result:

``` text
6 passed
```

Then run the application:

``` bash
PYTHONPATH=. python3 examples/minimal_battery_service/minimal_battery_service.py
```

The example demonstrates a complete v0.70 integration through canonical
selection, execution licensing, epsilon, explicit host-owned Layer-1
transition, transition validation, and provenance.

## Runtime Responsibilities

The runtime provides the common PV-PP decision architecture, including
the canonical decision pipeline and associated governance, recovery,
projection, selection, and execution interfaces.

At a high level, the canonical Layer-2 pipeline includes:

`PPP → Φ → H → G → R → graph/seed substrate → Π → Π completeness → Constraints → Domain Framing → Restoration Adequacy → Σ → ε`

Shared policy projection **Q** is used during candidate evaluation.

Developers normally invoke the integrated runtime interfaces rather than
manually reproducing this operator sequence.

## Host Responsibilities

The host application remains responsible for application-specific
semantics, including:

-   authoritative actual state;
-   domain-specific state interpretation;
-   world projections supplied through the appropriate runtime boundary;
-   external persistence where required;
-   external effects; and
-   authoritative Layer-1 state transition.

This separation is intentional.

Selection by the runtime does not itself mutate the actual world.

## Registry

Applications describe stable PV-PP structure through `PVPPRegistry`.

Depending on the application, registered structure may include:

-   domains;
-   Productive Powers;
-   actions;
-   recovery plans and dependencies;
-   governing and regime configuration;
-   graph and Π structure;
-   policy seeds;
-   constraints; and
-   Σ ordering.

Runtime v0.70 requires every registry to contain an action whose
identifier is exactly:

`steady`

`steady` represents the baseline or no-intervention continuation used by
the canonical runtime. Developers may give the action whatever
application-specific semantics are appropriate, but the registered
action ID must be `steady`.

## WorldAdapter

`WorldAdapter` is the principal boundary between the generic runtime and
the application's world semantics.

The adapter supplies information and projections the generic runtime
cannot infer itself.

The adapter does **not** replace the PV-PP decision architecture.
Applications should not reproduce Σ selection, Π construction, adequacy
evaluation, regime classification, or other runtime-owned decision logic
inside the adapter.

## Optional Services

Runtime v0.70 also exposes typed service boundaries for capabilities
such as:

-   shared policy projection;
-   Layer-1 transition;
-   memory retrieval;
-   epistemic updating;
-   capacity authority; and
-   prediction error.

Applications only need to implement optional services required by their
particular integration.

## What v0.70 Does Not Provide

The frozen runtime does not currently provide a universal:

-   persistent database or RuntimeStore;
-   autonomous runtime loop or scheduler;
-   LLM semantic adapter;
-   learning rule;
-   memory storage or retrieval algorithm;
-   unrestricted graph-search mechanism; or
-   universal arbitration rule for jointly impossible recovery
    obligations.

These remain host-owned, application-specific, or outside the present
runtime interface.

## First Example

The first native v0.70 teaching application is intentionally small.

It demonstrates:

-   registry construction;
-   Productive Power and domain registration;
-   action and recovery registration;
-   graph-native Π structure;
-   host-owned actual state;
-   typed perceived decision state;
-   shared projection Q;
-   canonical decision-cycle evaluation;
-   Σ selection;
-   execution licensing;
-   epsilon;
-   explicit host-owned Layer-1 transition; and
-   transition provenance.

The example is designed to teach the common runtime API rather than
reproduce an older custom PV-PP application architecture.

### A Note About Other Examples and Benchmarks

The repository contains additional historical example worlds and
benchmark support modules because they are dependencies of the frozen
v0.70 regression suite.

These files are retained to preserve regression reproducibility. They
should not be treated as the recommended architecture for new PV-PP
applications. Some originated during runtime development before the
present common API was frozen.

For new development, begin with `examples/minimal_battery_service/` and
the Volume Six Runtime API Reference.

## Documentation

The developer reference is:

**PV-PP Volume Six --- Runtime API Reference**\
*Beta Developer Documentation for Runtime v0.70*

The runtime implementation itself remains the ultimate authority for
callable behavior. Where documentation and runtime behavior differ,
v0.70 governs.

## Versioning and Compatibility

Runtime v0.70 is designated **Runtime Interface Freeze 1**.

Some callable surfaces remain in the package for compatibility with
earlier integrations. Their presence does not necessarily make them
recommended interfaces for new applications.

New beta applications should use the documented canonical integration
path.

## About PV-PP

Productive Value--Productive Power (PV-PP) is an economic and decision
framework centered on Productive Value, Productive Power, represented
and perceived productive state, governing domains, recovery structure,
and viability-aware action selection.

This repository is specifically concerned with the **runtime API**. It
is not intended to contain the complete theoretical, mathematical,
benchmark, or research record of the PV-PP framework.

## License

See the repository license for terms of use.

## Author

Lance Amundsen

## Support and Feedback

The PV-PP Runtime API is currently a public beta. If you are experimenting with the runtime and encounter an implementation problem, documentation ambiguity, unexpected behavior, or a potential defect, please get in touch.

Contact: Lance Amundsen — amundsenlance@gmail.com

Bug reports and reproducible examples are particularly useful.
