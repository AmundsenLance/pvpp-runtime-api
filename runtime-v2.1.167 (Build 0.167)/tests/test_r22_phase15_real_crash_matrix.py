"""Runtime 2.2 v0.156: real child-process death across durable supervisory boundaries.

Each case performs the consequential writes in a spawned child and terminates with
os._exit(), deliberately bypassing store.close(), Python finalizers, and pytest
fixture teardown.  The parent then opens the same SQLite store and verifies only
what was durably committed before death.
"""
from __future__ import annotations
from r22_trust_fixture import trusted_store, proof, register_source as register_test_source

import json
import multiprocessing as mp
import os
from pathlib import Path

import pytest

from pvpp_runtime.supervision import SQLiteSupervisoryStore
from pvpp_runtime.supervision.observation import ObservationService, ExternalObservation
from pvpp_runtime.supervision.effect import EffectService
from test_r22_phase6_control import setup, prepared
from test_r22_phase7_effect import setup7, terminalize
from test_r22_phase8_recovery import prep


def _new_observation():
    return ExternalObservation(
        'real-crash-new','src','reachability','net','sub','cfg','down',None,
        '2026-10-02T13:00:00+00:00','2026-10-02T13:00:00+00:00',
        '2026-10-02T13:00:00+00:00',{}
    )


def _die_at_stage(root_text: str, stage: str) -> None:
    root=Path(root_text)
    try:
        if stage in {'before_admission','after_admission'}:
            _rt,_bridge,store,obs,_dep,_cont,_rec=setup(root)
            o=_new_observation(); obs.submit_observation(o); adm=obs.assess_observation(o,assessed_at=o.received_at)
            if stage=='after_admission': obs.commit_admission_change(o,adm,committed_at='2026-10-02T10:00:00+00:00')

        elif stage in {'assessment','control_request','dispatch','ack','owner_transfer'}:
            _rt,_bridge,store,_obs,_dep,_cont,ctl,rec,own,assessment,reg=prepared(root)
            if stage=='owner_transfer':
                ctl.acquire_ownership(active_execution_id=rec.active_execution_id,owner_id='owner-B',acquired_at='2026-10-02T10:00:00+00:00')
            elif stage!='assessment':
                req=ctl.issue_control_request(
                    assessment_id=assessment.assessment_id,active_execution_id=rec.active_execution_id,
                    owner_id=own.owner_id,owner_fence=own.owner_fence,requested_control='cancel',
                    target_handle='job:1',created_at='2026-10-02T10:00:00+00:00')
                if stage in {'dispatch','ack'}:
                    attempt=ctl.dispatch_control_request(
                        control_request_id=req.control_request_id,adapter_registration_id=reg.adapter_registration_id,
                        owner_id=own.owner_id,owner_fence=own.owner_fence,target_handle='job:1',
                        control_region_at_request='cancelable',capability_evidence_ref='cap',
                        mapping_identity='cancel=cancel',dispatched_at='2026-10-02T10:00:00+00:00')
                    if stage=='ack':
                        ctl.record_enforcement_outcome(
                            control_attempt_id=attempt.control_attempt_id,outcome='completed',
                            attestation_evidence='signed:controller',controller_evidence_ref='ack',
                            observed_control_region='stopped',recorded_at='2026-10-02T10:00:00+00:00')

        elif stage in {'effect','finality','layer1'}:
            _rt,store,_obs,ctl,rec,eff=setup7(root)
            evidence=eff.submit_effect_evidence(
                active_execution_id=rec.active_execution_id,source_id='ledger',configuration_id='cfg',
                state='completed_effect',realized_bundle_ref='bundle',evidence_ref='world',
                provenance='signed',observed_at='2026-10-02T10:00:00+00:00',effective_at='2026-10-02T10:00:00+00:00',received_at='2026-10-02T10:00:00+00:00')
            state=eff.reconcile_effect(
                active_execution_id=rec.active_execution_id,effect_evidence_id=evidence.effect_evidence_id,
                updated_at='2026-10-02T10:00:00+00:00')
            if stage in {'finality','layer1'}:
                terminal=terminalize(ctl,rec,at='2026-10-02T10:40:00+00:00')
                finality=eff.accept_canonical_finality(
                    active_execution_id=rec.active_execution_id,
                    continuation_assessment_id=terminal.assessment_id,terminalized_at='2026-10-02T10:00:00+00:00')
                if stage=='layer1':
                    eff.record_layer1_transition(
                        active_execution_id=rec.active_execution_id,
                        effect_reconciliation_ref=state.effect_record_id,
                        prior_actual_state_ref='running',next_actual_state_ref='stopped',
                        transition_time='2026-10-02T10:00:00+00:00',evidence_ref='host',provenance='host',
                        configuration_id='cfg',authority_evidence='signed:layer1')

        elif stage=='recovery':
            store,_obs,_dep,_eff,svc,rec,_profile=prep(root,effect=True)
            svc.begin_recovery(active_execution_id=rec.active_execution_id,new_owner_id='B',started_at='2026-10-02T10:00:00+00:00')
        else:
            raise AssertionError(stage)
    except BaseException:
        import traceback, sys
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(90)
    os._exit(23)


def _row_count(store, table):
    return store._conn.execute(f'SELECT count(*) n FROM {table}').fetchone()['n']


def _verify_stage(root: Path, stage: str) -> None:
    store=trusted_store(root/'s.db')
    if stage=='before_admission':
        view=ObservationService(store).read_current_fact_view(
            configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net')
        assert view.value=='up'
    elif stage=='after_admission':
        view=ObservationService(store).read_current_fact_view(
            configuration_id='cfg',subject_id='sub',fact_kind='reachability',fact_id='net')
        assert view.value=='down' and _row_count(store,'admitted_fact_changes')>=2
    elif stage=='assessment':
        assert _row_count(store,'continuation_assessments')>=1
    elif stage=='control_request':
        assert _row_count(store,'control_requests')==1 and _row_count(store,'control_attempts')==0
    elif stage=='dispatch':
        assert _row_count(store,'control_attempts')==1 and _row_count(store,'enforcement_records')==0
    elif stage=='ack':
        # No EffectService existed in the child; initialize only the parent read schema,
        # then prove the controller acknowledgment did not manufacture effect evidence.
        EffectService(store,ObservationService(store))
        assert _row_count(store,'enforcement_records')==1 and _row_count(store,'effect_evidence')==0
    elif stage=='effect':
        row=store._conn.execute('SELECT payload FROM world_effect_state LIMIT 1').fetchone()
        assert row is not None and json.loads(row['payload'])['state']=='completed_effect'
    elif stage=='finality':
        assert _row_count(store,'canonical_finality')==1 and _row_count(store,'layer1_transitions')==0
    elif stage=='layer1':
        assert _row_count(store,'canonical_finality')==1 and _row_count(store,'layer1_transitions')==1
    elif stage=='recovery':
        row=store._conn.execute('SELECT payload FROM recovery_records LIMIT 1').fetchone()
        assert row is not None and json.loads(row['payload'])['recovery_state']=='recovering'
    elif stage=='owner_transfer':
        row=store._conn.execute('SELECT payload_json FROM supervisory_ownership LIMIT 1').fetchone()
        assert row is not None and json.loads(row['payload_json'])['owner_id']=='owner-B'
    else:
        raise AssertionError(stage)


@pytest.mark.parametrize('stage',(
    'before_admission','after_admission','assessment','control_request','dispatch','ack',
    'effect','finality','layer1','recovery','owner_transfer'))
def test_v0156_real_process_death_matrix(tmp_path, stage):
    root=tmp_path/stage; root.mkdir()
    ctx=mp.get_context('spawn')
    process=ctx.Process(target=_die_at_stage,args=(str(root),stage))
    process.start(); process.join(8)
    if process.is_alive():
        process.terminate(); process.join(2)
        raise AssertionError(f'child process hung at {stage}')
    assert process.exitcode==23, (stage,process.exitcode)
    _verify_stage(root,stage)
