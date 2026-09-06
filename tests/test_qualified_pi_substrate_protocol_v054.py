
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass
def rt():
    r=PVPPRegistry();r.register_action(ActionDefinition('steady','steady',()))
    return PVPPRuntime(r,W())

def complete(ok=True):
    return PiCompletenessAssessment(
        'pi_complete' if ok else 'pi_incomplete',
        ok,('continuation','exit'),('continuation','exit') if ok else ('continuation',),
        () if ok else ('exit',),('p',)
    )

def q(status,basis='paired contaminated-substrate trace'):
    return EpistemicSubstrateQualification(status,basis,('memory_distortion',) if status!='clean' else ())

def test_clean_complete_is_only_unqualified_pass():
    a=rt().qualify_pi_completeness_for_substrate(complete(True),q('clean','validated clean graph substrate'))
    assert a.status=='qualified_pi_pass'
    assert a.unqualified_structural_pass
    assert a.downstream_full_confidence_licensed

def test_clean_incomplete_is_pi_fail():
    a=rt().qualify_pi_completeness_for_substrate(complete(False),q('clean','validated clean graph substrate'))
    assert a.status=='qualified_pi_fail'
    assert not a.downstream_full_confidence_licensed
    assert a.layered_attribution==('Pi completeness failure on clean substrate',)

def test_uncertain_substrate_cannot_receive_unqualified_pass_even_if_pi_mirrors_it():
    a=rt().qualify_pi_completeness_for_substrate(complete(True),q('uncertain'))
    assert a.status=='qualified_pi_conditional_warning'
    assert a.local_pi_complete
    assert not a.unqualified_structural_pass
    assert not a.downstream_full_confidence_licensed

def test_contaminated_substrate_cannot_receive_unqualified_pass():
    a=rt().qualify_pi_completeness_for_substrate(complete(True),q('epistemically_contaminated'))
    assert a.status=='qualified_pi_conditional_warning'
    assert not a.downstream_full_confidence_licensed

def test_contaminated_plus_local_omission_preserves_layered_attribution():
    a=rt().qualify_pi_completeness_for_substrate(complete(False),q('epistemically_contaminated'))
    assert a.status=='qualified_pi_fail_with_layered_attribution'
    assert a.layered_attribution==(
        'substrate qualification: epistemically_contaminated',
        'local Pi completeness failure'
    )

def test_financial_exit_scenario_protocol_application():
    # Test-006-like: sale path never enters contaminated graph; local Pi mirrors its input.
    local=PiCompletenessAssessment('pi_complete',True,('continuation',),('continuation',),(),('continue',))
    a=rt().qualify_pi_completeness_for_substrate(
        local,EpistemicSubstrateQualification(
            'epistemically_contaminated',
            'memory-distorted sale reachability under paired reference trace',
            ('sale_path_suppressed',)
        )
    )
    assert a.status=='qualified_pi_conditional_warning'
    assert not a.downstream_full_confidence_licensed

def test_support_help_scenario_protocol_application():
    # Different scenario family: distorted help-seeking memory narrows support path.
    local=PiCompletenessAssessment('pi_complete',True,('self_continuation',),('self_continuation',),(),('self',))
    a=rt().qualify_pi_completeness_for_substrate(
        local,EpistemicSubstrateQualification(
            'uncertain','support path credibility under contaminated retrieval',
            ('helper_reachability_uncertain',)
        )
    )
    assert a.status=='qualified_pi_conditional_warning'

def test_method_does_not_restore_or_modify_local_pi_result():
    local=complete(False)
    a=rt().qualify_pi_completeness_for_substrate(local,q('epistemically_contaminated'))
    assert a.local_completeness is local
    assert local.missing_class_ids==('exit',)
    assert not hasattr(a,'restored_policy_classes')

def test_invalid_status_or_blank_basis_rejected():
    runtime=rt()
    for qualification in (
        EpistemicSubstrateQualification('maybe','basis'),
        EpistemicSubstrateQualification('clean',''),
    ):
        try:
            runtime.qualify_pi_completeness_for_substrate(complete(),qualification)
            assert False
        except ValueError:
            pass

def test_canonical_cycle_remains_unmodified_by_supporting_boundary():
    # Architectural test: method exists, but request/assessment has no substrate qualification field.
    assert 'substrate' not in CanonicalDecisionCycleRequest.__dataclass_fields__
    assert 'qualified_pi' not in CanonicalDecisionCycleAssessment.__dataclass_fields__
