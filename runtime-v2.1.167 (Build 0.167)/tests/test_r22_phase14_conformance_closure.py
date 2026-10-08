from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
"""Runtime 2.2 v0.155 Phase 14 — conformance closure."""
import json
from pathlib import Path
import pytest
from concurrent.futures import ThreadPoolExecutor
from pvpp_runtime import ExecutionObservation, ExecutionBindingIdentity
from pvpp_runtime.execution import ExecutionBindingRegistry
from pvpp_runtime.supervision.observation import ExternalObservation
from pvpp_runtime.supervision.simulation import SimulationObservationSource, SimulationEnforcementAdapter, SimulationEffectSource
from pvpp_runtime.supervision.operational import OperationalObservationAdapter, OperationalEnforcementAdapter, OperationalEffectAdapter, HostLayer1Authority
from pvpp_runtime.supervision.store import ConcurrencyConflict
from test_r22_phase6_control import setup, prepared
from test_r22_phase10_operational import pilot, changed_observation
from r22_real_cycle_fixture import license_from_real_cycle
from test_r22_phase15_strengthened_validation import behavioral_r3_checks


def _all_collected_test_ids():
    root=Path(__file__).resolve().parents[1]
    ids=set()
    for path in (root/'tests').glob('test_*.py'):
        text=path.read_text()
        for line in text.splitlines():
            if line.startswith('def test_'):
                name=line.split('def ',1)[1].split('(',1)[0]
                ids.add(f'tests/{path.name}::{name}')
    return ids


def test_phase14_r3_01_through_r3_24_manifest_is_complete_and_executable(tmp_path):
    root=Path(__file__).resolve().parents[1]
    data=json.loads((root/'R3_CONFORMANCE_v0_167.json').read_text())['requirements']
    assert set(data)=={f'R3-{i:02d}' for i in range(1,25)}
    collected=_all_collected_test_ids()
    for rid,row in data.items():
        assert row['surface'] and row['positive'] in collected and row['negative'] in collected, rid
    # v0.156 hardening: metadata resolvability is not treated as conformance proof.
    # Execute the behavioral R3 gate as part of this closure test.
    checks=behavioral_r3_checks(tmp_path)
    assert set(checks)==set(data)
    assert all(checks.values()), {k:v for k,v in checks.items() if not v}


def _second_execution(rt,bridge,store,dep):
    lic=license_from_real_cycle(rt); action_id=lic.action_ids[0]
    reg=ExecutionBindingRegistry(tuple(rt.registry.actions)); reg.register(ExecutionBindingIdentity('b2',action_id,'1'),lambda ctx:'ok')
    ep=bridge.instantiate_execution('ep2',lic,entry_sufficient=True,max_steps=5).episode
    auth=bridge.issue_native_execution_authorization(ep,action_id,reg,decision_cycle_id='cy2',configuration_id='cfg')
    h=bridge.resolve_canonical_execution(auth,configuration_id='cfg')
    rec=bridge.register_active_execution(store,h,execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id),registered_at='2026-10-02T10:00:00+00:00')
    dep.register_dependency_binding(active_execution_id=rec.active_execution_id,configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net',registration_authority='model',authority_proof=proof('model'),registered_at='2026-10-02T10:00:00+00:00')
    return rec


def _admit(obs, adapter, oid, value, effective):
    o=ExternalObservation(oid,'src','reachability','net','sub','cfg',value,None,effective,effective,effective,{})
    if isinstance(adapter, SimulationObservationSource): return adapter.inject(o,assessed_at=effective,committed_at=effective)
    return adapter.admit(o,assessed_at=effective,committed_at=effective)


def test_phase14_second_fact_change_during_shared_fanout(tmp_path):
    rt,bridge,store,obs,dep,cont,rec1=setup(tmp_path); rec2=_second_execution(rt,bridge,store,dep)
    sim=SimulationObservationSource(obs)
    _,ch1=_admit(obs,sim,'fan-1','degraded','2026-10-02T16:00:00')
    affected1=dep.resolve_affected_executions(ch1,configuration_id='cfg')
    assert set(affected1)=={rec1.active_execution_id,rec2.active_execution_id}
    stale1=dep.capture_governance_snapshot(rec1.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    stale2=dep.capture_governance_snapshot(rec2.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    # Second material change lands while the first affected-set is still being processed.
    _,ch2=_admit(obs,sim,'fan-2','down','2026-10-02T16:00:02')
    affected2=dep.resolve_affected_executions(ch2,configuration_id='cfg')
    assert set(affected2)==set(affected1)
    for rec,snap in ((rec1,stale1),(rec2,stale2)):
        with pytest.raises(ConcurrencyConflict):
            cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('stale'),assessed_at='2026-10-02T10:00:00+00:00')
    fresh1=dep.capture_governance_snapshot(rec1.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    fresh2=dep.capture_governance_snapshot(rec2.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1=pool.submit(cont.evaluate_continuation,active_execution_id=rec1.active_execution_id,snapshot=fresh1,observation=ExecutionObservation('ok'),assessed_at='2026-10-02T10:00:00+00:00')
        f2=pool.submit(cont.evaluate_continuation,active_execution_id=rec2.active_execution_id,snapshot=fresh2,observation=ExecutionObservation('stop',continuation_sufficient=False),assessed_at='2026-10-02T10:00:00+00:00')
        a1=f1.result(timeout=3); a2=f2.result(timeout=3)
    assert a1.continuation_posture=='continue' and a2.continuation_posture=='abort_return'


def _semantic_chain(tmp_path, simulated):
    tmp_path.mkdir(parents=True,exist_ok=True)
    rt,bridge,store,obs,dep,cont,ctl,rec,own,reg,eff=pilot(tmp_path)
    oa=SimulationObservationSource(obs) if simulated else OperationalObservationAdapter(obs)
    ca=SimulationEnforcementAdapter(ctl) if simulated else OperationalEnforcementAdapter(ctl)
    ea=SimulationEffectSource(eff) if simulated else OperationalEffectAdapter(eff)
    o=changed_observation()
    if simulated: admission,change=oa.inject(o,assessed_at='2026-10-02T10:00:00+00:00',committed_at='2026-10-02T10:00:00+00:00')
    else: admission,change=oa.admit(o,assessed_at='2026-10-02T10:00:00+00:00',committed_at='2026-10-02T10:00:00+00:00')
    dep.resolve_affected_executions(change,configuration_id='cfg')
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at='2026-10-02T10:00:00+00:00')
    a=cont.evaluate_continuation(active_execution_id=rec.active_execution_id,snapshot=snap,observation=ExecutionObservation('parity',continuation_sufficient=False),trigger_ids=(change.change_id,),assessed_at='2026-10-02T10:00:00+00:00')
    req=ctl.issue_control_request(assessment_id=a.assessment_id,active_execution_id=rec.active_execution_id,owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
    kwargs=dict(control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',control_region_at_request='cancelable',capability_evidence_ref='cap',mapping_identity='cancel=cancel',dispatched_at='2026-10-02T10:00:00+00:00')
    at=ca.dispatch(**kwargs) if simulated else ca.dispatch_exact(**kwargs)
    okw=dict(control_attempt_id=at.control_attempt_id,outcome='completed',attestation_evidence='signed:controller',controller_evidence_ref='ack',observed_control_region='stopped',recorded_at='2026-10-02T10:00:00+00:00')
    en=ca.outcome(**okw) if simulated else ca.report_outcome(**okw)
    ekw=dict(active_execution_id=rec.active_execution_id,source_id='world-ledger',configuration_id='cfg',state='completed_effect',realized_bundle_ref='world:stopped',evidence_ref='ledger',provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00',updated_at='2026-10-02T10:00:00+00:00',control_enforcement_refs=(en.enforcement_record_id,))
    evidence,state=ea.inject_and_reconcile(**ekw) if simulated else ea.admit_and_reconcile(**ekw)
    HostLayer1Authority(eff).commit(authority_evidence='signed:layer1',active_execution_id=rec.active_execution_id,effect_reconciliation_ref=state.effect_record_id,prior_actual_state_ref='running',next_actual_state_ref='stopped',transition_time='2026-10-02T10:00:00+00:00',evidence_ref='host',provenance='host',configuration_id='cfg')
    return store


def test_phase14_simulation_operational_parity(tmp_path):
    sim=_semantic_chain(tmp_path/'sim',True); op=_semantic_chain(tmp_path/'op',False)
    tables=('observations','observation_admissions','admitted_fact_changes','control_requests','control_attempts','enforcement_records','effect_evidence','world_effect_state','layer1_transitions')
    for table in tables:
        sn=sim._conn.execute(f'SELECT count(*) n FROM {table}').fetchone()['n']; on=op._conn.execute(f'SELECT count(*) n FROM {table}').fetchone()['n']
        assert sn==on and sn>0, table
    assert [e.event_kind for e in sim.audit_events(configuration_id='cfg')]==[e.event_kind for e in op.audit_events(configuration_id='cfg')]


def test_phase14_complete_causal_audit_trace(tmp_path):
    store=_semantic_chain(tmp_path/'audit',False)
    events=store.audit_events(configuration_id='cfg'); kinds=[e.event_kind for e in events]
    required=['observation_submitted','observation_assessed','fact_change_committed','dependency_fanout_resolved','continuation_assessed','control_requested','control_dispatched','enforcement_recorded','effect_evidence_admitted','effect_reconciled','layer1_transition_committed']
    pos=-1
    for kind in required:
        pos=kinds.index(kind,pos+1)
    bykind={e.event_kind:e for e in events}
    assert bykind['observation_submitted'].payload['initiating_event_id']=='op-change'
    assert bykind['fact_change_committed'].payload['state_version_after']>=1
    assert bykind['continuation_assessed'].payload['canonical_operation']=='epsilon/re-entry'
    assert bykind['continuation_assessed'].payload['canonical_result']
    assert bykind['control_requested'].payload['authority_source']
    assert bykind['effect_reconciled'].payload['terminal_effect_separation'] is True
    assert bykind['layer1_transition_committed'].payload['authority_source']=='host-trust-provider'
    assert all('invariant_status' in bykind[k].payload and 'error' in bykind[k].payload for k in required)
