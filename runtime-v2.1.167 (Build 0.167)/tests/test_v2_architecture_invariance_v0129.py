from pvpp_runtime import (PVPPRegistry,PVPPRuntime,DomainDefinition,ActionDefinition,AdapterIdentity,
 RuntimeConfigurationProvenance,ArchitectureInvarianceProfile)
class W:
 def execute(self,state,action_id): raise NotImplementedError
def rt():
 r=PVPPRegistry(); r.register_domain(DomainDefinition('d',0,0,1,1)); r.register_action(ActionDefinition('steady',('d',),{},{})); return PVPPRuntime(r,W())
def a(i,role,v='1'): return AdapterIdentity(i,role,v,(f'src:{i}',))
ROLES=('state_measurement','action_structure','projection_world_model','constraint_evidence','execution_transition')
def cfg(i,prefix='a'):
 return RuntimeConfigurationProvenance(i,'PV-PP V2','0.129',1,tuple(a(prefix+str(n),r) for n,r in enumerate(ROLES)),(f'source:{i}',))
def prof(): return ArchitectureInvarianceProfile('p',('PPP','Phi','H','G','R','Graph/Seed','Pi','Pi Completeness','Constraints','Domain Framing','Adequacy','Sigma'),ROLES)
def test_two_different_adapter_sets_preserve_profile():
 x=rt().assess_architecture_adaptation_invariance(prof(),(cfg('econ','e'),cfg('agent','s'))); assert x.valid and x.configuration_ids==('econ','agent')
def test_adapter_versions_may_differ():
 c=cfg('x','x'); ys=tuple(AdapterIdentity(z.adapter_id,z.adapter_role,'99',z.provenance_ids) for z in c.adapter_identities); c2=RuntimeConfigurationProvenance('y','PV-PP V2','0.129',2,ys,('source:y',)); assert rt().assess_architecture_adaptation_invariance(prof(),(c,c2)).valid
def test_requires_cross_domain_pair(): assert not rt().assess_architecture_adaptation_invariance(prof(),(cfg('one'),)).valid
def test_rejects_duplicate_configuration_identity(): assert not rt().assess_architecture_adaptation_invariance(prof(),(cfg('same','a'),cfg('same','b'))).valid
def test_rejects_missing_required_adapter_role():
 c=cfg('bad'); c=RuntimeConfigurationProvenance(c.configuration_id,c.framework_version,c.runtime_version,c.created_at,c.adapter_identities[:-1],c.source_ids); x=rt().assess_architecture_adaptation_invariance(prof(),(cfg('ok'),c)); assert not x.valid and any('missing required' in v for v in x.violations)
def test_rejects_invalid_configuration():
 c=RuntimeConfigurationProvenance('bad','PV-PP V2','0.129',1,(a('x','selector'),),('s',)); assert not rt().assess_architecture_adaptation_invariance(prof(),(cfg('ok'),c)).valid
def test_rejects_duplicate_canonical_stage_identity():
 p=ArchitectureInvarianceProfile('p',('G','G'),ROLES); assert not rt().assess_architecture_adaptation_invariance(p,(cfg('a'),cfg('b','b'))).valid
def test_instrumentation_grants_no_authority():
 x=rt().assess_architecture_adaptation_invariance(prof(),(cfg('a'),cfg('b','b'))); assert x.valid and not hasattr(x,'selection') and not hasattr(x,'execution_license') and 'confers no canonical operator or execution authority' in x.notes[1]
