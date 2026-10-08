
import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass

def build(n):
    r=PVPPRegistry()
    r.register_domain(DomainDefinition('G','g',0))
    r.register_action(ActionDefinition('steady','steady',('G',)))
    # One continuation plus n independent two-step staged compositions.
    r.register_graph_instance(GraphInstanceDefinition('base','state',('G',),'available'))
    r.register_action(ActionDefinition('cont','cont',('G',)))
    r.register_graph_transformation(GraphTransformationDefinition(
        'cont','base','base','continuation',('G',),'reachable','cont',('continuation',),
        structural_effect='continue'
    ))
    for i in range(n):
        s0=f's{i}a'; s1=f's{i}b'; s2=f's{i}c'
        r.register_graph_instance(GraphInstanceDefinition(s0,'state',('G',),'available'))
        r.register_graph_instance(GraphInstanceDefinition(s1,'state',('G',),'available'))
        r.register_graph_instance(GraphInstanceDefinition(s2,'state',('G',),'available'))
        a1=f'a{i}1'; a2=f'a{i}2'
        r.register_action(ActionDefinition(a1,a1,('G',)))
        r.register_action(ActionDefinition(a2,a2,('G',)))
        t1=f't{i}1'; t2=f't{i}2'
        r.register_graph_transformation(GraphTransformationDefinition(
            t1,s0,s1,'structural_reconfiguration',('G',),'reachable',a1,(f'path{i}',),
            structural_effect='stage one'
        ))
        r.register_graph_transformation(GraphTransformationDefinition(
            t2,s1,s2,'structural_reconfiguration',('G',),'reachable',a2,(f'path{i}',),
            structural_effect='stage two'
        ))
        r.register_graph_composition(GraphCompositionDefinition(
            f'c{i}',(t1,t2),'structural_reconfiguration',('G',),(f'path{i}',),
            recovery_relevance='staged recovery',distinctness_justification='distinct staged path'
        ))
    return PVPPRuntime(r,W())

po=PreliminaryPreservationObject('p','preserve governing function')
for n in (100,1000,5000,10000):
    rt=build(n)
    vals=[]
    for _ in range(5):
        t0=time.perf_counter()
        g=rt.construct_graph(po,'Survival',('G',),required_family_ids=('continuation',),
                             config=GraphConstructionConfig(max_seeds=3*n+10))
        vals.append((time.perf_counter()-t0)*1000)
        assert g.status=='PASS'
    print(f'{n}: {statistics.median(vals):.3f} ms')
