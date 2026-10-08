from __future__ import annotations

import math
import pytest

from pvpp_runtime import ExecutionObservation
import pvpp_runtime.supervision as supervision
from pvpp_runtime.supervision.continuation import ObservationIdentityConflict
from test_r22_phase6_control import prepared

ObservationValidationError = getattr(supervision, 'ObservationValidationError', ValueError)


class Reading:
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return 'Reading(...)'


class Plain:
    def __init__(self, value):
        self.value = value
    def __eq__(self, other):
        return isinstance(other, Plain) and self.value == other.value


def _intent_count(store, aeid):
    return store._conn.execute(
        'SELECT count(*) FROM continuation_intents WHERE active_execution_id=?',
        (aeid,),
    ).fetchone()[0]


@pytest.mark.parametrize('value', [Reading(10), Plain(1)])
def test_v0166_01_arbitrary_objects_rejected_before_intent(tmp_path, value):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    step=bridge.episode_step(rec.episode_id); before=_intent_count(store,rec.active_execution_id)
    with pytest.raises(ObservationValidationError, match='unsupported value type'):
        cont.checkpoint(
            active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('obj-bad',staged=True,information={'sensor':value}),
            checkpoint_at='2026-10-02T22:00:00+00:00',
        )
    assert bridge.episode_step(rec.episode_id)==step
    assert _intent_count(store,rec.active_execution_id)==before
    assert not bridge.episode_is_indeterminate(rec.episode_id)
    ok=cont.checkpoint(
        active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation('obj-good',staged=True,information={'sensor':10}),
        checkpoint_at='2026-10-02T22:00:01+00:00',
    )
    assert ok.continuation_posture=='continue'
    assert bridge.episode_step(rec.episode_id)==step+1


def test_v0166_02_nested_plain_data_nan_inf_identity_is_stable(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    payload={
        'nested':[None,True,7,1.25,{'tuple':('x',float('nan'),float('inf'),float('-inf'))}],
        'text':'ok',
    }
    first=cont.checkpoint(
        active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation('nested',staged=True,information=payload,realized_pv_bundle={'pv':[1,2,3]}),
        checkpoint_at='2026-10-02T22:05:00+00:00',
    )
    step=bridge.episode_step(rec.episode_id)
    replay=cont.checkpoint(
        active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation(
            'nested',staged=True,
            information={'nested':[None,True,7,1.25,{'tuple':('x',float('nan'),float('inf'),float('-inf'))}],'text':'ok'},
            realized_pv_bundle={'pv':[1,2,3]},
        ),
        checkpoint_at='2026-10-02T22:05:01+00:00',
    )
    assert replay.assessment_id==first.assessment_id
    assert bridge.episode_step(rec.episode_id)==step


def test_v0166_03_mapping_keys_must_be_str(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    before=_intent_count(store,rec.active_execution_id)
    with pytest.raises(ObservationValidationError, match='mapping keys must be str'):
        cont.checkpoint(
            active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('bad-key',staged=True,information={1:'x'}),
            checkpoint_at='2026-10-02T22:10:00+00:00',
        )
    assert _intent_count(store,rec.active_execution_id)==before
    assert bridge.episode_step(rec.episode_id)==0


def test_v0166_04_lone_surrogate_event_id_is_typed_validation_error(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    before=_intent_count(store,rec.active_execution_id)
    with pytest.raises(ObservationValidationError, match='valid Unicode'):
        cont.checkpoint(
            active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('e\ud800',staged=True),
            checkpoint_at='2026-10-02T22:15:00+00:00',
        )
    assert _intent_count(store,rec.active_execution_id)==before
    assert bridge.episode_step(rec.episode_id)==0
    assert not bridge.episode_is_indeterminate(rec.episode_id)
    cont.checkpoint(
        active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation('unicode-good',staged=True),
        checkpoint_at='2026-10-02T22:15:01+00:00',
    )
    assert bridge.episode_step(rec.episode_id)==1


def test_v0166_05_numeric_identity_is_type_strict(tmp_path):
    rt,bridge,store,obs,dep,cont,ctl,rec,own,assessment,reg=prepared(tmp_path)
    cont.checkpoint(
        active_execution_id=rec.active_execution_id,
        observation=ExecutionObservation('typed-num',staged=True,information={'v':1}),
        checkpoint_at='2026-10-02T22:20:00+00:00',
    )
    step=bridge.episode_step(rec.episode_id)
    with pytest.raises(ObservationIdentityConflict, match='event_id reused with changed content'):
        cont.checkpoint(
            active_execution_id=rec.active_execution_id,
            observation=ExecutionObservation('typed-num',staged=True,information={'v':1.0}),
            checkpoint_at='2026-10-02T22:20:01+00:00',
        )
    assert bridge.episode_step(rec.episode_id)==step
