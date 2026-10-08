from pvpp_runtime import CapabilityChangeObservation, project_capability_trajectory


def obs(i,t,kind,prior,current,**kw):
    d=dict(observation_id=f"capobs:{i}", entity_id="agent:1", capability_id="cap:tool-use",
           observed_at=t, change_kind=kind, prior_snapshot_id=prior, current_snapshot_id=current,
           source_id=f"monitor:{i}", provenance_id=f"prov:{i}", confidence=.9,
           evidence_ids=(f"ev:{i}",), configuration_ids=("cfg:1",))
    d.update(kw); return CapabilityChangeObservation(**d)


def chain():
    return (obs(1,10,"increased","s1","s2"), obs(2,20,"reconfigured","s2","s3"))


def test_valid_trajectory_preserves_order_and_non_scalar_snapshots():
    a=project_capability_trajectory("traj:1",chain())
    assert a.valid and a.trajectory.observation_ids==("capobs:1","capobs:2")
    assert a.trajectory.snapshot_chain==("s1","s2","s3")


def test_mixed_entity_or_capability_rejected():
    assert not project_capability_trajectory("t",chain()+(obs(3,30,"increased","s3","s4",entity_id="agent:2"),)).valid
    assert not project_capability_trajectory("t",chain()+(obs(3,30,"increased","s3","s4",capability_id="cap:other"),)).valid


def test_temporal_order_must_be_strict_and_explicit():
    assert not project_capability_trajectory("t",tuple(reversed(chain()))).valid
    assert not project_capability_trajectory("t",(obs(1,10,"increased","s1","s2"),obs(2,10,"increased","s2","s3"))).valid


def test_snapshot_discontinuity_fails_closed():
    a=project_capability_trajectory("t",(obs(1,10,"increased","s1","s2"),obs(2,20,"increased","WRONG","s3")))
    assert not a.valid and any("discontinuity" in x for x in a.violations)


def test_uncertain_observation_is_preserved_without_inventing_snapshot():
    xs=(obs(1,10,"increased","s1","s2"),obs(2,15,"uncertain",None,None),obs(3,20,"increased","s2","s3"))
    a=project_capability_trajectory("t",xs)
    assert a.valid and a.trajectory.uncertain_observation_ids==("capobs:2",)
    assert a.trajectory.snapshot_chain==("s1","s2","s3")


def test_as_of_blocks_future_observation():
    assert not project_capability_trajectory("t",chain(),as_of=15).valid


def test_invalid_component_observation_rejected():
    xs=(obs(1,10,"increased","s1","s2"),obs(2,20,"increased","s2","s2"))
    a=project_capability_trajectory("t",xs)
    assert not a.valid and any("invalid capability-change observation" in x for x in a.violations)


def test_trajectory_creates_no_graph_pi_or_execution_authority():
    a=project_capability_trajectory("t",chain())
    assert a.valid
    for name in ("graph_substrate_identity","pi","reentry","execution_result"):
        assert not hasattr(a.trajectory,name)
