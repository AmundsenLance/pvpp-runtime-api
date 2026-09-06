import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ConstraintAssessment, ConstraintViolationProfile

class W:
    def project(self,s,a): return None
    def compare_constraint_violation_severity(self,a,pa,b,pb,cls):
        # benchmark metadata encodes a coherent total preorder in the hard rule id
        def rank(p):
            ids=p.hard_violation_ids if cls=='hard' else (p.conditional_violation_ids if cls=='conditional' else p.soft_violation_ids)
            return int(ids[0].split(':')[1]) if ids else 0
        x,y=rank(pa),rank(pb); return (x>y)-(x<y)

def run(n,reps=5):
    r=PVPPRegistry(); r.register_action(ActionDefinition('steady','s',()))
    rt=PVPPRuntime(r,W())
    rows=tuple(ConstraintAssessment(f'p{i}',False,(),ConstraintViolationProfile((f'h:{n-i}',),(),(),()),'canonical_typed_constraint_profile') for i in range(n))
    times=[]
    for _ in range(reps):
        t=time.perf_counter(); x=rt.evaluate_sigma_terminal(rows); times.append((time.perf_counter()-t)*1000)
        assert x.selected_policy_id==f'p{n-1}'
    return statistics.median(times)

if __name__=='__main__':
    for n in (100,1000,5000,10000,50000): print(f'{n}: {run(n):.3f} ms')
