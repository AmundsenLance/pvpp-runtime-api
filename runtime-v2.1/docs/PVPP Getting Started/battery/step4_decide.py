"""Step 4: run one decision cycle and read what came back. Nothing is executed yet."""

from step1_registry import DOMAIN, FUNCTION, build_registry
from step2_world import World, actual_state
from step3_projection import Projection
from pvpp_runtime import (
    PVPPRuntime, CanonicalDecisionCycleRequest, PreliminaryPreservationObject,
    DomainFrame, DomainFrameTarget,
)


def make_runtime(layer1=None):
    return PVPPRuntime(build_registry(), World(), projection_service=Projection(),
                       layer1_transition_service=layer1)


def request():
    return CanonicalDecisionCycleRequest(
        PreliminaryPreservationObject("keep_measuring", "keep the sensor able to measure"),
        DomainFrame((DomainFrameTarget(DOMAIN, FUNCTION),)),
        required_graph_family_ids=("continuation", "corrective_repair"),
        materially_required_policy_class_ids=("continuation", "recovery"),
        projection_horizon=10.0)


def decide(battery, rt=None):
    rt = rt or make_runtime()
    return rt, rt.evaluate_integrated_canonical_cycle(actual_state(battery), request())


if __name__ == "__main__":
    for battery in (9.0, 5.0):
        _, out = decide(battery)
        d = out.decision
        print(f"\nbattery {battery}: {out.status}")
        print("  stages:    ", " -> ".join(d.pipeline_trace))
        print("  regime:    ", d.regime_assessment.regime)
        print("  candidates:", tuple(c.id for c in d.pi_construction.policy_space.candidates))
        print("  adequate:  ", d.adequacy.adequate_policy_ids)
        print("  finalists: ", d.selection.sigma.final_policy_ids)
        print("  selected:  ", d.selection.selected_policy_id)
