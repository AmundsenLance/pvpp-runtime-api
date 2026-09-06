
import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass

def make(n_optional):
    r=PVPPRegistry()
    r.register_domain(DomainDefinition('production','production',0.0))
    r.register_action(ActionDefinition('steady','steady',('production',)))
    r.register_action(ActionDefinition('continue','continue',('production',)))
    r.register_action(ActionDefinition('plant','plant',('production',)))
    r.register_policy_seed(PolicySeedDefinition(
        'continue',('continue',),'continuation',('production',),('continuation',)
    ))
    r.register_policy_seed(PolicySeedDefinition(
        'plant',('plant',),'structural_shift',('production',),('crop_initiation',)
    ))
    for i in range(n_optional):
        aid=f'opt{i}'
        r.register_action(ActionDefinition(aid,aid,('production',)))
        r.register_policy_seed(PolicySeedDefinition(
            aid,(aid,),'structural_shift',('production',),(f'optional_{i}',)
        ))
    return PVPPRuntime(r,W())

for n in (0,10,100,1000,5000):
    vals=[]
    for _ in range(5):
        rt=make(n)
        t0=time.perf_counter()
        pi=rt.construct_pi(
            'Mission',('production',),('continuation','crop_initiation'),
            config=PiConstructionConfig(max_candidates=64)
        )
        vals.append((time.perf_counter()-t0)*1000)
        assert 'plant' in pi.emitted_candidate_ids
        assert len(pi.emitted_candidate_ids)==2
    med=statistics.median(vals)
    print(f"{n} optional structural seeds: {med:.4f} ms Mission Pi construction")
