import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'examples'/'tiny_crossing_policy_world'))
from pvpp_runtime import CandidatePolicySet, CandidatePolicySpace
from run_crossing_choice import build_runtime, state


def c(pid, action, class_id):
    return CandidatePolicySet(pid,(action,),policy_class_ids=(class_id,))

rt=build_runtime()
complete=CandidatePolicySpace(
    (c('food_policy','favor_food','local_adjustment'),
     c('material_policy','favor_material','structural_shift')),
    ('local_adjustment','structural_shift'))
incomplete=CandidatePolicySpace(
    (c('food_policy','favor_food','local_adjustment'),),
    ('local_adjustment','exit_transfer'))

for label,space in [('complete',complete),('incomplete',incomplete)]:
    a=rt.evaluate_policy_space(state(),space)
    print(label)
    print('  completeness_status=',a.pi_completeness.status)
    print('  complete=',a.pi_completeness.complete)
    print('  missing=',a.pi_completeness.missing_class_ids)
    print('  downstream_status=',a.status)
    print('  evaluation_count=',len(a.evaluations))
    print('  selected_policy=',a.selected_policy_id)
