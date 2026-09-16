"""Minimal v0.130 authority-bound native call-through example."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pvpp_runtime import (PVPPRuntime, PVPPRegistry, ActionDefinition, ExecutionBindingRegistry,
    ExecutionBindingIdentity, ExecutionLicenseEnvelope)
from pvpp_runtime.models import ActionProjection

class World:
    def perceive(self, state): return state
    def domain_value(self, state, domain_id): return 0.0
    def project(self, state, action): return ActionProjection(action.id, state, True)

registry=PVPPRegistry()
registry.register_action(ActionDefinition("steady","steady",()))
registry.register_action(ActionDefinition("act","consequential action",()))
runtime=PVPPRuntime(registry,World())
bindings=ExecutionBindingRegistry(("steady","act"))
bindings.register(ExecutionBindingIdentity("act-native","act","1.0",("example",)), lambda context: "executed")

# In production this license comes from build_execution_license_from_cycle().
license=ExecutionLicenseEnvelope("policy-1",("act",),(),(),True,True,True,True,selection_mode="standard",entry_authorized=True)
episode=runtime.instantiate_execution("episode-1",license,entry_sufficient=True,max_steps=1).episode
authorization=runtime.issue_native_execution_authorization(episode,"act",bindings,decision_cycle_id="cycle-1")
result=runtime.invoke_authorized_native(authorization,bindings)
print(result.status, result.return_value)
