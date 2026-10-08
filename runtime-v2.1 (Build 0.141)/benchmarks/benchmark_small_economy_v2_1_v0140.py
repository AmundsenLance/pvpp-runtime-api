"""PV-PP Runtime V2.1 Small Economy objective-perturbation benchmark (v0.140).

The benchmark is deliberately a runtime/application benchmark, not framework authority.
It holds a compact economy/state substrate fixed where possible and perturbs O_i(t) to
verify that objective influence remains confined to the V2.1-authorized channels.
"""
from __future__ import annotations
from dataclasses import dataclass
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))

from pvpp_runtime import *


class SmallEconomyWorld:
    """Host-owned mechanics for a stylized household/workshop economy."""
    def represented_state_from_actual(self, actual):
        return WorldState(actual.time, {"solvency": 8.0, "continuity": 8.0}, {"state_id": actual.state_id})


class EconomyResp:
    """Application-owned objective/policy relation; no framework ranking semantics."""
    def objective_responsiveness(self, state, policy_id, action_ids, obj):
        kind=str(obj.content)
        table={
            "maintain_viability": {"maintain":"supports","expand":"neutral","train":"neutral"},
            "increase_output": {"maintain":"neutral","expand":"supports","train":"supports"},
            "reduce_workload": {"maintain":"neutral","expand":"conflicts","train":"neutral"},
            "maximize_output_at_any_cost": {"maintain":"conflicts","expand":"supports","train":"neutral"},
            "impossible_teleport_capacity": {"maintain":"neutral","expand":"neutral","train":"neutral"},
            "develop_skill": {"maintain":"neutral","expand":"neutral","train":"supports"},
        }
        rel=table.get(kind,{}).get(policy_id,"unresolved")
        return ObjectiveResponsivenessRecord(policy_id,obj.id,rel,evidence={"economy_model":"v0.140"},provenance="small-economy-v2.1")


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    objective_ids: tuple[str,...]
    active_objective_ids: tuple[str,...]
    graph_validated: tuple[str,...]
    graph_excluded: tuple[str,...]
    candidate_ids: tuple[str,...]
    responsiveness: tuple[tuple[str,str,str],...]
    lifecycle_reentry_stage: str|None=None
    memory_governance_current_positive: bool|None=None
    notes: tuple[str,...]=()


def _objective(oid, content, status="active", version="1"):
    return QualifiedObjectiveRecord(oid,content,"self-adopted","small-economy",status=status,
                                    authority={"basis":"actor"},version=version)


def _objectives(*objs, version="1"):
    return ObjectiveSet("economy",0.0,tuple(objs),"small-economy-objectives",version)


def build_runtime():
    reg=PVPPRegistry()
    reg.register_domain(DomainDefinition("solvency","solvency",5.0))
    reg.register_domain(DomainDefinition("continuity","continuity",5.0))
    for aid in ("steady","maintain_action","expand_action","train_action","teleport_action"):
        reg.register_action(ActionDefinition(aid,aid,()))
    reg.register_graph_instance(GraphInstanceDefinition("shop","system",("solvency","continuity"),"current"))
    reg.register_graph_transformation(GraphTransformationDefinition(
        "t_maintain","shop","shop","continuation",("solvency","continuity"),"reachable","maintain_action",("continuation",)))
    reg.register_graph_transformation(GraphTransformationDefinition(
        "t_expand","shop","shop","structural_reconfiguration",("solvency","continuity"),"reachable","expand_action",("expansion",)))
    reg.register_graph_transformation(GraphTransformationDefinition(
        "t_train","shop","shop","maintenance_local_adjustment",("continuity",),"reachable","train_action",("capability_development",)))
    # Desired teleport capacity is deliberately represented as structurally unavailable.
    reg.register_graph_transformation(GraphTransformationDefinition(
        "t_teleport","shop","shop","maintenance_local_adjustment",("continuity",),"unreachable","teleport_action",("teleport",)))
    return PVPPRuntime(reg,SmallEconomyWorld())


def _space():
    return CandidatePolicySpace((
        CandidatePolicySet("maintain",("maintain_action",),policy_class_ids=("continuation",)),
        CandidatePolicySet("expand",("expand_action",),policy_class_ids=("expansion",)),
        CandidatePolicySet("train",("train_action",),policy_class_ids=("capability_development",)),
    ),("continuation","expansion","capability_development"))


def _graph(rt):
    return rt.construct_graph(PreliminaryPreservationObject("preserve","preserve economy"),"ordinary",("solvency","continuity"))


def _evaluate(rt, case_id, os, *, lifecycle=None, governance=None):
    actual=ActualPersistentStateEnvelope("economy","econ-state",0.0,{"labor":1},{"cash":8},{"solvency":8,"continuity":8},{"market":"stable"})
    active=rt.validate_objective_set(os,actual) if os is not None else None
    graph=_graph(rt); space=_space()
    resp=rt.evaluate_objective_responsiveness(WorldState(0.0,{}),space,os,EconomyResp())
    assert resp.valid
    return CaseResult(
        case_id,
        tuple(o.id for o in os.objectives) if os else (),
        tuple(o.id for o in os.objectives) if os and active.valid else (),
        tuple(graph.validated_transformation_ids), tuple(graph.excluded_transformation_ids),
        tuple(c.id for c in space.candidates),
        tuple((r.policy_id,r.objective_id,r.relation) for r in resp.records),
        lifecycle.reentry.recompute_from_stage if lifecycle else None,
        governance.usable_as_current_positive_evidence if governance else None,
    )


def run_benchmark():
    rt=build_runtime(); out=[]
    # 1. Attainable objective: responsiveness is visible, but candidate/Graph authority is unchanged.
    out.append(_evaluate(rt,"attainable",_objectives(_objective("o_output","increase_output"))))
    # 2. Conflicting objectives coexist without runtime weighting or pruning.
    out.append(_evaluate(rt,"conflicting",_objectives(_objective("o_output","increase_output"),_objective("o_work","reduce_workload"))))
    # 3. Objective-versus-viability: a policy may support the objective; that support is not adequacy/authority.
    out.append(_evaluate(rt,"objective_vs_viability",_objectives(_objective("o_anycost","maximize_output_at_any_cost"))))
    # 4. Impossible objective: unavailable desired capability remains excluded from current Graph.
    out.append(_evaluate(rt,"impossible",_objectives(_objective("o_teleport","impossible_teleport_capacity"))))
    # 5. Capability-development objective: currently reachable training is representable; future skill is not current PP.
    out.append(_evaluate(rt,"capability_development",_objectives(_objective("o_skill","develop_skill"))))
    # 6. Lifecycle: only explicitly objective-dependent artifacts invalidate; viability prefix is preserved.
    deps=(GovernanceArtifactDependency("dep_graph","graph-objective-cues","Graph/Seed","objective",("objective:o_output",)),)
    change=ObjectiveLifecycleChange("oc1","economy","small-economy-objectives","1","small-economy-objectives","2",("o_output",),"completed")
    life=derive_objective_lifecycle_invalidations(deps,change)
    assert life.valid and life.preserved_stage_ids==("PPP","Phi","H","G","R")
    out.append(_evaluate(rt,"lifecycle",_objectives(version="2"),lifecycle=life))
    # 7. Relevant but prohibited evidence: relevance cannot promote it to permitted/current positive evidence.
    gov=InformationGovernanceMetadata(source_authority="ledger",applicability_scope="economy",
        permitted_use_scope="audit-only",authorized_surfaces=("audit",),disposition="prohibited_for_use")
    ga=rt.validate_information_governance_metadata(gov)
    assert ga.valid and not ga.usable_as_current_positive_evidence
    out.append(_evaluate(rt,"unauthorized_evidence",_objectives(_objective("o_output","increase_output")),governance=ga))
    # 8. No-objective control: the economy/Graph/candidate substrate remains valid with O absent.
    out.append(_evaluate(rt,"no_objective",None))
    return tuple(out)


def assert_benchmark_invariants(results):
    by={r.case_id:r for r in results}
    baseline=by["no_objective"]
    # O never rewrites Graph admission or candidate construction in this controlled economy.
    for r in results:
        assert r.graph_validated==baseline.graph_validated
        assert r.graph_excluded==baseline.graph_excluded
        assert r.candidate_ids==baseline.candidate_ids
    assert "t_teleport" in baseline.graph_excluded
    # Conflicts coexist; no policy disappears.
    cr=by["conflicting"]
    assert ("expand","o_output","supports") in cr.responsiveness
    assert ("expand","o_work","conflicts") in cr.responsiveness
    # Objective support does not erase viability-relevant alternatives.
    assert ("expand","o_anycost","supports") in by["objective_vs_viability"].responsiveness
    assert set(by["objective_vs_viability"].candidate_ids)=={"maintain","expand","train"}
    # Capability development uses a currently reachable path while desired teleport capability stays unavailable.
    assert ("train","o_skill","supports") in by["capability_development"].responsiveness
    assert "t_train" in by["capability_development"].graph_validated
    assert "t_teleport" in by["capability_development"].graph_excluded
    # Objective lifecycle begins no earlier than the explicit dependency and does not restart viability prefix.
    assert by["lifecycle"].lifecycle_reentry_stage=="Graph/Seed"
    # Information governance remains sovereign over objective relevance.
    assert by["unauthorized_evidence"].memory_governance_current_positive is False
    # O-free operation is a valid control.
    assert baseline.objective_ids==() and baseline.responsiveness==()
    return True


if __name__=='__main__':
    rs=run_benchmark(); assert_benchmark_invariants(rs)
    for r in rs:
        print(r.case_id, "objectives=",r.objective_ids,"graph=",r.graph_validated,"excluded=",r.graph_excluded,
              "candidates=",r.candidate_ids,"reentry=",r.lifecycle_reentry_stage,"gov_current=",r.memory_governance_current_positive)
    print("PASS: V2.1 Small Economy objective perturbation benchmark")
