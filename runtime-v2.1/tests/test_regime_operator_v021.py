import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))

from pvpp_runtime import *
from pvpp_runtime.models import DomainAssessment, ActionProjection

def config(**kw):
    base=dict(
        tau_h_existential=1.0, tau_h_survival=3.0, tau_h_stabilization=7.0,
        tau_phi_existential=0.9, tau_phi_survival=0.6, tau_phi_stabilization=0.3,
        tau_m_survival=3, tau_m_stabilization=2,
        tau_h_mult_survival=2.5, tau_h_mult_stabilization=6.0,
        delta_h_escalation=0.5, delta_h_deescalation=2.0,
    )
    base.update(kw); return RegimeConfiguration(**base)

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return s.power_value(d)
    def project(self,s,a):
        return ActionProjection(a.id,s,True)

def runtime(n=4):
    reg=PVPPRegistry()
    for i in range(n): reg.register_domain(DomainDefinition(f'D{i}',f'd{i}',0))
    reg.register_action(ActionDefinition('steady','steady',()))
    reg.register_regime_configuration(config())
    return PVPPRuntime(reg,W())

def da(horizons, pressures):
    return {d:DomainAssessment(d,1.0,pressures[d],horizons[d],True,0.0) for d in horizons}

def test_ordered_horizon_mapping():
    rt=runtime()
    for h,expected in [(0.5,'Existential'),(2.0,'Survival'),(5.0,'Stabilization'),(10.0,'Mission')]:
        hs={'D0':h}; ds=da(hs,{'D0':0.1})
        assert rt.classify_regime(ds,hs,{'D0'}).regime==expected

def test_pressure_can_escalate_posture_without_scalar_aggregation():
    rt=runtime()
    hs={'D0':10.0,'D1':12.0}; ps={'D0':0.65,'D1':0.2}
    a=rt.classify_regime(da(hs,ps),hs,{'D0','D1'})
    assert a.regime=='Survival'
    assert a.trigger=='governing_max_pressure_survival'
    assert a.governing_max_pressure==0.65

def test_contextual_interruption_forces_existential():
    rt=runtime()
    hs={'D0':100.0}; ps={'D0':0.0}
    a=rt.classify_regime(da(hs,ps),hs,{'D0'},contextual_interruption=True)
    assert a.regime=='Existential'
    assert a.trigger=='contextual_interruption'

def test_governing_multiplicity_is_recorded_without_hidden_aggregation():
    rt=runtime()
    hs={'D0':5.5,'D1':5.8,'D2':100.0}; ps={d:0.1 for d in hs}
    a=rt.classify_regime(da(hs,ps),hs,{'D0','D1'})
    assert a.regime=='Stabilization'
    assert a.governing_multiplicity==2
    assert a.trigger=='governing_min_horizon_stabilization'

def test_hysteresis_delays_deescalation_but_never_suppresses_existential():
    rt=runtime()
    hs={'D0':8.0}; ps={'D0':0.1}
    previous=PreviousRegimeState('Survival',7.0)
    a=rt.classify_regime(da(hs,ps),hs,{'D0'},previous=previous)
    assert a.base_regime=='Mission'
    assert a.regime=='Survival'
    assert a.hysteresis_applied is True

    hs2={'D0':0.5}
    b=rt.classify_regime(da(hs2,ps),hs2,{'D0'},previous=previous)
    assert b.regime=='Existential'
    assert b.hysteresis_applied is False

def test_invalid_threshold_order_is_rejected():
    reg=PVPPRegistry()
    bad=config(tau_h_existential=5.0,tau_h_survival=3.0)
    try:
        reg.register_regime_configuration(bad)
        assert False
    except ValueError:
        pass

def test_regime_consumes_g_and_does_not_expand_it():
    rt=runtime()
    hs={'D0':2.0,'D1':0.1}; ps={'D0':0.1,'D1':1.0}
    a=rt.classify_regime(da(hs,ps),hs,{'D0'})
    assert a.governing_domain_ids==('D0',)
    assert a.regime=='Survival'

def test_regime_requires_visible_configuration_and_nonempty_g():
    reg=PVPPRegistry(); reg.register_domain(DomainDefinition('D','d',0)); reg.register_action(ActionDefinition('steady','steady',()))
    rt=PVPPRuntime(reg,W())
    hs={'D':2.0}; ds=da(hs,{'D':0.1})
    try: rt.classify_regime(ds,hs,{'D'}); assert False
    except ValueError: pass
    reg.register_regime_configuration(config())
    try: rt.classify_regime(ds,hs,set()); assert False
    except ValueError: pass

def test_ordinary_assessment_surfaces_typed_regime_when_configured():
    reg=PVPPRegistry()
    reg.register_domain(DomainDefinition('D','d',0,governing_horizon=20))
    reg.register_power(ProductivePowerDefinition('D','D','p'))
    reg.register_action(ActionDefinition('steady','steady',('D',)))
    reg.register_regime_configuration(config())
    class DriftWorld(W):
        def domain_value(self,s,d): return s.power_value('D')
        def project(self,s,a):
            v=s.power_value('D')-1.0
            return ActionProjection(a.id,WorldState(s.time+1,{'D':ProductivePowerState('D',v)}),True)
    rt=PVPPRuntime(reg,DriftWorld())
    a=rt.assess(WorldState(0,{'D':ProductivePowerState('D',2.0)}),select=False)
    assert a.regime_assessment is not None
    assert a.regime == 'Survival'
    assert a.regime_assessment.governing_domain_ids == ('D',)
