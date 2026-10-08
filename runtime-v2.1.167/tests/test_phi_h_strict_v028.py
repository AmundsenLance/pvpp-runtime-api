import sys, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class StrictWorld:
    def __init__(self, pressure_scale=1.0, expected_pressure_sensitivity=1.0):
        self.pressure_scale=pressure_scale
        self.expected_pressure_sensitivity=expected_pressure_sensitivity
    def perceive(self,s): return s
    def domain_value(self,s,d):
        return s.powers[d].value
    def project(self,s,a):
        # steady continuation loses one unit in every domain
        powers={k:ProductivePowerState(k,v.value-1.0) for k,v in s.powers.items()}
        return ActionProjection(a.id,WorldState(s.time+1,powers),True)
    def pressure_factors(self,state,domain_id,baseline_drift):
        margin=state.powers[domain_id].value
        return PressureFactors(domain_id,margin,baseline_drift,0.2,0.3,0.1,{"mode":"test"})
    def pressure_value(self,domain_id,factors):
        # explicit domain-local bounded form with monotonic compression.
        margin_term=1.0/(1.0+max(factors.margin,0.0))
        return self.pressure_scale*(margin_term + max(0.0,-factors.local_trajectory)
               + factors.discontinuity + factors.persistence + factors.propagation)
    def expected_deterioration(self,state,domain_id,baseline_drift,pressure_value,pressure_factors):
        # Pressure modifies expected deterioration, not current state.
        return baseline_drift - self.expected_pressure_sensitivity*0.1*pressure_value
    def execute(self,state,action_id):
        raise NotImplementedError

def runtime(world=None):
    r=PVPPRegistry()
    r.register_domain(DomainDefinition("A","A",0))
    r.register_domain(DomainDefinition("B","B",0))
    r.register_action(ActionDefinition("steady","steady",("A","B")))
    r.register_gov_config= None
    r.register_governing_configuration(GoverningConfiguration(epsilon_h=0.0))
    r.register_regime_configuration(RegimeConfiguration(
        tau_h_existential=1.0,tau_h_survival=3.0,tau_h_stabilization=8.0,
        tau_phi_existential=4.0,tau_phi_survival=2.0,tau_phi_stabilization=1.0
    ))
    r.register_horizon_configuration(HorizonConfiguration(epsilon_deterioration=1e-9))
    return PVPPRuntime(r,world or StrictWorld())

def state(a=10.0,b=20.0):
    return WorldState(0,{
        "A":ProductivePowerState("A",a),
        "B":ProductivePowerState("B",b),
    })

def test_strict_phi_preserves_domain_vector_and_components():
    rt=runtime()
    phi=rt.evaluate_pressure_field(state())
    assert tuple(x.domain_id for x in phi.domain_results)==("A","B")
    assert phi.domain_results[0].factors.margin==10.0
    assert phi.domain_results[0].factors.local_trajectory==-1.0
    assert phi.pressures["A"] > phi.pressures["B"]

def test_phi_margin_must_match_ppp_distance_to_threshold():
    class Bad(StrictWorld):
        def pressure_factors(self,state,domain_id,baseline_drift):
            x=super().pressure_factors(state,domain_id,baseline_drift)
            return PressureFactors(domain_id,x.margin+1,x.local_trajectory)
    rt=runtime(Bad())
    try:
        rt.evaluate_pressure_field(state())
        assert False
    except ValueError as e:
        assert "perceived value minus viability boundary" in str(e)

def test_phi_monotonic_compression_validator_passes_good_mapping():
    rt=runtime()
    ref=PressureFactors("A",10.0,-1.0,0.2,0.3,0.1,{})
    a=rt.validate_pressure_invariants("A",ref,(10.0,5.0,1.0,0.1))
    assert a.valid is True
    assert all(y>=x for x,y in zip(a.pressures,a.pressures[1:]))

def test_phi_monotonic_compression_validator_rejects_reversed_mapping():
    class Reversed(StrictWorld):
        def pressure_value(self,domain_id,factors):
            return factors.margin
    rt=runtime(Reversed())
    ref=PressureFactors("A",10.0,-1.0)
    a=rt.validate_pressure_invariants("A",ref,(10.0,5.0,1.0,0.1))
    assert a.valid is False
    assert any("monotonic compression violated" in v for v in a.violations)

def test_h_consumes_phi_through_expected_deterioration():
    low=runtime(StrictWorld(pressure_scale=0.5))
    high=runtime(StrictWorld(pressure_scale=2.0))
    h_low=low.evaluate_collapse_horizons(state()).horizons["A"]
    h_high=high.evaluate_collapse_horizons(state()).horizons["A"]
    assert h_high < h_low

def test_h_does_not_modify_current_perceived_state():
    s=state()
    rt=runtime()
    before=s.powers["A"].value
    rt.evaluate_collapse_horizons(s)
    assert s.powers["A"].value==before

def test_horizon_increases_with_margin_when_expected_deterioration_is_fixed():
    class Fixed(StrictWorld):
        def expected_deterioration(self,state,domain_id,baseline_drift,pressure_value,pressure_factors):
            return -2.0
    rt=runtime(Fixed())
    h1=rt.evaluate_collapse_horizons(state(a=4,b=20)).horizons["A"]
    h2=rt.evaluate_collapse_horizons(state(a=8,b=20)).horizons["A"]
    assert h2 > h1

def test_pressure_never_changes_g_membership_when_h_is_held_fixed():
    rt=runtime()
    hs={"A":5.0,"B":10.0}
    g1=rt.identify_governing_domains(hs)
    # Changing Phi has no parameter path into G.
    rt.world.pressure_scale=100000.0
    g2=rt.identify_governing_domains(hs)
    assert g1.governing_domain_ids==g2.governing_domain_ids==("A",)

def test_regime_can_escalate_from_governing_pressure_without_redefining_g():
    rt=runtime(StrictWorld(pressure_scale=3.0,expected_pressure_sensitivity=0.0))
    perceived,domains,hs,g=rt._assess_domains(state(a=20,b=30))
    assert g=={"A"}
    # Horizon is long, but high represented pressure can refine posture.
    reg=rt.classify_regime(domains,hs,g)
    assert reg.regime in {"Stabilization","Survival","Existential"}
    assert reg.governing_domain_ids==("A",)

def test_legacy_host_still_uses_compatibility_phi_h_path():
    class Legacy:
        def perceive(self,s): return s
        def domain_value(self,s,d): return s.powers[d].value
        def project(self,s,a):
            return ActionProjection(a.id,WorldState(1,{
                "A":ProductivePowerState("A",9),
                "B":ProductivePowerState("B",19),
            }),True)
        def execute(self,s,a): raise NotImplementedError
    rt=runtime(Legacy())
    perceived,domains,hs,g=rt._assess_domains(state())
    assert domains["A"].pressure > domains["B"].pressure
    assert hs["A"]==10.0
