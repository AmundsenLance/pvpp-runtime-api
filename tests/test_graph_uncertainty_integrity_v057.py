import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection
class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)
def base():
    r=PVPPRegistry();r.register_domain(DomainDefinition('D','d',0))
    for a in ('steady','cont','repair','exit'):r.register_action(ActionDefinition(a,a,('D',)))
    for i in ('x','y'):r.register_graph_instance(GraphInstanceDefinition(i,'asset',('D',),'ok'))
    return PVPPRuntime(r,W()),r,PreliminaryPreservationObject('p','preserve function')
def add(r,id,fam,status,act,*,note='',only=False,required=False):
    r.register_graph_transformation(GraphTransformationDefinition(
        id,'x','y',fam,('D',),status,act,structurally_required=required,
        uncertainty_note=note,structural_effect=fam,only_viable_path_candidate=only))
def test_uncertain_requires_reason():
    rt,r,po=base()
    try:add(r,'u','corrective_repair','uncertain','repair');assert False
    except ValueError as e: assert 'uncertainty_note' in str(e)
def test_uncertain_alternate_with_family_already_known_can_conditionally_pass():
    rt,r,po=base();add(r,'c','continuation','reachable','cont');add(r,'r','corrective_repair','reachable','repair');add(r,'u','corrective_repair','uncertain','repair',note='supplier confirmation pending')
    g=rt.construct_graph(po,'Mission',('D',),required_family_ids=('continuation',))
    assert g.status=='CONDITIONAL PASS' and g.safe_to_handoff
    assert g.open_uncertainty_markers==('u: supplier confirmation pending',)
    assert not g.uncertain_family_presence_ids
def test_uncertain_sole_family_presence_cannot_conditionally_pass():
    rt,r,po=base();add(r,'c','continuation','reachable','cont');add(r,'u','corrective_repair','uncertain','repair',note='access unknown')
    g=rt.construct_graph(po,'Mission',('D',),required_family_ids=('continuation',))
    assert g.status=='FAIL' and 'G-004' in g.failure_codes
    assert g.uncertain_family_presence_ids==('corrective_repair',)
    assert not g.safe_to_handoff and not g.policy_seeds
def test_uncertain_only_viable_path_candidate_fails_even_if_family_has_other_reachable_member():
    rt,r,po=base();add(r,'c','continuation','reachable','cont');add(r,'r','corrective_repair','reachable','repair');add(r,'u','corrective_repair','uncertain','repair',note='bridge state unknown',only=True)
    g=rt.construct_graph(po,'Mission',('D',),required_family_ids=('continuation',))
    assert g.status=='FAIL' and 'G-004' in g.failure_codes
    assert g.uncertain_only_viable_path_ids==('u',)
def test_uncertain_required_path_still_fails_closed():
    rt,r,po=base();add(r,'c','continuation','reachable','cont');add(r,'u','exit_transfer_liquidation','uncertain','exit',note='buyer access unverified',required=True)
    g=rt.construct_graph(po,'Survival',('D',),required_family_ids=('continuation','exit_transfer_liquidation'))
    assert g.status=='FAIL' and 'G-003' in g.failure_codes
def test_pi_cannot_bypass_uncertainty_invalid_graph():
    rt,r,po=base();add(r,'c','continuation','reachable','cont');add(r,'u','corrective_repair','uncertain','repair',note='unknown')
    g=rt.construct_graph(po,'Mission',('D',),required_family_ids=('continuation',))
    pi=rt.construct_pi_from_graph(g,('continuation',))
    assert pi.status=='pi_blocked_by_graph_invalidity'
def test_unreachable_remains_absent_not_uncertain():
    rt,r,po=base();add(r,'c','continuation','reachable','cont');add(r,'r','corrective_repair','unreachable','repair')
    g=rt.construct_graph(po,'Mission',('D',),required_family_ids=('continuation',))
    assert g.status=='PASS' and g.excluded_transformation_ids==('r',) and not g.open_uncertainty_markers
