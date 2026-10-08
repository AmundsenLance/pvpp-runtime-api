
import time, statistics, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class DummyWorld: pass

reg=PVPPRegistry()
reg.register_action(ActionDefinition('steady','steady',()))
rt=PVPPRuntime(reg,DummyWorld())
frame=DomainFrame((DomainFrameTarget('G','continuity'),))
gov=GoverningAssessment(('G',),('G',))
comp=PiCompletenessAssessment('pi_complete',True)

def cycle_n(n):
    cs=tuple(CandidatePolicySet(f'p{i}',('a',)) for i in range(n))
    space=CandidatePolicySpace(cs,())
    pi=PiConstructionAssessment('pi_constructed','Mission',('G',),policy_space=space)
    cons=ConstraintsAssessment('constraints_passed_all_candidates',feasible_policy_ids=tuple(c.id for c in cs))
    framing=DomainFramingAssessment('domain_framing_valid',True,('G',),('G',))
    adeq=AdequacyAssessment('adequacy_passed',adequate_policy_ids=(cs[-1].id,))
    sel=PolicySelectionAssessment(
        'sigma_standard_policy_selected',cs,selected_policy_id=cs[-1].id,
        pi_completeness=comp,domain_framing=framing,constraints=cons,adequacy=adeq
    )
    return CanonicalDecisionCycleAssessment(
        'sigma_standard_policy_selected','Sigma',('Sigma',),
        governing_assessment=gov,pi_construction=pi,pi_completeness=comp,
        constraints=cons,domain_framing=framing,adequacy=adeq,selection=sel
    )

for n in (100,1000,5000,10000,50000):
    cyc=cycle_n(n)
    vals=[]
    for _ in range(9):
        t0=time.perf_counter()
        rt.build_execution_license_from_cycle(cyc,frame)
        vals.append((time.perf_counter()-t0)*1000)
    print(f'{n}: {statistics.median(vals):.3f} ms')
