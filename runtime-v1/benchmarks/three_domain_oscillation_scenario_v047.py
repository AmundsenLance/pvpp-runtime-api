
import sys
from dataclasses import dataclass
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection
from pvpp_runtime.testing import bounded_viability_oracle, classify_multidomain_stress

THRESHOLD=5.0
DOMAINS=('hydration','energy','safety')
ACTION_FOR_DOMAIN={'hydration':'seek_water','energy':'forage_food','safety':'hide_rest'}
DOMAIN_FOR_ACTION={v:k for k,v in ACTION_FOR_DOMAIN.items()}

# Deliberately bounded synthetic ecology. Repeating the same repair twice produces
# a "deep recovery" bonus; rotating every cycle never earns that bonus.
BASE_EFFECTS={
    'seek_water': {'hydration':2.0,'energy':-1.0,'safety':-1.0},
    'forage_food': {'hydration':-1.0,'energy':2.0,'safety':-1.0},
    'hide_rest': {'hydration':-1.0,'energy':-1.0,'safety':2.0},
}
DEEP_BONUS=4.0

@dataclass(frozen=True)
class EcoState:
    time: int
    hydration: float
    energy: float
    safety: float
    previous_action: str|None = None
    def values(self):
        return {'hydration':self.hydration,'energy':self.energy,'safety':self.safety}
    def key(self):
        return (self.time,self.hydration,self.energy,self.safety,self.previous_action)

def ecology_step(s:EcoState, action_id:str)->EcoState:
    vals=s.values()
    eff=BASE_EFFECTS[action_id]
    vals={d:vals[d]+eff[d] for d in DOMAINS}
    target=DOMAIN_FOR_ACTION[action_id]
    if s.previous_action==action_id:
        vals[target]+=DEEP_BONUS
    return EcoState(s.time+1,vals['hydration'],vals['energy'],vals['safety'],action_id)

def viable(s:EcoState):
    return min(s.values().values()) > THRESHOLD

def recovered(s:EcoState):
    return min(v-THRESHOLD for v in s.values().values()) >= 8.0

class World:
    def represented_state_from_actual(self,s):
        vals=dict(s.pp['domains'])
        return WorldState(s.time,vals,{'state_id':s.state_id,'previous_action':s.context.get('previous_action')})
    def perceive(self,s): return s
    def domain_value(self,s,d): return float(s.powers[d])
    def project(self,s,a):
        # Baseline continuation used by H: every domain deteriorates at 1 unit/step.
        if a.id=='steady':
            return ActionProjection(a.id,WorldState(s.time+1,{d:float(s.powers[d])-1.0 for d in DOMAINS},dict(s.metadata)),True)
        return ActionProjection(a.id,s,True)
    def pressure_factors(self,state,did,baseline_drift):
        return PressureFactors(did,self.domain_value(state,did)-THRESHOLD,baseline_drift)
    def pressure_value(self,did,factors):
        return 1.0/max(float(factors.margin),0.1)
    def expected_deterioration(self,state,did,baseline_drift,pressure_value,pressure_factors):
        return baseline_drift
    def constraint_profile(self,state,pid,action_ids,regime,governing):
        return PolicyConstraintProfile(pid,(ConstraintObservation('hard',False),ConstraintObservation('soft',False)))
    def fallback_structure_profile(self,state,pid,action_ids,governing):
        return FallbackStructuralProfile(pid)

    def project_policy_record(self,state,pid,action_ids):
        # One-step structural projection: only the policy matching a governing
        # domain gets a recovery corridor for that domain. This intentionally
        # reproduces the working-draft local-repair setup.
        aid=action_ids[0]
        target=DOMAIN_FOR_ACTION.get(aid)
        vals={d:float(state.powers[d]) for d in DOMAINS}
        projected_h={}
        corridors=[]
        for d in DOMAINS:
            # conservative one-step expected horizon under immediate action
            if d==target:
                h=max((vals[d]+2.0-THRESHOLD),0.0)
            else:
                h=max((vals[d]-1.0-THRESHOLD),0.0)
            projected_h[d]=h
            if d==target:
                corridors.append(RecoveryCorridorProjection(
                    d,f'{d}_continuity',True,True,True,1.0,h
                ))
        return PolicyProjectionRecord(pid,True,state,projected_h,tuple(corridors),projection_horizon=12.0)

class Transition:
    def transition(self,current,handoff):
        aid={
            'graph:water':'seek_water',
            'graph:food':'forage_food',
            'graph:hide':'hide_rest',
        }[handoff.selected_policy_id]
        vals=dict(current.pp['domains'])
        prev=current.context.get('previous_action')
        eco=EcoState(int(current.time),vals['hydration'],vals['energy'],vals['safety'],prev)
        nxt=ecology_step(eco,aid)
        next_state=ActualPersistentStateEnvelope(
            current.actor_id,f's{nxt.time}',float(nxt.time),
            {'domains':nxt.values()},current.spv,
            {'viable':viable(nxt)},{'previous_action':aid}
        )
        return Layer1TransitionResult(
            handoff.episode_id,handoff.selected_policy_id,current.state_id,
            next_state,True,{'ecology_transition':True}
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
        'cont','i','i','continuation',DOMAINS,'reachable','continue',('continuation',)))
    r.register_graph_transformation(GraphTransformationDefinition(
        'water','i','i','maintenance_local_adjustment',('hydration',),'reachable','seek_water',('local',)))
    r.register_graph_transformation(GraphTransformationDefinition(
        'food','i','i','maintenance_local_adjustment',('energy',),'reachable','forage_food',('local',)))
    r.register_graph_transformation(GraphTransformationDefinition(
        'hide','i','i','maintenance_local_adjustment',('safety',),'reachable','hide_rest',('local',)))
    # State-independent only; should not matter when adequacy yields a unique target repair.
    r.register_sigma_order(SigmaOrderDefinition('graph:cont',5))
    r.register_sigma_order(SigmaOrderDefinition('graph:water',10))
    r.register_sigma_order(SigmaOrderDefinition('graph:food',20))
    r.register_sigma_order(SigmaOrderDefinition('graph:hide',30))
    return PVPPRuntime(r,World(),layer1_transition_service=Transition())

def request(framed_domains):
    framed_domains=tuple(framed_domains)
    return CanonicalDecisionCycleRequest(
        PreliminaryPreservationObject('survival','preserve current governing survival continuity'),
        DomainFrame(tuple(DomainFrameTarget(d,f'{d}_continuity') for d in framed_domains)),
        ('continuation','maintenance_local_adjustment'),(),
        ('continuation','local')
    )

def actual_from_eco(s):
    return ActualPersistentStateEnvelope(
        'agent',f's{s.time}',float(s.time),{'domains':s.values()},{},
        {'viable':viable(s)},{'previous_action':s.previous_action}
    )

def run_runtime(cycles=18):
    rt=build_runtime()
    current=actual_from_eco(EcoState(0,9.0,10.0,15.0,None))
    policies=[]; governing=[]; margins=[]; regimes=[]; decision_statuses=[]; adequacy_statuses=[]
    for i in range(cycles):
        vals=dict(current.pp['domains'])
        margins.append({d:vals[d]-THRESHOLD for d in DOMAINS})
        out=rt.evaluate_integrated_canonical_cycle(
            current,request(tuple(d for d,v in vals.items() if abs(v-min(vals.values())) < 1e-12)),execute=True,episode_id=f'osc-{i}',max_execution_steps=1,
            execution_observations=(ExecutionObservation(f'obs-{i}',completed=True),)
        )
        if out.decision.governing_assessment is not None:
            governing.append(tuple(out.decision.governing_assessment.governing_domain_ids))
        else:
            governing.append(())
        regimes.append(out.decision.regime_assessment.regime if out.decision.regime_assessment else None)
        decision_statuses.append(out.decision.status)
        adequacy_statuses.append(out.decision.adequacy.status if out.decision.adequacy else None)
        pid=out.decision.selection.selected_policy_id if out.decision.selection else None
        policies.append(pid)
        current=out.final_actual_state
        if pid is None:
            break
        if min(current.pp['domains'].values()) <= THRESHOLD:
            break
    vals=dict(current.pp['domains'])
    margins.append({d:vals[d]-THRESHOLD for d in DOMAINS})
    collapsed=min(vals.values()) <= THRESHOLD
    rec=min(v-THRESHOLD for v in vals.values()) >= 8.0
    return current,tuple(policies),tuple(governing),tuple(margins),tuple(regimes),collapsed,rec,tuple(decision_statuses),tuple(adequacy_statuses)

def viability_precheck(horizon=12):
    init=EcoState(0,9.0,10.0,15.0,None)
    return bounded_viability_oracle(
        init,('seek_water','forage_food','hide_rest'),ecology_step,viable,horizon,
        state_key=lambda s:(s.hydration,s.energy,s.safety,s.previous_action),
        success=recovered
    )

def main():
    witness=viability_precheck(12)
    final,policies,governing,margins,regimes,collapsed,rec,statuses,adequacy=run_runtime(18)
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
    print('final_domains=',final.pp['domains'])
    print('classification=',classification.outcome)
    print('policy_period=',classification.policy_diagnostics.repeated_period,
          'repetitions=',classification.policy_diagnostics.repeated_period_repetitions)

if __name__=='__main__':
    main()
