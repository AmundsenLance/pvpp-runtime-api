import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'examples'/'tiny_dual_corridor_world'))
from run_dual import build_runtime, calendar

def test_two_corridors_individually_feasible_but_jointly_infeasible_at_five():
    rt=build_runtime(); rep=rt.assess_recovery_feasibility(calendar(5))
    assert rep.jointly_feasible is False
    assert rep.infeasible_corridor_sets == (("corridor_A","corridor_B"),)

def test_two_corridors_jointly_feasible_at_six():
    rt=build_runtime(); rep=rt.assess_recovery_feasibility(calendar(6))
    assert rep.jointly_feasible is True
    assert len(rep.schedule)==6
    assert {s.corridor_id for s in rep.schedule}=={"corridor_A","corridor_B"}

def test_no_sacrifice_rule_is_embedded_in_infeasible_report():
    rt=build_runtime(); rep=rt.assess_recovery_feasibility(calendar(5))
    assert rep.schedule==()
    assert any("no priority" in n for n in rep.notes)

def test_deadline_structure_constrains_schedule_without_value_priority():
    from pvpp_runtime import ActiveRecoveryCorridor
    rt=build_runtime()
    rt.active_corridors['corridor_A']=ActiveRecoveryCorridor('corridor_A','K','function_A',('teach_A1','teach_A2','teach_A3'),2)
    rt.active_corridors['corridor_B']=ActiveRecoveryCorridor('corridor_B','K','function_B',('teach_B1','teach_B2','teach_B3'),5)
    rep=rt.assess_recovery_feasibility(calendar(6))
    assert rep.jointly_feasible is True
    a_periods=[s.period_offset for s in rep.schedule if s.corridor_id=='corridor_A']
    assert max(a_periods) <= 2
