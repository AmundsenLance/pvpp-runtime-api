import pytest
from pvpp_runtime import (
    PVPPRegistry,PVPPRuntime,ActionDefinition,InformationTemporalProvenance,
    TransferHistoryEvent,TransferHistoryReference,TransferHistoryPackage,
    MemoryStateReference,ExpectationStateReference,ActualPersistentStateEnvelope,
)
class W: pass
def rt(service=None):
    r=PVPPRegistry(); r.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(r,W(),transfer_history_service=service)
def event(**kw):
    d=dict(event_id='e1',actor_id='a',participants=('a','b'),interaction_id='i1',sequence_index=1,
           transfer_type='partial',realized_pv={'money':5},revealed_pp_effect={'knowledge':'increased'},
           temporal_provenance=InformationTemporalProvenance(valid_time=10,record_or_knowledge_time=12))
    d.update(kw); return TransferHistoryEvent(**d)

def test_event_preserves_v2_1_event_fields_without_scalarization():
    e=event(); assert e.realized_pv=={'money':5} and e.revealed_pp_effect=={'knowledge':'increased'}
def test_event_requires_identity():
    assert 'event_id required' in ' '.join(rt().validate_transfer_history_event(event(event_id='')))
def test_event_actor_attribution_is_checked():
    assert rt().validate_transfer_history_event(event(),expected_actor_id='b')
def test_sequence_index_must_be_nonnegative_integer():
    assert rt().validate_transfer_history_event(event(sequence_index=-1))
def test_temporal_provenance_preserves_valid_vs_knowledge_time():
    e=event(); assert e.temporal_provenance.valid_time==10 and e.temporal_provenance.record_or_knowledge_time==12
def test_exact_time_is_not_mandatory_when_sequence_is_sufficient():
    e=event(temporal_provenance=None,sequence_index=3); assert rt().validate_transfer_history_event(e)==()
def test_transfer_history_is_not_memory():
    e=event(); m=MemoryStateReference('a','m1',12,{})
    assert not isinstance(e,MemoryStateReference) and m.payload=={}
def test_transfer_history_is_not_expectation():
    e=event(); k=ExpectationStateReference('a','k1',12,{})
    assert not isinstance(e,ExpectationStateReference)
def test_transfer_history_is_not_current_state_or_pp():
    e=event(); s=ActualPersistentStateEnvelope('a','s1',12,{}, {}, {}, {})
    assert not isinstance(e,ActualPersistentStateEnvelope) and s.state_id=='s1'
def test_package_requires_unique_event_ids():
    h=TransferHistoryReference('a','h2',12)
    p=TransferHistoryPackage('a',None,h,(event(),event()))
    assert not rt().validate_transfer_history_package(p,expected_actor_id='a').valid
def test_package_preserves_sequence_order():
    h=TransferHistoryReference('a','h2',12)
    p=TransferHistoryPackage('a',None,h,(event(event_id='e2',sequence_index=2),event(event_id='e1',sequence_index=1)))
    assert not rt().validate_transfer_history_package(p).valid
def test_package_time_cannot_move_backward():
    old=TransferHistoryReference('a','h1',12); new=TransferHistoryReference('a','h2',11)
    p=TransferHistoryPackage('a',old,new,(event(),))
    assert not rt().validate_transfer_history_package(p,prior_history=old).valid
def test_package_prior_identity_must_match_supplied_prior():
    old=TransferHistoryReference('a','h1',10); other=TransferHistoryReference('a','other',10); new=TransferHistoryReference('a','h2',12)
    p=TransferHistoryPackage('a',other,new,(event(),))
    assert not rt().validate_transfer_history_package(p,prior_history=old).valid
class Service:
    def record(self,prior,events):
        return TransferHistoryPackage(events[0].actor_id,prior,TransferHistoryReference(events[0].actor_id,'h2',12),events)
def test_host_owned_service_records_and_runtime_validates():
    p,a=rt(Service()).record_transfer_history(None,(event(),)); assert a.valid and p.next_history.transfer_history_id=='h2'
def test_no_service_means_no_runtime_owned_history_store():
    with pytest.raises(RuntimeError): rt().record_transfer_history(None,(event(),))
def test_empty_event_append_is_rejected():
    with pytest.raises(ValueError): rt(Service()).record_transfer_history(None,())
def test_history_record_does_not_mutate_event_into_memory_or_pp():
    p,a=rt(Service()).record_transfer_history(None,(event(),)); assert a.valid and p.events[0].memory_status is None
