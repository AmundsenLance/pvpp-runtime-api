
import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
class W: pass
r=PVPPRegistry();r.register_action(ActionDefinition('steady','steady',()))
rt=PVPPRuntime(r,W())
local=PiCompletenessAssessment('pi_complete',True,('c',),('c',),(),('p',))
q=EpistemicSubstrateQualification('epistemically_contaminated','test basis',('w',))
for n in (100,1000,10000,50000,100000):
    vals=[]
    for _ in range(5):
        t0=time.perf_counter()
        for i in range(n):
            a=rt.qualify_pi_completeness_for_substrate(local,q)
        vals.append((time.perf_counter()-t0)*1000)
    med=statistics.median(vals)
    print(f'{n} qualification calls: {med:.3f} ms total; {med/n:.5f} ms/call')
