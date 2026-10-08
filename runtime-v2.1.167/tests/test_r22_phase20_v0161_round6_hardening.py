from __future__ import annotations

import pytest

from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision.effect import EffectService
from pvpp_runtime.supervision.observation import ObservationService
from r22_trust_fixture import proof
from test_r22_phase6_control import prepared
from test_r3_phase2_canonical_bridge import setup as bridge_setup


def _latest_intent(store, active_execution_id):
    return store._conn.execute(
        "SELECT rowid AS intent_rowid,* FROM continuation_intents WHERE active_execution_id=? ORDER BY rowid DESC LIMIT 1",
        (active_execution_id,),
    ).fetchone()


@pytest.mark.parametrize(
    "checkpoint_at",
    [
        "2026-10-02T11:00:00+00:00",
        "2026-10-02T09:00:00+00:00",
        "2026-10-02T05:30:00-05:00",
        "2026-10-02T09:30:00Z",
        "2026-10-02T15:30:00+05:00",
    ],
)
def test_v0161_01_true_divergence_never_superseded_by_caller_timestamp(tmp_path, monkeypatch, checkpoint_at):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at=checkpoint_at)
    before=bridge.episode_step(rec.episode_id)
    real_persist=cont._persist
    monkeypatch.setattr(cont,"_persist",lambda a: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError,match="disk full"):
        cont.evaluate_continuation(
            active_execution_id=rec.active_execution_id,
            snapshot=snap,
            observation=ExecutionObservation("true-divergence"),
            assessed_at=checkpoint_at,
        )
    monkeypatch.setattr(cont,"_persist",real_persist)
    assert bridge.episode_step(rec.episode_id)==before+1
    row=_latest_intent(store,rec.active_execution_id)
    assert row["status"]=="reconciliation_required"
    result=cont.reconcile_continuation_divergence(
        active_execution_id=rec.active_execution_id,
        authority_id="admin",
        authority_proof=proof("admin"),
        reconciled_at="2026-10-02T12:00:00+00:00",
    )
    assert result["outcome"]=="terminally_fenced"
    assert _latest_intent(store,rec.active_execution_id)["status"]=="terminally_fenced"


def test_v0161_02_empty_event_id_is_prevalidated_without_indeterminate_state(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    before=bridge.episode_step(rec.episode_id)
    with pytest.raises(ValueError,match="execution observation event_id required"):
        cont.checkpoint(
            active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation(""),
            checkpoint_at="2026-10-02T12:10:00+00:00",
        )
    assert bridge.episode_step(rec.episode_id)==before
    assert not bridge.episode_is_indeterminate(rec.episode_id)
    residue=store._conn.execute(
        "SELECT status FROM continuation_intents WHERE active_execution_id=? AND status!='closed'",
        (rec.active_execution_id,),
    ).fetchall()
    assert residue==[]
    fresh=cont.checkpoint(
        active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation("valid-after-input-error"),
        checkpoint_at="2026-10-02T12:10:01+00:00",
    )
    assert fresh.canonical_step==before+1


def test_v0161_03_public_bridge_rebinding_cannot_forge_retry_authority(tmp_path):
    rt,bridge,bindings,ep,auth,store=bridge_setup(tmp_path)
    handle=bridge.resolve_canonical_execution(auth,configuration_id="cfg-A")
    rec=bridge.register_active_execution(
        store,
        handle,
        execution_id=rt.native_execution_authorization_execution_id(auth.authorization_id),
        registered_at="2026-10-02T12:20:00+00:00",
    )
    rt.invoke_authorized_native(auth,bindings,configuration_id="cfg-A")
    assert rt.native_execution_authorization_status(auth.authorization_id)=="consumed"

    class FakeBridge:
        def authorization_status(self, authorization_id):
            return "issued"

    with pytest.raises(PermissionError,match="private|trusted bridge registration|required"):
        store.bind_canonical_bridge(rec.active_execution_id,FakeBridge())
    eff=EffectService(store,ObservationService(store))
    with pytest.raises(ValueError,match="retry contract must be pre-execution"):
        eff.register_retry_contract(
            active_execution_id=rec.active_execution_id,
            idempotent=True,
            reconciliation_required=False,
            registered_at="2026-10-02T12:20:01+00:00",
        )


def test_v0161_04_abandoned_close_records_reconciliation_and_audit(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at="2026-10-02T12:30:00+00:00")
    original=bridge.authorize_supervised_advance
    monkeypatch.setattr(bridge,"authorize_supervised_advance",lambda *a,**k: (_ for _ in ()).throw(RuntimeError("transient")))
    with pytest.raises(RuntimeError,match="transient"):
        cont.evaluate_continuation(
            active_execution_id=rec.active_execution_id,
            snapshot=snap,
            observation=ExecutionObservation("transient"),
            assessed_at="2026-10-02T12:30:01+00:00",
        )
    monkeypatch.setattr(bridge,"authorize_supervised_advance",original)
    row=_latest_intent(store,rec.active_execution_id)
    assert row["status"]=="abandoned"
    with pytest.raises(ValueError,match="continuation_reconciliation_not_required"):
        cont.reconcile_continuation_divergence(
            active_execution_id=rec.active_execution_id,
            authority_id="admin",
            authority_proof=proof("admin"),
            reconciled_at="2026-10-02T12:30:02+00:00",
        )
    recrow=store._conn.execute(
        "SELECT outcome,payload FROM continuation_reconciliations WHERE active_execution_id=? ORDER BY rowid DESC LIMIT 1",
        (rec.active_execution_id,),
    ).fetchone()
    assert recrow is not None
    assert recrow["outcome"]=="not_required_abandoned_closed"
    events=[e for e in store.audit_events(configuration_id="cfg") if e.event_kind=="continuation_divergence_reconciled"]
    assert events
    assert events[-1].payload.get("outcome")=="not_required_abandoned_closed"


def test_v0161_05_later_persisted_assessment_supersedes_only_nondivergent_prepared_intent(tmp_path):
    from dataclasses import replace
    from pvpp_runtime.supervision.models import SemanticId

    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    snap=dep.capture_governance_snapshot(rec.active_execution_id,created_at="2026-10-02T12:40:00+00:00")
    episode=bridge.current_episode(rec.episode_id)
    intent_id=cont._prepare_intent(rec.active_execution_id,episode,snap,"2099-01-01T00:00:00+00:00")
    row=_latest_intent(store,rec.active_execution_id)
    assert row["intent_id"]==intent_id and row["status"]=="prepared"
    # Persist a later assessment using durable insertion order, deliberately with a
    # caller timestamp that sorts earlier. Timestamp ordering must not matter.
    later=replace(assessment,assessment_id=SemanticId.new("assess").value,assessed_at="2000-01-01T00:00:00+00:00")
    with store._lock:
        store._conn.execute("BEGIN IMMEDIATE")
        cont._persist(later)
        store._conn.execute("COMMIT")
    with pytest.raises(ValueError,match="continuation_reconciliation_not_required"):
        cont.reconcile_continuation_divergence(
            active_execution_id=rec.active_execution_id,
            authority_id="admin",
            authority_proof=proof("admin"),
            reconciled_at="2026-10-02T12:40:01+00:00",
        )
    recrow=store._conn.execute(
        "SELECT outcome FROM continuation_reconciliations WHERE intent_id=? ORDER BY rowid DESC LIMIT 1",
        (intent_id,),
    ).fetchone()
    assert recrow is not None and recrow["outcome"]=="not_required_superseded_closed"
