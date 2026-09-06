from pvpp_runtime.models import CandidatePolicySet
from structural_world import build_runtime

cs=(CandidatePolicySet("food_policy",("favor_food",),(),("favor_food",)),
    CandidatePolicySet("material_policy",("favor_material",),(),("favor_material",)))
for blocked in (False,True):
    rt,state=build_runtime(blocked)
    a=rt.evaluate_policy_sets(state,cs)
    print('constraint_block=',blocked,'status=',a.status,'selected=',a.selected_policy_id,'conflicts=',a.conflicting_domains)
    for e in a.evaluations:
        print(' ',e.policy_id,'feasible=',e.feasible,'adequate=',e.adequate,'H=',dict(e.projected_horizons),'reasons=',e.reasons)
