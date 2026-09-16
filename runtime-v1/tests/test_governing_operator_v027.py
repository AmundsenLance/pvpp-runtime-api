import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class W:
    def perceive(self,s): return s
    def domain_value(self,s,d): return 1.0
    def project(self,s,a): return ActionProjection(a.id,s,True)

def rt(domains=('A','B','C','D'),epsilon=0.0):
    r=PVPPRegistry()
    for d in domains: r.register_domain(DomainDefinition(d,d,0))
    r.register_action(ActionDefinition('steady','steady',tuple(domains)))
    r.register_governing_configuration(GoverningConfiguration(epsilon))
    return PVPPRuntime(r,W()),r

def test_minimum_horizon_domain_is_always_seeded_and_g_nonempty():
    runtime,_=rt()
    g=runtime.identify_governing_domains({'A':5,'B':9,'C':7,'D':11})
    assert g.seed_domain_ids==('A',)
    assert g.governing_domain_ids==('A',)

def test_epsilon_h_includes_only_near_minimum_horizon_domains():
    runtime,_=rt(epsilon=1.5)
    g=runtime.identify_governing_domains({'A':5,'B':6.4,'C':6.6,'D':10})
    assert g.seed_domain_ids==('A','B')
    assert g.governing_domain_ids==('A','B')

def test_hidden_recovery_dependency_expands_g():
    runtime,r=rt()
    r.register_recovery_necessity(RecoveryNecessityDefinition('B_for_A','B','A'))
    g=runtime.identify_governing_domains({'A':2,'B':100,'C':100,'D':100})
    assert g.governing_domain_ids==('A','B')
    assert g.added_by_dependency_ids==('B',)
    assert g.provenance['B']==('B_for_A','A')

def test_dependency_closure_is_transitive():
    runtime,r=rt()
    r.register_recovery_necessity(RecoveryNecessityDefinition('B_for_A','B','A'))
    r.register_recovery_necessity(RecoveryNecessityDefinition('C_for_B','C','B'))
    r.register_recovery_necessity(RecoveryNecessityDefinition('D_for_C','D','C'))
    g=runtime.identify_governing_domains({'A':1,'B':9,'C':9,'D':9})
    assert g.governing_domain_ids==('A','B','C','D')

def test_irrelevant_helpful_domain_is_not_inflated_into_g():
    runtime,r=rt()
    r.register_recovery_necessity(RecoveryNecessityDefinition('B_for_A','B','A'))
    g=runtime.identify_governing_domains({'A':1,'B':10,'C':1_000,'D':1_000})
    assert g.governing_domain_ids==('A','B')
    assert 'C' not in g.governing_domain_ids

def test_pressure_cannot_change_g_membership():
    runtime,r=rt()
    r.register_recovery_necessity(RecoveryNecessityDefinition('B_for_A','B','A'))
    horizons={'A':1,'B':10,'C':100,'D':100}
    x=runtime.identify_governing_domains(horizons)
    # G takes horizons and registered recovery necessity only; no pressure input exists.
    y=runtime.identify_governing_domains(dict(horizons))
    assert x.governing_domain_ids==y.governing_domain_ids==('A','B')

def test_tied_minimum_horizons_all_seed():
    runtime,_=rt()
    g=runtime.identify_governing_domains({'A':3,'B':3,'C':8,'D':9})
    assert g.seed_domain_ids==('A','B')

def test_immediate_collapse_domain_is_seeded():
    runtime,_=rt()
    g=runtime.identify_governing_domains({'A':0,'B':5,'C':8,'D':9})
    assert 'A' in g.governing_domain_ids

def test_all_infinite_horizons_still_yield_nonempty_deterministic_g():
    runtime,_=rt()
    g=runtime.identify_governing_domains({'A':float('inf'),'B':float('inf'),'C':float('inf'),'D':float('inf')})
    assert g.governing_domain_ids==('A','B','C','D')

def test_nan_horizon_rejected():
    runtime,_=rt()
    try:
        runtime.identify_governing_domains({'A':1,'B':float('nan'),'C':3,'D':4})
        assert False
    except ValueError as e:
        assert 'NaN' in str(e)

def test_recovery_necessity_cycle_terminates_without_duplicate_inflation():
    runtime,r=rt()
    r.register_recovery_necessity(RecoveryNecessityDefinition('B_for_A','B','A'))
    r.register_recovery_necessity(RecoveryNecessityDefinition('A_for_B','A','B'))
    g=runtime.identify_governing_domains({'A':1,'B':9,'C':9,'D':9})
    assert g.governing_domain_ids==('A','B')
    assert len(g.added_by_dependency_ids)==1

def test_canonical_g_ignores_legacy_domain_governing_horizon_when_configured():
    r=PVPPRegistry()
    r.register_domain(DomainDefinition('A','A',0,governing_horizon=1000))
    r.register_domain(DomainDefinition('B','B',0,governing_horizon=0.1))
    r.register_action(ActionDefinition('steady','steady',('A','B')))
    r.register_governing_configuration(GoverningConfiguration(0.0))
    runtime=PVPPRuntime(r,W())
    g=runtime.identify_governing_domains({'A':10,'B':1})
    assert g.governing_domain_ids==('B',)
