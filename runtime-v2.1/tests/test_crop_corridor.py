import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'examples'/'tiny_crop_world'))
from run_crop import build_runtime, initial_state

def test_plant_is_selected_by_terminal_corridor_adequacy():
    rt=build_runtime(); a=rt.decide(initial_state()); assert a.selected_action=='plant'
def test_runtime_ledger_persists_corridor_and_forces_continuation():
    rt=build_runtime(); s=initial_state()
    a=rt.decide(s); er=rt.world.execute(s,a.selected_action); rt.record_execution(er); s=er.next_state
    assert rt.active_corridors['crop_recovery'].remaining_actions==('maintain_crop','harvest_crop')
    a=rt.decide(s); assert a.selected_action=='maintain_crop'
    er=rt.world.execute(s,a.selected_action); rt.record_execution(er); s=er.next_state
    a=rt.decide(s); assert a.selected_action=='harvest_crop'
    er=rt.world.execute(s,a.selected_action); rt.record_execution(er); s=er.next_state
    assert rt.active_corridors['crop_recovery'].status=='complete'
    assert s.power_value('food_stock')==35
