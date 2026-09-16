import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
class W: pass
reg=PVPPRegistry();reg.register_domain(DomainDefinition('D','D',0.0));reg.register_action(ActionDefinition('steady','steady',()))
rt=PVPPRuntime(reg,W())
s=WorldState(0.0,{'D':1.0},{'state_id':'s'})
q=ProjectionRequest(s,'p',('a',),'ordinary_adequacy',5.0,None,'s',{'state':'s'})
c=ProjectionInformationQualityClaim('reachability','route:A','graph+forecast','moderate','',('g1',))
r=PolicyProjectionRecord(policy_id='p',feasible=True,projected_horizons={'D':5.0},projection_horizon=5.0,right_censored_domain_ids=('D',),state_id='s',state_time=0.0,candidate_mode='ordinary_adequacy',information_quality_claims=(c,),model_version='m1',projection_input_trace={'state':'s'})
for n in (100,1000,10000,50000):
    vals=[]
    for _ in range(5):
        t0=time.perf_counter()
        for i in range(n): rt.validate_projection_record(q,r)
        vals.append((time.perf_counter()-t0)*1000)
    med=statistics.median(vals)
    print(f'{n} typed Q validations: {med:.3f} ms total; {med/n:.5f} ms/call')
