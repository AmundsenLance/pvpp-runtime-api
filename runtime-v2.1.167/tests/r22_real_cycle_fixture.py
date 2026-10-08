"""Shared Runtime 2.2 successor test fixture using only the public integrated-cycle license path."""
from test_integrated_canonical_cycle_v041 import build as integrated_build, actual as integrated_actual, req as integrated_req


def new_runtime_and_license():
    rt, _world, _transition = integrated_build()
    return rt, license_from_real_cycle(rt)


def license_from_real_cycle(rt):
    request = integrated_req()
    integrated = rt.evaluate_integrated_canonical_cycle(integrated_actual(), request)
    return rt.build_execution_license_from_cycle(integrated.decision, request.domain_frame)
