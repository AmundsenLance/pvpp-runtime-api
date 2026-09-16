from __future__ import annotations
from pvpp_runtime import ActionProjection, ExecutionResult, ProductivePowerState, WorldState

class DependencyClosureWorld:
    def perceive(self, state):
        return state

    def domain_value(self, state, domain_id):
        return state.power_value(domain_id.lower())

    def project(self, state, action):
        powers=dict(state.powers)
        vals={d: state.power_value(d.lower()) for d in ("A","B","C")}
        if action.id == "steady":
            for d in vals: vals[d] -= 10.0
        elif action.id == "favor_upstream":
            vals["A"] += 25.0; vals["B"] += 25.0; vals["C"] += 15.0
        elif action.id == "favor_downstream":
            vals["A"] += 15.0; vals["B"] += 35.0; vals["C"] += 35.0
        for d,v in vals.items():
            powers[d.lower()]=ProductivePowerState(d.lower(),v)
        return ActionProjection(action.id, WorldState(state.time,powers,dict(state.metadata)), True)

    def project_policy(self, state, action_ids):
        s=state
        for aid in action_ids:
            if aid == "steady":
                continue
            s=self.project(s, type("A",(),{"id":aid})()).next_state
        return ActionProjection("policy:"+"+".join(action_ids), s, True)

    def execute(self,state,action_id):
        pr=self.project(state,type("A",(),{"id":action_id})())
        return ExecutionResult(action_id,pr.next_state,pr.feasible,pr.reasons)
