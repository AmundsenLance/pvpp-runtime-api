from pvpp_runtime import (
    GovernanceArtifactDependency, ObjectiveLifecycleChange,
    derive_objective_lifecycle_invalidations, plan_governance_reentry,
)


def ch(**kw):
    d=dict(change_id='oc1', actor_id='a', prior_objective_set_id='os', prior_objective_set_version='1',
           current_objective_set_id='os', current_objective_set_version='2', changed_objective_ids=('o1',),
           reason='objective completed')
    d.update(kw); return ObjectiveLifecycleChange(**d)

def dep(i, stage, facts):
    return GovernanceArtifactDependency(i, 'art-'+i, stage, 'objective', tuple(facts))


def test_objective_only_change_preserves_viability_prefix():
    a=derive_objective_lifecycle_invalidations((), ch())
    assert a.valid and a.preserved_stage_ids == ('PPP','Phi','H','G','R')
    assert not a.reentry.return_to_governance

def test_changed_objective_identity_matches_explicit_dependency():
    a=derive_objective_lifecycle_invalidations((dep('d','Graph/Seed',('objective:o1',)),), ch())
    assert a.valid and a.matched_dependency_ids == ('d',)
    assert a.reentry.recompute_from_stage == 'Graph/Seed'

def test_set_version_dependency_can_invalidate():
    facts=('objective_set:os:1',)
    a=derive_objective_lifecycle_invalidations((dep('d','Pi',facts),), ch())
    assert a.reentry.recompute_from_stage == 'Pi'

def test_unrelated_objective_dependency_does_not_invalidate():
    a=derive_objective_lifecycle_invalidations((dep('d','Graph/Seed',('objective:o2',)),), ch())
    assert a.valid and not a.matched_dependency_ids and a.reentry.recompute_from_stage is None

def test_no_automatic_phi_invalidation():
    a=derive_objective_lifecycle_invalidations((), ch())
    assert 'Phi' not in a.reentry.invalidated_stages

def test_no_automatic_h_invalidation():
    assert 'H' not in derive_objective_lifecycle_invalidations((), ch()).reentry.invalidated_stages

def test_no_automatic_g_invalidation():
    assert 'G' not in derive_objective_lifecycle_invalidations((), ch()).reentry.invalidated_stages

def test_explicit_objective_dependency_is_not_hidden_utility():
    a=derive_objective_lifecycle_invalidations((dep('d','Pi',('objective:o1',)),), ch())
    assert a.reentry.recompute_from_stage == 'Pi'
    assert not hasattr(a, 'utility') and not hasattr(a, 'rank') and not hasattr(a, 'selected_policy_id')

def test_downstream_scope_begins_at_matched_stage():
    a=derive_objective_lifecycle_invalidations((dep('d','Pi',('objective:o1',)),), ch())
    p=plan_governance_reentry(a.reentry, a.invalidation_signals)
    assert p.valid and p.recompute_from_stage == 'Pi'
    assert p.reusable_upstream_stages[:5] == ('PPP','Phi','H','G','R')

def test_multiple_dependencies_choose_earliest_explicit_match():
    ds=(dep('d1','Pi',('objective:o1',)),dep('d2','Graph/Seed',('objective:o1',)))
    a=derive_objective_lifecycle_invalidations(ds,ch())
    assert a.reentry.recompute_from_stage == 'Graph/Seed'

def test_nonobjective_dependency_kind_does_not_match():
    d=GovernanceArtifactDependency('d','art','Graph/Seed','state',('objective:o1',))
    a=derive_objective_lifecycle_invalidations((d,),ch())
    assert not a.matched_dependency_ids

def test_actual_state_change_must_use_independent_path():
    a=derive_objective_lifecycle_invalidations((),ch(actual_state_changed=True))
    assert not a.valid and any('ordinary dependency' in v for v in a.violations)

def test_perceived_state_change_must_use_independent_path():
    a=derive_objective_lifecycle_invalidations((),ch(perceived_state_changed=True))
    assert not a.valid

def test_same_set_identity_and_version_is_not_lifecycle_change():
    a=derive_objective_lifecycle_invalidations((),ch(current_objective_set_version='1'))
    assert not a.valid

def test_changed_objective_ids_required():
    a=derive_objective_lifecycle_invalidations((),ch(changed_objective_ids=()))
    assert not a.valid

def test_changed_objective_ids_unique():
    a=derive_objective_lifecycle_invalidations((),ch(changed_objective_ids=('o1','o1')))
    assert not a.valid

def test_historical_objective_retention_does_not_reactivate_without_dependency():
    a=derive_objective_lifecycle_invalidations((),ch(reason='abandoned objective retained in memory'))
    assert a.valid and not a.invalidation_signals

def test_objective_change_does_not_create_execution_authority():
    a=derive_objective_lifecycle_invalidations((dep('d','epsilon',('objective:o1',)),),ch())
    assert a.valid and a.reentry.recompute_from_stage == 'epsilon'
    assert not hasattr(a,'authorized') and not hasattr(a,'execution_license')
