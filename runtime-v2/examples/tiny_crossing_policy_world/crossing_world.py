from __future__ import annotations
from pvpp_runtime import ActionProjection, ExecutionResult, ProductivePowerState, WorldState

class CrossingPolicyWorld:
    """Two governing domains with crossing same-period discretionary consequences."""
    def perceive(self, state):
        return state

    def domain_value(self, state, domain_id):
        if domain_id == "F":
            return state.power_value("food")
        if domain_id == "M":
            return state.power_value("material")
        if domain_id == "K":
            return state.power_value("knowledge")
        raise KeyError(domain_id)

    def project(self, state, action):
        powers=dict(state.powers)
        food=state.power_value("food")
        material=state.power_value("material")
        if action.id == "steady":
            food -= 10.0
            material -= 10.0
        elif action.id == "favor_food":
            food += 20.0
            material += 15.0
        elif action.id == "favor_material":
            food += 15.0
            material += 20.0
        powers["food"]=ProductivePowerState("food",food)
        powers["material"]=ProductivePowerState("material",material)
        return ActionProjection(action.id,WorldState(state.time,powers,dict(state.metadata)),True)

    def project_policy(self,state,action_ids):
        powers=dict(state.powers)
        food=state.power_value("food")
        material=state.power_value("material")
        for aid in action_ids:
            if aid == "favor_food":
                food += 20.0; material += 15.0
            elif aid == "favor_material":
                food += 15.0; material += 20.0
        powers["food"]=ProductivePowerState("food",food)
        powers["material"]=ProductivePowerState("material",material)
        return ActionProjection("policy:"+"+".join(action_ids),WorldState(state.time,powers,dict(state.metadata)),True)

    def execute(self,state,action_id):
        pr=self.project(state,type("A",(),{"id":action_id})())
        return ExecutionResult(action_id,pr.next_state,pr.feasible,pr.reasons)
