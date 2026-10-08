from r22_trust_fixture import trusted_store, proof, register_source as register_test_source
from datetime import datetime, timezone

import pytest

from pvpp_runtime.supervision import AuditEvent, ConcurrencyConflict, SemanticId, SQLiteSupervisoryStore


def now():
    return datetime.now(timezone.utc).isoformat()


def test_semantic_id_is_stable_value_and_non_authorizing_shape():
    a = SemanticId.new("obs")
    b = SemanticId.new("obs")
    assert a.value.startswith("obs_")
    assert a != b


def test_configuration_is_durable_across_reopen(tmp_path):
    db = tmp_path / "supervisor.db"
    with trusted_store(db) as store:
        created = store.create_configuration("cfg-A", {"mode": "test"}, updated_at=now())
        assert created.version == 1
    with trusted_store(db) as store:
        loaded = store.get_configuration("cfg-A")
        assert loaded is not None
        assert loaded.version == 1
        assert loaded.payload == {"mode": "test"}


def test_configuration_cas_advances_version_and_rejects_stale_write(tmp_path):
    db = tmp_path / "supervisor.db"
    with trusted_store(db) as store:
        store.create_configuration("cfg-A", {"n": 1}, updated_at=now())
        current = store.compare_and_swap_configuration(
            "cfg-A", expected_version=1, payload={"n": 2}, updated_at=now()
        )
        assert current.version == 2
        with pytest.raises(ConcurrencyConflict):
            store.compare_and_swap_configuration(
                "cfg-A", expected_version=1, payload={"n": 3}, updated_at=now()
            )
        assert store.get_configuration("cfg-A").payload == {"n": 2}


def test_audit_is_append_only_and_deduplicates_semantic_event_id(tmp_path):
    db = tmp_path / "supervisor.db"
    event = AuditEvent.create(
        "configuration_created", configuration_id="cfg-A", payload={"version": 1}, event_id="evt-fixed"
    )
    with trusted_store(db) as store:
        seq = store.append_audit_event(event)
        assert seq == 1
        with pytest.raises(ConcurrencyConflict):
            store.append_audit_event(event)
        events = store.audit_events(configuration_id="cfg-A")
        assert events == [event]


def test_create_configuration_is_fail_closed_on_duplicate(tmp_path):
    db = tmp_path / "supervisor.db"
    with trusted_store(db) as store:
        store.create_configuration("cfg-A", {}, updated_at=now())
        with pytest.raises(ConcurrencyConflict):
            store.create_configuration("cfg-A", {"replacement": True}, updated_at=now())
