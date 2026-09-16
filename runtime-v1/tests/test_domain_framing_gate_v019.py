import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'examples'/'tiny_crossing_policy_world'))

from pvpp_runtime import CandidatePolicySet, CandidatePolicySpace, DomainFrameTarget, DomainFrame
from run_crossing_choice import build_runtime, state

def space():
    return CandidatePolicySpace((
        CandidatePolicySet('food_policy',('favor_food',),policy_class_ids=('local',)),
        CandidatePolicySet('material_policy',('favor_material',),policy_class_ids=('shift',)),
    ),('local','shift'))

def valid_frame(order=('F','M')):
    return DomainFrame(tuple(DomainFrameTarget(d,f'{d}_viability_function') for d in order))

def test_explicit_complete_locked_frame_allows_adequacy_and_sigma():
    rt=build_runtime()
    a=rt.evaluate_framed_policy_space(state(),space(),valid_frame())
    assert a.pi_completeness.complete is True
    assert a.domain_framing.valid is True
    assert a.domain_framing.status == 'domain_framing_passed'
    assert a.status == 'crossing_governing_consequences_unresolved'
    assert len(a.evaluations) == 2

def test_missing_governing_target_blocks_adequacy():
    rt=build_runtime()
    a=rt.evaluate_framed_policy_space(state(),space(),DomainFrame((
        DomainFrameTarget('F','F_viability_function'),
    )))
    assert a.status == 'domain_framing_failed'
    assert a.domain_framing.missing_domain_ids == ('M',)
    assert a.evaluations == ()
    assert a.selected_policy_id is None

def test_unlocked_or_semantically_empty_target_blocks_adequacy():
    rt=build_runtime()
    frame=DomainFrame((
        DomainFrameTarget('F','F_viability_function'),
        DomainFrameTarget('M','',locked=False),
    ))
    a=rt.evaluate_framed_policy_space(state(),space(),frame)
    assert a.domain_framing.valid is False
    assert 'M' in a.domain_framing.invalid_target_domain_ids
    assert a.evaluations == ()

def test_duplicate_target_is_not_silently_resolved_by_order():
    rt=build_runtime()
    frame=DomainFrame((
        DomainFrameTarget('F','food_function'),
        DomainFrameTarget('F','other_food_function'),
        DomainFrameTarget('M','material_function'),
    ))
    a=rt.evaluate_framed_policy_space(state(),space(),frame)
    assert a.domain_framing.valid is False
    assert a.domain_framing.duplicate_domain_ids == ('F',)

def test_non_substitutable_mechanism_basis_is_explicitly_allowed_not_inferred():
    rt=build_runtime()
    frame=DomainFrame((
        DomainFrameTarget('F','food_mechanism','non_substitutable_mechanism'),
        DomainFrameTarget('M','material_function','function'),
    ))
    a=rt.evaluate_framed_policy_space(state(),space(),frame)
    assert a.domain_framing.valid is True

def test_frame_order_does_not_change_result():
    a=build_runtime().evaluate_framed_policy_space(state(),space(),valid_frame(('F','M')))
    b=build_runtime().evaluate_framed_policy_space(state(),space(),valid_frame(('M','F')))
    assert a.domain_framing.valid == b.domain_framing.valid == True
    assert a.status == b.status
    assert a.selected_policy_id == b.selected_policy_id is None

def test_pi_failure_precedes_domain_framing():
    rt=build_runtime()
    bad=CandidatePolicySpace((CandidatePolicySet('food_policy',('favor_food',),policy_class_ids=('local',)),),
                             ('local','missing_exit'))
    a=rt.evaluate_framed_policy_space(state(),bad,valid_frame())
    assert a.status == 'pi_completeness_failed_missing_material_policy_classes'
    assert a.domain_framing is None
    assert a.evaluations == ()
