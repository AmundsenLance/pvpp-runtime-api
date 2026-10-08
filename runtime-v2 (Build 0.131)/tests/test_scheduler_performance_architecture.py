from benchmarks.performance_checkpoint_v0_11 import synthetic


def test_default_infeasible_diagnostics_return_minimal_witness_not_exhaustive_enumeration():
    rt, cal = synthetic(3, 8)
    rep = rt.assess_recovery_feasibility(cal)
    assert rep.jointly_feasible is False
    assert rep.infeasible_sets_complete is False
    assert len(rep.infeasible_corridor_sets) == 1
    witness = rep.infeasible_corridor_sets[0]
    assert witness == ("c0", "c1", "c2")


def test_exhaustive_mode_remains_available_for_offline_diagnostics():
    rt, cal = synthetic(3, 8)
    rep = rt.assess_recovery_feasibility(cal, diagnostic_mode="all_minimal")
    assert rep.jointly_feasible is False
    assert rep.infeasible_sets_complete is True
    assert rep.infeasible_corridor_sets == (("c0", "c1", "c2"),)


def test_high_capacity_feasible_schedule_preserves_parallel_execution():
    rt, cal = synthetic(8, 3, cap=8)
    rep = rt.assess_recovery_feasibility(cal)
    assert rep.jointly_feasible is True
    for period in range(3):
        assert len([s for s in rep.schedule if s.period_offset == period]) == 8
