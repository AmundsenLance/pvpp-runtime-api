import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def test_active_epsilon_steps_keep_trace_linked_and_defer_path_materialization():
    reg=PVPPRegistry(); reg.register_domain(DomainDefinition('D','d',0))
    reg.register_action(ActionDefinition('steady','steady',()))
    rt=PVPPRuntime(reg,W())
    lic=ExecutionLicenseEnvelope('p',('a',),('D',),('f',),True,True,True,True)
    ep=rt.instantiate_execution('e',lic,entry_sufficient=True,max_steps=10001).episode
    last=None
    for i in range(10000):
        r=rt.advance_execution(ep,ExecutionObservation(str(i)))
        assert r.execution_path == ()
        ep=r.episode
        last=ep.trace_tail
    assert ep.step_count==10000
    assert last is not None
    assert last.prior is not None
