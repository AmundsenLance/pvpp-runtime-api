
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
if str(ROOT/'benchmarks') not in sys.path: sys.path.insert(0,str(ROOT/'benchmarks'))

from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection
from pvpp_runtime.testing import classify_multidomain_stress, analyze_sequence
from three_domain_oscillation_scenario_v047 import (
    THRESHOLD, DOMAINS, ACTION_FOR_DOMAIN, DOMAIN_FOR_ACTION,
    EcoState, ecology_step, viable, recovered, actual_from_eco, viability_precheck
)

STAGED_POLICY_ACTIONS={
    'graphpath:water_depth':('seek_water','seek_water'),
    'graphpath:food_depth':('forage_food','forage_food'),
    'graphpath:hide_depth':('hide_rest','hide_rest'),
}
SINGLE_POLICY_ACTIONS={
    'graph:water':('seek_water',),
    'graph:food':('forage_food',),
    'graph:hide':('hide_rest',),
    'graph:cont':('continue',),
}
POLICY_ACTIONS={**SINGLE_POLICY_ACTIONS,**STAGED_POLICY_ACTIONS}


def represented_eco(state):
    vals={d:float(state.powers[d]) for d in DOMAINS}
    return EcoState(
        int(state.time),vals['hydration'],vals['energy'],vals['safety'],
        state.metadata.get('previous_action')
    )


def simulate_policy(state, action_ids):
    eco=represented_eco(state)
    path=[eco]
    for aid in action_ids:
        if aid=='continue':
            eco=EcoState(
                eco.time+1,
                eco.hydration-1.0,eco.energy-1.0,eco.safety-1.0,
                eco.previous_action
            )
        else:
            eco=ecology_step(eco,aid)
        path.append(eco)
    return tuple(path)


class BufferedWorld:
    """Same ecology as v0.47, but projection represents short staged recovery depth."""
    def represented_state_from_actual(self,s):
        vals=dict(s.pp['domains'])
        return WorldState(
            s.time,vals,
            {'state_id':s.state_id,'previous_action':s.context.get('previous_action')}
        )

    def perceive(self,s):
        return s

    def domain_value(self,s,d):
        return float(s.powers[d])

    def project(self,s,a):
        # Baseline continuation for Phi/H remains identical to v0.47.
        if a.id=='steady':
            return ActionProjection(
                a.id,
                WorldState(
                    s.time+1,
                    {d:float(s.powers[d])-1.0 for d in DOMAINS},
                    dict(s.metadata)
                ),
                True
            )
        return ActionProjection(a.id,s,True)

    def pressure_factors(self,state,did,baseline_drift):
        return PressureFactors(
            did,self.domain_value(state,did)-THRESHOLD,baseline_drift
        )

    def pressure_value(self,did,factors):
        return 1.0/max(float(factors.margin),0.1)

    def expected_deterioration(self,state,did,baseline_drift,pressure_value,pressure_factors):
        return baseline_drift

    def constraint_profile(self,state,pid,action_ids,regime,governing):
        return PolicyConstraintProfile(
            pid,(ConstraintObservation('hard',False),
                 ConstraintObservation('soft',False))
        )

    def fallback_structure_profile(self,state,pid,action_ids,governing):
        return FallbackStructuralProfile(pid)

    def project_policy_record(self,state,pid,action_ids):
        action_ids=tuple(action_ids)
        path=simulate_policy(state,action_ids)
        final=path[-1]
        vals=final.values()

        # Projected horizon remains domain-local. No scalar score is computed.
        projected_h={d:max(vals[d]-THRESHOLD,0.0) for d in DOMAINS}

        # A full recovery-corridor fact is emitted only for an explicitly staged
        # repeated repair that preserves viability through its intermediate state
        # and reaches real buffer depth in its target domain.
        corridors=[]
        target=None
        if len(action_ids)>=2 and len(set(action_ids))==1:
            target=DOMAIN_FOR_ACTION.get(action_ids[0])
        if target is not None:
            pre_viable=all(viable(x) for x in path[1:])
            reached=(vals[target]-THRESHOLD)>=8.0
            # Joint sustainment is represented by all domains remaining above the
            # threshold after the staged path, not by cross-domain aggregation.
            joint=all(vals[d]>THRESHOLD for d in DOMAINS)
            corridors.append(RecoveryCorridorProjection(
                target,f'{target}_continuity',
                pre_viable,reached,joint,
                float(len(action_ids)),projected_h[target]
            ))

        return PolicyProjectionRecord(
            pid,True,state,projected_h,tuple(corridors),
            projection_horizon=12.0,
            metadata={
                'projected_action_ids':action_ids,
                'projection_depth':len(action_ids),
                'buffered_recovery_target':target,
                'intermediate_viability':tuple(viable(x) for x in path[1:]),
            }
        )


class BufferedTransition:
    """Realizes the entire selected staged policy through the same host ecology."""
    def transition(self,current,handoff):
        actions=POLICY_ACTIONS[handoff.selected_policy_id]
        vals=dict(current.pp['domains'])
        eco=EcoState(
            int(current.time),vals['hydration'],vals['energy'],vals['safety'],
            current.context.get('previous_action')
        )
        for aid in actions:
            if aid=='continue':
                eco=EcoState(
                    eco.time+1,
                    eco.hydration-1.0,eco.energy-1.0,eco.safety-1.0,
                    eco.previous_action
                )
            else:
                eco=ecology_step(eco,aid)
        nxt=ActualPersistentStateEnvelope(
            current.actor_id,f's{eco.time}',float(eco.time),
            {'domains':eco.values()},current.spv,
            {'viable':viable(eco)},{'previous_action':eco.previous_action}
        )
        return Layer1TransitionResult(
            handoff.episode_id,handoff.selected_policy_id,current.state_id,
            nxt,True,{'ecology_transition':True,'full_policy_realized':True}
        )


def build_runtime():
    r=PVPPRegistry()
    for d in DOMAINS:
        r.register_domain(DomainDefinition(d,d,THRESHOLD))
    for aid in ('steady','continue','seek_water','forage_food','hide_rest'):
        r.register_action(ActionDefinition(aid,aid,DOMAINS))

    r.register_governing_configuration(GoverningConfiguration(0.0))
    r.register_regime_configuration(RegimeConfiguration(
        tau_h_existential=1.0,tau_h_survival=6.0,tau_h_stabilization=10.0,
        tau_phi_existential=100.0,tau_phi_survival=90.0,tau_phi_stabilization=80.0,
        tau_m_survival=99,tau_m_stabilization=99,
        tau_h_mult_survival=0.0,tau_h_mult_stabilization=0.0,
        delta_h_escalation=0.0,delta_h_deescalation=0.0
    ))
    r.register_constraint_rule(ConstraintRuleDefinition('hard','hard'))
    r.register_constraint_rule(ConstraintRuleDefinition('soft','soft'))
    r.register_fallback_configuration(FallbackConfiguration(0.05))

    r.register_graph_instance(GraphInstanceDefinition('i','agent',DOMAINS,'active'))
    r.register_graph_transformation(GraphTransformationDefinition(
        'cont','i','i','continuation',DOMAINS,'reachable','continue',('continuation',)
    ))
    r.register_graph_transformation(GraphTransformationDefinition(
        'water','i','i','maintenance_local_adjustment',('hydration',),
        'reachable','seek_water',('local',)
    ))
    r.register_graph_transformation(GraphTransformationDefinition(
        'food','i','i','maintenance_local_adjustment',('energy',),
        'reachable','forage_food',('local',)
    ))
    r.register_graph_transformation(GraphTransformationDefinition(
        'hide','i','i','maintenance_local_adjustment',('safety',),
        'reachable','hide_rest',('local',)
    ))

    # Explicit short compositions. No arbitrary search depth is added.
    r.register_graph_composition(GraphCompositionDefinition(
        'water_depth',('water','water'),'maintenance_local_adjustment',
        ('hydration',),('local','buffered_depth'),
        'two-step hydration recovery establishes real reserve depth',
        'distinct from one-step water repair because the second step unlocks the host deep-recovery effect'
    ))
    r.register_graph_composition(GraphCompositionDefinition(
        'food_depth',('food','food'),'maintenance_local_adjustment',
        ('energy',),('local','buffered_depth'),
        'two-step energy recovery establishes real reserve depth',
        'distinct from one-step food repair because the second step unlocks the host deep-recovery effect'
    ))
    r.register_graph_composition(GraphCompositionDefinition(
        'hide_depth',('hide','hide'),'maintenance_local_adjustment',
        ('safety',),('local','buffered_depth'),
        'two-step safety recovery establishes real reserve depth',
        'distinct from one-step hide/rest because the second step unlocks the host deep-recovery effect'
    ))

    # State-independent order remains explicit. It should not determine the result:
    # staged adequacy is unique at each cycle in this scenario.
    for idx,pid in enumerate((
        'graph:cont','graph:water','graph:food','graph:hide',
        'graphpath:water_depth','graphpath:food_depth','graphpath:hide_depth'
    ),start=1):
        r.register_sigma_order(SigmaOrderDefinition(pid,idx*10))

    return PVPPRuntime(r,BufferedWorld(),layer1_transition_service=BufferedTransition())


def request(framed_domains):
    framed_domains=tuple(framed_domains)
    return CanonicalDecisionCycleRequest(
        PreliminaryPreservationObject(
            'survival','preserve current governing survival continuity with explicit staged recovery'
        ),
        DomainFrame(tuple(
            DomainFrameTarget(d,f'{d}_continuity') for d in framed_domains
        )),
        ('continuation','maintenance_local_adjustment'),
        ('buffered_depth',),
        ('continuation','local','buffered_depth')
    )


def run_runtime(max_cycles=12):
    rt=build_runtime()
    current=actual_from_eco(EcoState(0,9.0,10.0,15.0,None))
    policies=[]; governing=[]; margins=[]; regimes=[]; statuses=[]; adequacy=[]; graph_paths=[]
    for i in range(max_cycles):
        vals=dict(current.pp['domains'])
        margins.append({d:vals[d]-THRESHOLD for d in DOMAINS})
        minimum=min(vals.values())
        framed=tuple(d for d,v in vals.items() if abs(v-minimum)<1e-12)
        out=rt.evaluate_integrated_canonical_cycle(
            current,request(framed),execute=True,episode_id=f'buffered-{i}',
            max_execution_steps=1,
            execution_observations=(ExecutionObservation(f'obs-{i}',completed=True),)
        )
        governing.append(
            tuple(out.decision.governing_assessment.governing_domain_ids)
            if out.decision.governing_assessment else ()
        )
        regimes.append(
            out.decision.regime_assessment.regime
            if out.decision.regime_assessment else None
        )
        statuses.append(out.decision.status)
        adequacy.append(out.decision.adequacy.status if out.decision.adequacy else None)
        graph_paths.append(
            tuple(out.decision.graph_assessment.composition_ids)
            if out.decision.graph_assessment else ()
        )
        pid=out.decision.selection.selected_policy_id if out.decision.selection else None
        policies.append(pid)
        current=out.final_actual_state
        if pid is None:
            break
        if recovered(EcoState(
            int(current.time),
            current.pp['domains']['hydration'],
            current.pp['domains']['energy'],
            current.pp['domains']['safety'],
            current.context.get('previous_action')
        )):
            break

    vals=dict(current.pp['domains'])
    margins.append({d:vals[d]-THRESHOLD for d in DOMAINS})
    collapsed=min(vals.values())<=THRESHOLD
    rec=min(v-THRESHOLD for v in vals.values())>=8.0
    return (
        current,tuple(policies),tuple(governing),tuple(margins),tuple(regimes),
        collapsed,rec,tuple(statuses),tuple(adequacy),tuple(graph_paths)
    )


def main():
    witness=viability_precheck(12)
    result=run_runtime(12)
    final,policies,governing,margins,regimes,collapsed,rec,statuses,adequacy,graph_paths=result
    classification=classify_multidomain_stress(
        structurally_feasible=witness.feasible,collapsed=collapsed,recovered=rec,
        margins=margins,policies=policies,governing_sets=governing
    )
    print('witness_feasible=',witness.feasible)
    print('witness_actions=',witness.action_path)
    print('runtime_policies=',policies)
    print('runtime_governing=',governing)
    print('runtime_regimes=',regimes)
    print('decision_statuses=',statuses)
    print('adequacy_statuses=',adequacy)
    print('graph_compositions_visible=',graph_paths)
    print('final_domains=',final.pp['domains'])
    print('classification=',classification.outcome)
    print('policy_period=',classification.policy_diagnostics.repeated_period)

if __name__=='__main__':
    main()
