import statistics
import time
from pvpp_runtime import CandidatePolicySet, CandidatePolicySpace, PVPPRuntime

class DummyRuntime:
    validate_pi_completeness=PVPPRuntime.validate_pi_completeness


def make_space(n, missing=False):
    candidates=tuple(CandidatePolicySet(f'p{i}',(),policy_class_ids=(f'class_{i}',)) for i in range(n))
    required=tuple(f'class_{i}' for i in range(n))
    if missing:
        required += ('material_missing_class',)
    return CandidatePolicySpace(candidates,required)


def run(n, missing, repeats):
    rt=DummyRuntime()
    space=make_space(n,missing)
    times=[]
    result=None
    for _ in range(repeats):
        t=time.perf_counter()
        result=rt.validate_pi_completeness(space)
        times.append((time.perf_counter()-t)*1000)
    return statistics.median(times), result

if __name__=='__main__':
    print('PV-PP v0.18 Pi completeness validation microbenchmark')
    print('Operation: explicit required-class coverage gate only; excludes policy projection/evaluation.')
    for n,repeats in ((100,200),(1000,100),(5000,40),(10000,25),(50000,8)):
        for missing in (False,True):
            ms,result=run(n,missing,repeats)
            label='one_missing' if missing else 'complete'
            print(f'{n:6d} classes {label:11s}: median {ms:.3f} ms; status={result.status}')
