from pvpp_runtime import WorldState, ProductivePowerState, ExecutionResult
from pvpp_runtime.models import ActionProjection

class TinyCropWorld:
    consumption=10.0
    def perceive(self,state): return state
    def domain_value(self,state,did):
        if did=="F": return state.power_value("food_stock")
        if did=="L": return state.power_value("labor_available")
        raise KeyError(did)
    def project(self,state,action):
        food=state.power_value("food_stock"); stage=state.metadata.get("crop_stage","none")
        if action.id=="steady": nf,ns=food-10,stage
        elif action.id=="plant":
            if stage!="none": return ActionProjection(action.id,state,False,("crop already active",))
            nf,ns=food-10,"planted"
        elif action.id=="maintain_crop":
            if stage!="planted": return ActionProjection(action.id,state,False,("requires planted crop",))
            nf,ns=food-10,"maintained"
        elif action.id=="harvest_crop":
            if stage!="maintained": return ActionProjection(action.id,state,False,("requires maintained crop",))
            nf,ns=food+30,"none"
        else: return ActionProjection(action.id,state,False,("unknown action",))
        nxt=WorldState(state.time+1,{"food_stock":ProductivePowerState("food_stock",max(0,nf)),"labor_available":ProductivePowerState("labor_available",10,10)}, {"crop_stage":ns})
        return ActionProjection(action.id,nxt,True)
    def execute(self,state,action_id):
        from pvpp_runtime.models import ActionDefinition
        pr=self.project(state,ActionDefinition(action_id,action_id,("F","L")))
        return ExecutionResult(action_id,pr.next_state,pr.feasible,pr.reasons)
