import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class CountingWorld:
    def __init__(self): self.project_calls=0
    def perceive(self,s): return s
    def domain_value(self,s,d): return s.powers[d].value
    def project(self,s,a):
        self.project_calls += 1
        return ActionProjection(a.id,s,True)

def test_domain_assessment_projects_shared_baseline_once_not_once_per_domain():
    reg=PVPPRegistry()
    powers={}
    for i in range(1000):
        d=f'D{i}'; reg.register_domain(DomainDefinition(d,d,0.0))
        powers[d]=ProductivePowerState(d,1.0)
    reg.register_action(ActionDefinition('steady','steady',()))
    world=CountingWorld(); rt=PVPPRuntime(reg,world)
    rt._assess_domains(WorldState(0,powers))
    assert world.project_calls == 1
