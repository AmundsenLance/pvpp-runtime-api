import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def base():
    r=PVPPRegistry()
    r.register_domain(DomainDefinition("T","transport",0))
    r.register_domain(DomainDefinition("F","finance",0))
    for a in ("steady","continue","sell","buy","repair","escape"):
        r.register_action(ActionDefinition(a,a,("T","F")))
    r.register_graph_instance(GraphInstanceDefinition("car","asset",("T",),"failing"))
    r.register_graph_instance(GraphInstanceDefinition("cash","asset",("F",),"available"))
    r.register_graph_instance(GraphInstanceDefinition("replacement","asset",("T",),"available"))
    rt=PVPPRuntime(r,W())
    po=PreliminaryPreservationObject("transport_fn","household transportation viability","mechanism independent")
    return rt,r,po

def tr(r,id,src,dst,family,status,action,classes=(),required=False,only_viable=False):
    r.register_graph_transformation(GraphTransformationDefinition(
        id,src,dst,family,("T",),status,action,classes,
        structurally_required=required,structural_effect=family,
        uncertainty_note=("reachability evidence incomplete" if status=="uncertain" else ""),
        only_viable_path_candidate=only_viable
    ))

def test_valid_graph_reaches_pi_handoff_and_preserves_staged_exit_substitution():
    rt,r,po=base()
    tr(r,"cont","car","car","continuation","reachable","continue",("continuation",))
    tr(r,"sell","car","cash","exit_transfer_liquidation","reachable","sell",("exit",))
    tr(r,"buy","cash","replacement","substitution","reachable","buy",("substitution",))
    r.register_graph_composition(GraphCompositionDefinition(
        "sell_replace",("sell","buy"),"substitution",("T",),
        ("staged_exit_substitution",),"exit then replacement","direct recovery vs staged recovery",True
    ))
    g=rt.construct_graph(po,"Survival",("T",),
        required_family_ids=("continuation","exit_transfer_liquidation","substitution"),
        required_path_class_ids=("staged_exit_substitution",))
    assert g.status=="PASS"
    assert "graphpath:sell_replace" in g.seed_ids
    pi=rt.construct_pi_from_graph(g,("continuation","staged_exit_substitution"))
    assert pi.status=="pi_constructed"
    assert rt.validate_pi_completeness(pi.policy_space).complete is True

def test_unreachable_transformation_is_recorded_but_not_admitted():
    rt,r,po=base()
    tr(r,"cont","car","car","continuation","reachable","continue")
    tr(r,"fake","car","replacement","substitution","unreachable","buy")
    g=rt.construct_graph(po,"Mission",("T",),required_family_ids=("continuation",))
    assert g.status=="PASS"
    assert g.excluded_transformation_ids==("fake",)
    assert "fake" not in g.validated_transformation_ids
    assert all("fake" not in s.id for s in g.policy_seeds)

def test_missing_required_family_is_graph_failure_not_pi_failure():
    rt,r,po=base()
    tr(r,"cont","car","car","continuation","reachable","continue")
    g=rt.construct_graph(po,"Survival",("T",),
        required_family_ids=("continuation","exit_transfer_liquidation"))
    assert g.status=="FAIL"
    assert "G-002" in g.failure_codes
    pi=rt.construct_pi_from_graph(g,("continuation",))
    assert pi.status=="pi_blocked_by_graph_invalidity"

def test_uncertain_nonmaterial_path_allows_conditional_pass():
    rt,r,po=base()
    tr(r,"cont","car","car","continuation","reachable","continue")
    tr(r,"repair","car","car","corrective_repair","reachable","repair")
    tr(r,"maybe_repair","car","car","corrective_repair","uncertain","repair")
    g=rt.construct_graph(po,"Mission",("T",),required_family_ids=("continuation",))
    assert g.status=="CONDITIONAL PASS"
    assert g.uncertain_transformation_ids==("maybe_repair",)

def test_uncertain_required_family_fails_graph():
    rt,r,po=base()
    tr(r,"cont","car","car","continuation","reachable","continue")
    tr(r,"maybe_exit","car","cash","exit_transfer_liquidation","uncertain","sell",required=True)
    g=rt.construct_graph(po,"Survival",("T",),
        required_family_ids=("continuation","exit_transfer_liquidation"))
    assert g.status=="FAIL"
    assert "G-003" in g.failure_codes

def test_invalid_staged_composition_is_rejected():
    rt,r,po=base()
    tr(r,"cont","car","car","continuation","reachable","continue")
    tr(r,"sell","car","cash","exit_transfer_liquidation","reachable","sell")
    tr(r,"repair","car","car","corrective_repair","reachable","repair")
    # sell ends at cash, repair starts at car: discontinuous path.
    r.register_graph_composition(GraphCompositionDefinition(
        "broken_path",("sell","repair"),"structural_reconfiguration",("T",),
        ("staged_recovery",),"recovery","staged",True
    ))
    g=rt.construct_graph(po,"Survival",("T",),
        required_family_ids=("continuation",),required_path_class_ids=("staged_recovery",))
    assert g.status=="FAIL"
    assert "G-005" in g.failure_codes

def test_required_multistep_class_missing_is_detected_before_pi():
    rt,r,po=base()
    tr(r,"cont","car","car","continuation","reachable","continue")
    tr(r,"sell","car","cash","exit_transfer_liquidation","reachable","sell")
    g=rt.construct_graph(po,"Survival",("T",),
        required_family_ids=("continuation","exit_transfer_liquidation"),
        required_path_class_ids=("staged_exit_substitution",))
    assert g.status=="FAIL"
    assert "G-005" in g.failure_codes

def test_graph_seed_overflow_blocks_handoff_without_order_truncation():
    rt,r,po=base()
    tr(r,"cont","car","car","continuation","reachable","continue")
    for i in range(6):
        aid=f"a{i}"; iid=f"i{i}"
        r.register_action(ActionDefinition(aid,aid,("T",)))
        r.register_graph_instance(GraphInstanceDefinition(iid,"option",("T",),"available"))
        tr(r,f"t{i}","car",iid,"maintenance_local_adjustment","reachable",aid,(f"k{i}",))
    g=rt.construct_graph(po,"Mission",("T",),required_family_ids=("continuation",),
        config=GraphConstructionConfig(max_seeds=3))
    assert g.status=="FAIL"
    assert "G-007" in g.failure_codes
    assert g.policy_seeds==()
    assert g.seed_ids==()

def test_graph_validity_does_not_guarantee_pi_completeness():
    rt,r,po=base()
    tr(r,"cont","car","car","continuation","reachable","continue",("continuation",))
    g=rt.construct_graph(po,"Mission",("T",),required_family_ids=("continuation",))
    assert g.status=="PASS"
    pi=rt.construct_pi_from_graph(g,("continuation","missing_pi_class"))
    comp=rt.validate_pi_completeness(pi.policy_space)
    assert comp.complete is False
    assert comp.missing_class_ids==("missing_pi_class",)

def test_preliminary_scope_is_not_downstream_domain_framing():
    rt,r,_=base()
    tr(r,"cont","car","car","continuation","reachable","continue")
    bad=PreliminaryPreservationObject("","")
    g=rt.construct_graph(bad,"Mission",("T",),required_family_ids=("continuation",))
    assert g.status=="FAIL"
    assert "G-010" in g.failure_codes
