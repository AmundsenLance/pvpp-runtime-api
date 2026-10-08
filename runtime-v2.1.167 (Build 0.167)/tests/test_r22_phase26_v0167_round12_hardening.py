from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import threading

import pytest

from pvpp_runtime import ExecutionObservation
from pvpp_runtime.supervision.continuation import ObservationIdentityConflict
from pvpp_runtime.supervision.observation_value import (
    ObservationValidationError,
    canonical_execution_observation_payload,
)
from test_r22_phase6_control import prepared


class ShiftingMapping(Mapping):
    """One-key mapping whose value changes on every materialization read."""
    def __init__(self):
        self.reads = 0
    def __iter__(self):
        return iter(("level",))
    def __len__(self):
        return 1
    def __getitem__(self, key):
        if key != "level":
            raise KeyError(key)
        self.reads += 1
        return self.reads


def _commit_digest(store, aeid, event_id):
    row = store._conn.execute(
        "SELECT observation_digest FROM continuation_observation_commits WHERE active_execution_id=? AND event_id=?",
        (aeid, event_id),
    ).fetchone()
    assert row is not None
    return row["observation_digest"]


def _digest_plain(observation: ExecutionObservation) -> str:
    payload = canonical_execution_observation_payload(observation)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8", "strict")
    return hashlib.sha256(raw).hexdigest()


def _intent_count(store, aeid):
    return store._conn.execute(
        "SELECT count(*) FROM continuation_intents WHERE active_execution_id=?",
        (aeid,),
    ).fetchone()[0]


def test_v0167_01_shifting_mapping_runtime_content_matches_committed_digest(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg = prepared(tmp_path)
    live = ShiftingMapping()
    original = ExecutionObservation("shift", staged=True, information=live)
    first = cont.checkpoint(
        active_execution_id=rec.active_execution_id,
        observation=original,
        checkpoint_at="2026-10-02T23:00:00+00:00",
    )
    episode = bridge.current_episode(rec.episode_id)
    assert episode.trace_tail is not None
    trace_info = dict(episode.trace_tail.information)
    # The runtime-consumed content must be exactly the content described by the
    # committed observation identity, regardless of how often the caller object
    # would change if read again.
    expected = _digest_plain(ExecutionObservation("shift", staged=True, information=trace_info))
    assert _commit_digest(store, rec.active_execution_id, "shift") == expected
    assert live.reads == 1
    step = bridge.episode_step(rec.episode_id)
    # Replaying the still-live shifting object snapshots its now-different content
    # and therefore conflicts with the committed identity instead of silently
    # returning the historical assessment.
    with pytest.raises(ObservationIdentityConflict, match="event_id reused with changed content"):
        cont.checkpoint(
            active_execution_id=rec.active_execution_id,
            observation=original,
            checkpoint_at="2026-10-02T23:00:01+00:00",
        )
    assert bridge.episode_step(rec.episode_id) == step
    assert first.continuation_posture == "continue"


def test_v0167_02_plain_dict_mutation_after_snapshot_does_not_change_runtime_input(tmp_path, monkeypatch):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg = prepared(tmp_path)
    live_information = {"level": 1}
    original = ExecutionObservation("threaded-live", staged=True, information=live_information)
    captured = threading.Event()
    release = threading.Event()
    real_authorize = bridge.authorize_supervised_advance

    def gated_authorize(*args, **kwargs):
        result = real_authorize(*args, **kwargs)
        captured.set()
        assert release.wait(5)
        return result

    monkeypatch.setattr(bridge, "authorize_supervised_advance", gated_authorize)
    out = []
    err = []

    def run_checkpoint():
        try:
            out.append(cont.checkpoint(
                active_execution_id=rec.active_execution_id,
                observation=original,
                checkpoint_at="2026-10-02T23:05:00+00:00",
            ))
        except Exception as exc:  # pragma: no cover - asserted below
            err.append(exc)

    thread = threading.Thread(target=run_checkpoint)
    thread.start()
    assert captured.wait(5)
    live_information["level"] = 999
    release.set()
    thread.join(5)
    assert not thread.is_alive()
    assert not err and out
    episode = bridge.current_episode(rec.episode_id)
    assert episode.trace_tail is not None
    assert dict(episode.trace_tail.information) == {"level": 1}
    expected = _digest_plain(ExecutionObservation("threaded-live", staged=True, information={"level": 1}))
    assert _commit_digest(store, rec.active_execution_id, "threaded-live") == expected


def _deep_value(depth=5000):
    value = "leaf"
    for _ in range(depth):
        value = [value]
    return value


@pytest.mark.parametrize(
    "value,pattern",
    [
        pytest.param(_deep_value(), "nesting depth", id="deep"),
        pytest.param(None, "cyclic value", id="cycle"),
        pytest.param(10 ** 5000, None, id="huge-int"),
    ],
)
def test_v0167_03_pathological_values_are_typed_validation_errors(tmp_path, value, pattern):
    if value is None:
        value = []
        value.append(value)
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg = prepared(tmp_path)
    before = _intent_count(store, rec.active_execution_id)
    step = bridge.episode_step(rec.episode_id)
    with pytest.raises(ObservationValidationError, match=pattern) if pattern is not None else pytest.raises(ObservationValidationError):
        cont.checkpoint(
            active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation("pathological", staged=True, information={"v": value}),
            checkpoint_at="2026-10-02T23:10:00+00:00",
        )
    assert _intent_count(store, rec.active_execution_id) == before
    assert bridge.episode_step(rec.episode_id) == step
    assert not bridge.episode_is_indeterminate(rec.episode_id)
    good = cont.checkpoint(
        active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation("pathological-good", staged=True, information={"v": 1}),
        checkpoint_at="2026-10-02T23:10:01+00:00",
    )
    assert good.continuation_posture == "continue"
    assert bridge.episode_step(rec.episode_id) == step + 1
