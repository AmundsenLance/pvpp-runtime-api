# PV-PP Runtime API --- Runtime V2

Runtime V2 is the current successor runtime for applications built with
the Productive Value--Productive Power (PV-PP) framework.

## Status

**Runtime generation:** Runtime V2\
**Current build:** v0.131\
**Status:** Freeze candidate / public beta\
**Previous frozen generation:** Runtime V1, build v0.70 (Runtime
Interface Freeze 1)

Runtime V2 v0.131 is the current successor to the frozen v0.70 runtime.
It preserves the canonical PV-PP authority architecture while adding the
Version 2 state/interface model, governed re-entry, dynamic represented
structure, provenance and capability-evolution support, and
authority-bound native call-through.

The complete v0.131 regression suite passes:

``` text
967 passed
```

v0.131 also closes the authority-lineage defect found during hostile
testing of v0.130. A consequential callable invoked through the PV-PP
native interface now requires runtime-private authority derived through
the canonical:

`decision cycle → Σ → execution license → active ε episode → native execution authorization → invocation`

lineage. Host-created or reconstructed license, episode, context,
cycle-ID, or authority-looking metadata does not create native
invocation authority.

Runtime V1/v0.70 is retained separately for historical compatibility and
reproducibility. New integrations should normally target Runtime V2.

## What Runtime V2 Is

Runtime V2 provides the common runtime interface for developers building
applications using the PV-PP framework.

The basic integration model is:

1.  The application registers or supplies its governed PV-PP model
    structure.
2.  The host owns the actual world and authoritative state.
3.  The runtime constructs the represented/perceived decision state
    through the typed Runtime V2 boundaries.
4.  The runtime evaluates the state through the canonical PV-PP decision
    architecture.
5.  Σ resolves the governing decision and the runtime constructs the
    corresponding execution license.
6.  Entry into ε creates a runtime-recognized execution episode.
7.  A consequential native call requires a runtime-issued, single-use
    native execution authorization tied to that current canonical
    lineage.
8.  Native execution produces outcome telemetry/evidence; the host
    explicitly performs the authoritative Layer-1 state transition.
9.  Transition, evidence, prediction-error, capability, and other
    provenance can feed subsequent governed processing and re-entry.

The runtime does **not** take ownership of the application's world model
or silently mutate authoritative application state.

## Developer Starting Point

New Runtime V2 applications should normally begin with:

-   `PVPPRegistry`
-   the Runtime V2 typed state and adapter boundaries
-   `PVPPRuntime`
-   the canonical decision-cycle interface
-   execution licensing and ε episode creation
-   authority-bound native call-through when consequential external
    execution is required
-   explicit Layer-1 transition
-   transition/evidence provenance

Use the Runtime V2 examples and documentation rather than older custom
PV-PP sample programs. Earlier applications may predate the common
runtime or use Runtime V1 interfaces and should not be treated as
authoritative descriptions of Runtime V2.

## Quick Start

Runtime V2 v0.131 requires Python 3.

From the `runtime-v2` directory:

``` bash
python3 -m pip install pytest
python3 -m pytest -q
```

Expected result:

``` text
967 passed
```

### Native Call-Through Example

Runtime V2 includes a dedicated application-level battery call-through
example under `examples/battery_callthrough_service/`. This is the
recommended starting point for developers who want to understand the
Runtime V2 authority-bound native execution path.

The example carries a real battery action through the canonical decision
lineage into a registered Python callable. It demonstrates successful
governed execution, denial before callable entry, single-use/replay
protection, and propagation of callable execution failures back through
the runtime.

The important sequence is:

``` text
canonical decision cycle
        ↓
execution license
        ↓
active ε execution episode
        ↓
runtime-issued NativeExecutionAuthorization
        ↓
PVPPRuntime.invoke_authorized_native(...)
        ↓
NativeExecutionResult / telemetry / ε evidence
        ↓
explicit host-owned Layer-1 handling
```

Do not invoke a consequential callable through
`ExecutionBindingRegistry.invoke(...)`. That former public route fails
closed in Runtime V2 because a host-created `ExecutionContext` carries
no governance authority.

## Runtime Responsibilities

Runtime V2 implements the common PV-PP decision and governance
architecture, including projection, governing structure, recovery,
candidate construction, constraints, domain framing, adequacy,
selection, execution authority, evidence handling, and governed
re-entry.

At a high level, the canonical Layer-2 architecture includes:

`P_I(t) → Φ → H → G → R → Graph/seed substrate → Π → Π completeness → Joint Recovery → Constraints → Domain Framing → Adequacy → Σ → ε`

Shared policy projection **Q** is used during candidate evaluation where
required by the runtime architecture.

Developers should normally use the integrated runtime interfaces rather
than manually reproducing this operator sequence.

No downstream stage repairs an upstream authority or representation
defect. When material information changes, Runtime V2 can invalidate
affected artifacts and re-enter at the earliest canonical stage whose
authority has been invalidated.

## Typed State and Productive Capability

Runtime V2 preserves the distinction between broader actual/perceived
state and Productive Power.

The actual persistent state envelope can represent:

`S_I(t) = [PP_I(t), SPV_I(t), AVS_I(t), X_I(t)]`

PP is therefore a productive-capability component rather than a synonym
for the complete actual state.

Runtime V2 also provides typed support for distinctions such as access,
possession, permission, control, and operability;
configuration-dependent productive capability and joint feasibility;
reserve versus recovery mechanism and current recovery reachability; and
productive-role qualification/nested productive units.

## Host and Adapter Responsibilities

The host/application remains responsible for application-specific
semantics, including:

-   authoritative actual state and world mechanics;
-   domain-specific measurements and interpretation;
-   neutral causal/world projections supplied through runtime
    boundaries;
-   external persistence where required;
-   empirical evidence and capability measurements;
-   external enforcement mechanisms and effects; and
-   authoritative Layer-1 state transition.

Adapters must not silently replace runtime-owned governance.

In particular, application code should not smuggle policy selection,
adequacy judgments, Σ ordering, canonical re-entry decisions, or other
runtime-owned decision semantics into projection or adapter outputs.

## Registry and Dynamic Represented Structure

Applications describe governed PV-PP structure through `PVPPRegistry`
and related Runtime V2 interfaces.

Registered or governed structure may include domains, Productive Powers,
actions, recovery structures and dependencies, governing/regime
configuration, Graph and Π material, constraints, and Σ ordering.

Runtime V2 also supports bounded, provenance-bearing changes to
represented structure where explicitly governed. This includes dynamic
Graph reachability, structural-coverage qualification, controlled Graph
transformation admission/revision/removal, controlled novel
action/function admission, and recovery-necessity topology changes.

These capabilities are **not** autonomous semantic discovery or
unrestricted self-modification. Genuinely unrepresented consequential
behavior remains a coverage/admission problem rather than becoming
authorized merely because it is observed.

## Governance Re-entry

Runtime V2 supports earliest-invalidated-stage governance re-entry.

Depending on what has become stale or invalid, bounded re-entry can
begin at the appropriate canonical boundary, including fresh
perception/PPP processing, Φ, H, G, R, Graph/seed, Π, Π completeness,
Joint Recovery, Constraints, Domain Framing, Adequacy, or Σ.

Re-entry preserves only explicitly validated reusable artifacts and then
follows the normal downstream architecture. Memory-conditioned
perception, evidence-authority changes, capability prediction errors,
dynamic Graph changes, and other declared dependencies can participate
in this mechanism.

The native execution layer does not decide which canonical stage should
be revisited. It invalidates stale native authority when the governing
lineage is no longer current; canonical re-entry remains governed
separately.

## Evidence, Provenance, Control, and Capability Evolution

Runtime V2 includes typed foundations for:

-   provenance-bearing observations and epistemic qualification;
-   evidence-source authority/control and declared dependencies;
-   dynamic control/provenance topology;
-   capability-change observations;
-   cumulative non-scalar capability trajectories;
-   capability-driven Graph reachability and controlled
    constructibility;
-   capability-formation prediction error; and
-   architecture-invariance/adaptation assessment across application
    configurations.

These are runtime governance mechanisms. Production sensors, security
integrations, empirical capability tests, and domain-specific adapters
remain application/integration work.

## Authority-Bound Native Call-Through

Runtime V2 v0.131 provides synchronous native call-through for
registered consequential functions.

Registration alone grants no execution authority.

A native invocation requires a current runtime-issued
`NativeExecutionAuthorization`. The authorization is bound to the
canonical execution lineage, action, current binding identity and
implementation version, configuration identity where applicable, and
execution attempt.

Authorizations are runtime-ledger-backed and single use. They are
consumed immediately before callable entry. Replay, fabricated or
reconstructed authority artifacts, stale lineage, binding/version
mismatch, configuration mismatch, pause, abort, or reauthorization
requirements fail closed before callable entry.

If callable entry occurs, a later clean failure, indeterminate transport
failure, timeout, exception, or completed-invalid outcome does not
revive the authorization. A retry requires fresh authority.

This is a runtime-interface authority invariant, not a Python sandbox.
Host code that owns a callable can still bypass PV-PP by directly
calling its own function; such a direct call is not representable as a
PV-PP-authorized native invocation.

## Optional and Application-Specific Services

Runtime V2 exposes typed boundaries used as required by an application,
including memory retrieval, epistemic updating, projection, evidence
qualification, prediction error, Layer-1 transition, capability/recovery
support, and related adapter services.

Applications need only implement the services relevant to their
integration.

## Deliberate Scope Boundaries

Runtime V2 v0.131 does not claim to provide a universal:

-   persistent database or RuntimeStore;
-   autonomous semantic-discovery engine;
-   automatic PP-domain invention mechanism;
-   LLM semantic adapter;
-   learning algorithm;
-   unrestricted runtime self-modification mechanism;
-   operating-system/IAM/network/sandbox enforcement replacement;
-   asynchronous/distributed execution framework; or
-   guarantee of mid-flight cancellation.

Reachability-at-scale optimization also remains a separate engineering
concern rather than a change to the governance semantics.

The runtime governs the represented productive envelope. Conventional
enforcement mechanisms remain necessary to make licensed or prohibited
effects operationally real.

## Examples and Benchmarks

The Runtime V2 directory includes examples, benchmarks, and the complete
regression suite.

Some historical benchmark/support material is retained because it is
useful for regression reproducibility and architectural comparison. It
should not automatically be treated as the recommended architecture for
a new application.

For new development, prefer examples explicitly written for the Runtime
V2 interfaces. The two battery examples serve different purposes:

-   `examples/minimal_battery_service/` is the simpler canonical battery
    example and is useful for understanding the basic Runtime API
    integration pattern.
-   `examples/battery_callthrough_service/` is the recommended Runtime V2
    execution example. It demonstrates the complete
    decision/license/ε/native-authorization path through an actual
    registered Python callable, including denial, replay protection, and
    execution-failure propagation.

The call-through example should be preferred when consequential external
execution is part of the integration being developed.

## Documentation

The documentation under `runtime-v2/docs/` should be read as Runtime V2
documentation.

Runtime V1/v0.70 documentation remains under `runtime-v1/` and is
intentionally preserved rather than rewritten.

The Runtime V2 implementation and its frozen/candidate test evidence
govern callable implementation behavior. Framework meaning remains
governed by the authoritative PV-PP framework documentation; runtime
code does not redefine the theory.

## Versioning and Compatibility

The repository contains two runtime generations:

-   **Runtime V1 --- build v0.70:** Runtime Interface Freeze 1; retained
    unchanged for historical compatibility and reproducibility.
-   **Runtime V2 --- build v0.131:** current successor runtime and
    freeze candidate.

Runtime V2 is a controlled successor rather than an in-place rewrite of
the frozen Runtime V1 package. Applications that depend on Runtime V1
should continue to use the V1 directory unless deliberately migrated.

The development builds between v0.70 and v0.131 are engineering history
rather than separate supported runtime generations.

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

Runtime V2 is currently being treated as a freeze candidate/public beta.
Reproducible implementation problems, documentation ambiguities,
unexpected behavior, integration failures, and potential
authority-boundary defects are particularly useful.

Contact: Lance Amundsen --- amundsenlance@gmail.com
