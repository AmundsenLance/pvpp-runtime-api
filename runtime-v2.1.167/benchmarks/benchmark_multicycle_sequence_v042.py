
import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def represented_state_from_actual(self,s):
        return WorldState(s.time,{'G':10.0},{'state_id':s.state_id})
    def perceive(self,s): return s
    def domain_value(self,s,d): return float(s.powers.get(d,10.0))
    def project(self,s,a):
        if a.id=='steady':
            return ActionProjection(a.id,WorldState(s.time+1,{'G':9.0},dict(s.metadata)),True)
        return ActionProjection(a.id,s,True)
    def pressure_factors(self,s,d,drift): return PressureFactors(d,5.0,drift)
    def pressure_value(self,d,f): return 0.2
    def expected_deterioration(self,s,d,drift,p,f): return drift
    def constraint_profile(self,s,pid,a,r,g):
        return PolicyConstraintProfile(pid,(ConstraintObservation('soft',False),))
    def project_policy_record(self,s,pid,a):
        return PolicyProjectionRecord(
            pid,True,s,{'G':20.0},
            (RecoveryCorridorProjection('G','continuity',True,True,True,1.0,20.0),),
            projection_horizon=30.0
        )

class T:
    def transition(self,s,h):
        nxt=ActualPersistentStateEnvelope(
            s.actor_id,f"s{int(s.time)+1}",s.time+1,s.pp,s.spv,s.avs,s.context
        )
        return Layer1TransitionResult(
            h.episode_id,h.selected_policy_id,s.state_id,nxt,True,{'ok':True}
        )

def build():
    r=PVPPRegistry(); r.register_domain(DomainDefinition('G','g',5.0))
    for a in ('steady','continue'): r.register_action(ActionDefinition(a,a,('G',)))
    r.register_governing_configuration(GoverningConfiguration(0.0))
    r.register_regime_configuration(RegimeConfiguration(1,2,4,100,50,10))
    r.register_constraint_rule(ConstraintRuleDefinition('soft','soft'))
    r.register_graph_instance(GraphInstanceDefinition('i','system',('G',),'active'))
    r.register_graph_transformation(GraphTransformationDefinition(
        'cont','i','i','continuation',('G',),'reachable','continue',('continuation',)
    ))
    r.register_sigma_order(SigmaOrderDefinition('graph:cont',1))
    rt=PVPPRuntime(r,W(),layer1_transition_service=T())
    req=CanonicalDecisionCycleRequest(
        PreliminaryPreservationObject('p','preserve continuity'),
        DomainFrame((DomainFrameTarget('G','continuity'),)),
        ('continuation',),(),('continuation',)
    )
    s=ActualPersistentStateEnvelope('a','s0',0,{}, {}, {}, {})
    return rt,req,s

for n in (10,100,1000,5000):
    vals=[]
    for _ in range(3):
        rt,req,s=build()
        ds=tuple(CanonicalCycleDirective(
            req,True,f'e{i}',1,(ExecutionObservation(f'o{i}',completed=True),)
        ) for i in range(n))
        t0=time.perf_counter()
        out=rt.evaluate_canonical_cycle_sequence(s,ds)
        vals.append((time.perf_counter()-t0)*1000)
        assert out.completed_cycle_count==n
    med=statistics.median(vals)
    print(f"{n}: total {med:.3f} ms; per-cycle {med/n:.4f} ms")
