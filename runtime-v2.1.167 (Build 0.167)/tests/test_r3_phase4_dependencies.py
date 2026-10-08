from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
from pvpp_runtime.supervision.dependency import *
from pvpp_runtime.supervision.store import SQLiteSupervisoryStore, ConcurrencyConflict
from pvpp_runtime.supervision.models import CanonicalExecutionHandle
from pvpp_runtime.supervision.observation import *
import pytest

def setup(tmp_path,n=1):
 s=trusted_store(tmp_path/'x.db'); ds=DependencyService(s); os=ObservationService(s); aids=[]
 for i in range(n):
  h=CanonicalExecutionHandle(f'h{i}',f'ep{i}',i+1,'p','a','cy','cfg',1,'b','1',f'au{i}','current','t')
  aids.append(s._register_resolved_active_execution(h,execution_id=f'ex{i}',registered_at='2026-10-02T10:00:00+00:00').active_execution_id)
 return s,ds,os,aids

def fact(os,val='up',eff='2026-10-02T10:00:00'):
 r=SourceRegistration('sr','src',('observation',),('reachability',),('sub',),('cfg',),('governance',),'x',None,None,'current','admin',1); register_test_source(os, r)
 o=ExternalObservation('o','src','reachability','net','sub','cfg',val,None,eff,eff,eff,{}); os.submit_observation(o); a=os.assess_observation(o,assessed_at=eff); return o,a,os.commit_admission_change(o,a,committed_at=eff)

def test_descriptor_runtime_owned_and_alias_normalized(tmp_path):
 s,d,o,a=setup(tmp_path); fact(o); b=d.register_dependency_binding(active_execution_id=a[0],configuration_id='cfg',fact_kind=' Reachability ',fact_id='net',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00'); x=d.derive_dependency_set(a[0],derived_at='2026-10-02T10:00:00+00:00'); assert x.canonical_fact_identities==(('sub','reachability','net'),)
def test_unauthorized_retirement_rejected(tmp_path):
 s,d,o,a=setup(tmp_path); b=d.register_dependency_binding(active_execution_id=a[0],configuration_id='cfg',subject_id='sub',fact_kind='f',fact_id='x',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00');
 with pytest.raises(PermissionError): d.retire_dependency_binding(b.binding_id,registration_authority='caller',retired_at='2026-10-02T10:00:00+00:00')
def test_binding_change_stales_snapshot(tmp_path):
 s,d,o,a=setup(tmp_path); fact(o); d.register_dependency_binding(active_execution_id=a[0],configuration_id='cfg',fact_kind='reachability',fact_id='net',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00'); snap=d.capture_governance_snapshot(a[0],created_at='2026-10-02T10:00:00+00:00'); d.register_dependency_binding(active_execution_id=a[0],configuration_id='cfg',subject_id='sub',fact_kind='other',fact_id='z',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00');
 with pytest.raises(ConcurrencyConflict): d.validate_snapshot(snap)
def test_material_fact_change_stales_snapshot(tmp_path):
 s,d,o,a=setup(tmp_path); fact(o); d.register_dependency_binding(active_execution_id=a[0],configuration_id='cfg',fact_kind='reachability',fact_id='net',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00'); snap=d.capture_governance_snapshot(a[0],created_at='2026-10-02T10:00:00+00:00'); oo=ExternalObservation('o2','src','reachability','net','sub','cfg','down',None,'2026-10-02T11:00:00','x','x',{}); o.submit_observation(oo); aa=o.assess_observation(oo,assessed_at='2026-10-02T10:00:00+00:00'); o.commit_admission_change(oo,aa,committed_at='2026-10-02T10:00:00+00:00');
 with pytest.raises(ConcurrencyConflict): d.validate_snapshot(snap)
def test_shared_fact_fans_out(tmp_path):
 s,d,o,a=setup(tmp_path,2); _,_,ch=fact(o)
 for x in a:d.register_dependency_binding(active_execution_id=x,configuration_id='cfg',fact_kind='reachability',fact_id='net',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00')
 assert set(d.resolve_affected_executions(ch,configuration_id='cfg'))==set(a)
def test_cross_configuration_binding_rejected(tmp_path):
 s,d,o,a=setup(tmp_path)
 with pytest.raises(ValueError): d.register_dependency_binding(active_execution_id=a[0],configuration_id='other',fact_kind='f',fact_id='x',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00')
def test_snapshot_valid_when_unchanged(tmp_path):
 s,d,o,a=setup(tmp_path); fact(o); d.register_dependency_binding(active_execution_id=a[0],configuration_id='cfg',fact_kind='reachability',fact_id='net',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00'); assert d.validate_snapshot(d.capture_governance_snapshot(a[0],created_at='2026-10-02T10:00:00+00:00'))
def test_missing_material_fact_blocks_snapshot(tmp_path):
 s,d,o,a=setup(tmp_path); d.register_dependency_binding(active_execution_id=a[0],configuration_id='cfg',subject_id='sub',fact_kind='f',fact_id='missing',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00')
 with pytest.raises(ValueError): d.capture_governance_snapshot(a[0],created_at='2026-10-02T10:00:00+00:00')
