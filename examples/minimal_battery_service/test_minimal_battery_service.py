from minimal_battery_service import *


def test_registry_contains_native_structure():
    r=build_registry()
    assert ENERGY_DOMAIN in r.domains and BATTERY_POWER in r.powers
    assert "battery_recovery" in r.recovery_plans
    assert set(r.graph_transformations)=={"continue_sampling","restore_battery"}


def test_typed_perceived_state_is_used():
    rt=build_runtime(); snap=rt.prepare_canonical_cycle_snapshot(make_actual())
    assert snap.perceived_decision_state.ppp[BATTERY_POWER] == 3.0
    assert snap.perceived_decision_state.spv_hat["stored_charge"] == 3.0


def test_low_reserve_selects_registered_recovery_policy_and_does_not_mutate_during_decision():
    actual=make_actual(3.0)
    rt=build_runtime(); out=rt.evaluate_integrated_canonical_cycle(actual,make_request())
    assert out.decision.stopped_at == "Sigma"
    assert out.decision.selection.selected_policy_id == "graph:restore_battery"
    assert out.final_actual_state is actual
    assert actual.pp["battery_units"] == 3.0


def test_full_explicit_execution_transition_and_provenance_chain():
    actual=make_actual(3.0)
    rt,integrated,lic,eps,handoff,tr,val,prov=run_once(actual)
    assert lic.action_ids == ("recharge",)
    assert eps.status == "completed" and eps.terminal
    assert tr.next_state.pp["battery_units"] == 8.0
    assert val.valid
    assert prov.prior_state_id == "state-0"
    assert prov.next_state_id == "state-0:next"
    assert actual.pp["battery_units"] == 3.0


def test_bad_projection_record_fails_closed():
    class BadQ(SharedProjectionQ):
        def project(self, req):
            return replace(super().project(req), model_version="")
    rt=PVPPRuntime(build_registry(),SensorWorldAdapter(),projection_service=BadQ(),layer1_transition_service=SensorLayer1Transition())
    try:
        rt.evaluate_integrated_canonical_cycle(make_actual(),make_request())
        assert False
    except ValueError as e:
        assert "model_version" in str(e)


def test_missing_layer1_service_is_visible():
    rt=PVPPRuntime(build_registry(),SensorWorldAdapter(),projection_service=SharedProjectionQ())
    out=rt.evaluate_integrated_canonical_cycle(make_actual(),make_request())
    lic=rt.build_execution_license_from_cycle(out.decision,make_request().domain_frame)
    entry=rt.instantiate_execution("ep",lic,entry_sufficient=True,max_steps=1)
    eps=rt.advance_execution(entry.episode,ExecutionObservation("done",completed=True))
    handoff=rt.build_layer1_transition_handoff(eps)
    try:
        rt.apply_layer1_transition(make_actual(),handoff)
        assert False
    except ValueError as e:
        assert "no Layer1TransitionService" in str(e)
