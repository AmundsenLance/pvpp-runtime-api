
import sys,time,statistics
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import compare_contaminated_substrate_cycles
def cycle(n,drop=0):
    cs=tuple(SimpleNamespace(policy_class_ids=(f'c{i}',)) for i in range(n-drop))
    ss=tuple(SimpleNamespace(id=f's{i}',visible=True) for i in range(n-drop))
    return SimpleNamespace(pi_construction=SimpleNamespace(policy_space=SimpleNamespace(candidates=cs)),
        graph_assessment=SimpleNamespace(policy_seeds=ss),pi_completeness=SimpleNamespace(complete=True),
        adequacy=None,selection=None,governing_assessment=None)
for n in (10,100,1000,5000,10000):
    a=cycle(n); b=cycle(n,1)
    vals=[]
    for _ in range(5):
        t0=time.perf_counter()
        out=compare_contaminated_substrate_cycles(a,b,materially_relevant_reference_class_ids=(f'c{n-1}',))
        vals.append((time.perf_counter()-t0)*1000)
    print(f'{n} classes/seeds paired diagnostic: {statistics.median(vals):.4f} ms')
