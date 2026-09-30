"""B.5 Re-entry after change: dependency, change, invalidation, plan, bundle, Sigma executor."""

from pvpp_runtime import (
    GovernanceArtifactDependency,
    GovernanceDependencyChange,
    derive_dependency_invalidations,
    plan_governance_reentry,
    apply_executable_dependency_scope,
    GovernanceReusableArtifactBundle,
    validate_reusable_artifact_bundle,
    SigmaReusableAdequacyArtifact,
    execute_sigma_reentry,
)
from b2_cycle import run_cycle, make_actual

CYCLE_ID, CONFIG_ID = "cycle-1", "config-1"


def reenter_sigma():
    rt, integrated = run_cycle()
    d = integrated.decision
    # 1. Register, when the artifact is produced, what it depends on (12.2).
    deps = (
        GovernanceArtifactDependency("dep-sel", "selection-1", "Sigma", "evidence", ("ev-order",)),
    )
    # 2. Later, report which facts changed.
    changes = (
        GovernanceDependencyChange(
            "chg-1", "evidence", ("ev-order",), "tie-break evidence revised"
        ),
    )
    # 3. Derive invalidations from explicit matches only.
    # 4. Plan from the earliest invalidated stage (12.3).
    inv = derive_dependency_invalidations(deps, changes)
    plan = plan_governance_reentry(inv.reentry, inv.invalidation_signals)
    plan = apply_executable_dependency_scope(
        plan
    )  # changes only Joint Recovery Feasibility plans (12.4)
    assert plan.recompute_from_stage == "Sigma"
    # 5. Bundle the reusable results of THIS cycle: one payload per reusable stage,
    #    in plan order (12.4).
    payloads = {
        # Payloads for stages this executor does not consume are not inspected;
        # use the cycle's own records.
        "PPP": make_actual(),
        "Phi": d.pressure_field,
        "H": d.horizon_assessment,
        "G": d.governing_assessment,
        "R": d.regime_assessment,
        "Graph/Seed": d.graph_assessment,
        "Pi": d.pi_construction,
        "Pi Completeness": d.pi_completeness,
        "Constraints": d.constraints,
        "Domain Framing": d.domain_framing,
        "Joint Recovery Feasibility": d.joint_recovery_feasibility,
        "Adequacy": SigmaReusableAdequacyArtifact(d.adequacy, tuple(d.projection_records)),
    }
    bundle = GovernanceReusableArtifactBundle(
        "bundle-1",
        CYCLE_ID,
        integrated.initial_actual_state_id,
        CONFIG_ID,
        tuple((s, payloads[s]) for s in plan.reusable_upstream_stages),
    )
    check = validate_reusable_artifact_bundle(
        plan,
        bundle,
        expected_cycle_id=CYCLE_ID,
        expected_initial_state_id=integrated.initial_actual_state_id,
        expected_configuration_id=CONFIG_ID,
    )
    assert check.valid, check.violations
    # 6. Execute through the executor for this boundary (12.5). The result is selective
    #    recomputation: it is not
    #    enforcement-equivalent to a full canonical rerun.
    return d, execute_sigma_reentry(rt, plan, bundle, check)


if __name__ == "__main__":
    original, out = reenter_sigma()
    print(
        out.valid,
        out.status,
        out.recomputed_stage_ids,
        out.decision.selection.selected_policy_id,
        original.selection.selected_policy_id,
    )
