import sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pvpp_runtime import *

class W: pass
class T:
    def transition(self,current,handoff):
        return Layer1TransitionResult(
            handoff.episode_id,handoff.selected_policy_id,current.state_id,
            ActualPersistentStateEnvelope(current.actor_id,'s1',current.time+1,
                current.pp,current.spv,current.avs,current.context),
            True,{f'i{i}':True for i in range(N)}
        )

r=PVPPRegistry(); r.register_action(ActionDefinition('steady','steady',()))
state=ActualPersistentStateEnvelope('actor','s0',0.0,{}, {}, {}, {})
handoff=Layer1TransitionHandoff('ep','p','completed',(),(),(),False)
for N in (100,1000,5000,10000,50000):
    service=T(); rt=PVPPRuntime(r,W(),layer1_transition_service=service)
    result=service.transition(state,handoff)
    vals=[]
    for _ in range(9):
        t0=time.perf_counter(); a=rt.validate_layer1_transition_result(state,handoff,result); vals.append((time.perf_counter()-t0)*1000)
        assert a.valid
    print(f'{N}: {statistics.median(vals):.3f} ms')
