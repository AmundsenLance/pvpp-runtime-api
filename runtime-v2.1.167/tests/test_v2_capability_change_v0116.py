import pytest
from pvpp_runtime import CapabilityChangeObservation, validate_capability_change_observation


def obs(**kw):
    d=dict(observation_id="capobs:1", entity_id="agent:1", capability_id="cap:tool-use",
           observed_at=12.0, change_kind="increased", prior_snapshot_id="snap:1",
           current_snapshot_id="snap:2", source_id="monitor:1", provenance_id="prov:1",
           confidence=.9, evidence_ids=("ev:1",), configuration_ids=("cfg:1",))
    d.update(kw); return CapabilityChangeObservation(**d)


def test_valid_definite_change_is_material_report_only():
    a=validate_capability_change_observation(obs())
    assert a.valid and a.material_change_reported and a.change_kind=="increased"


def test_reconfigured_requires_prior_snapshot():
    a=validate_capability_change_observation(obs(change_kind="reconfigured", prior_snapshot_id=None))
    assert not a.valid and any("prior_snapshot_id" in x for x in a.violations)


def test_definite_change_requires_current_snapshot():
    a=validate_capability_change_observation(obs(change_kind="lost", current_snapshot_id=None))
    assert not a.valid and any("current_snapshot_id" in x for x in a.violations)


def test_uncertain_change_does_not_become_material_change():
    a=validate_capability_change_observation(obs(change_kind="uncertain", prior_snapshot_id=None, current_snapshot_id=None))
    assert a.valid and not a.material_change_reported


def test_same_snapshot_cannot_prove_change():
    a=validate_capability_change_observation(obs(current_snapshot_id="snap:1"))
    assert not a.valid


def test_source_and_provenance_are_mandatory():
    assert not validate_capability_change_observation(obs(source_id="")).valid
    assert not validate_capability_change_observation(obs(provenance_id="")).valid


def test_confidence_and_evidence_identity_hygiene():
    assert not validate_capability_change_observation(obs(confidence=1.1)).valid
    assert not validate_capability_change_observation(obs(evidence_ids=("ev:1","ev:1"))).valid


def test_validation_creates_no_graph_or_execution_authority():
    a=validate_capability_change_observation(obs())
    assert a.valid
    assert not hasattr(a, "graph_substrate_identity")
    assert not hasattr(a, "reentry")
    assert not hasattr(a, "execution_result")
