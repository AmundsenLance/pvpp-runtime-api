from pvpp_runtime import ActionProjection, ExecutionResult, ProductivePowerState, WorldState

class BranchingDependencyWorld:
    """Four governing domains with a branching and converging policy consequence graph."""
    def perceive(self, state):
        return state

    def domain_value(self, state, domain_id):
        return state.power_value(domain_id.lower())

    def project(self, state, action):
        powers=dict(state.powers)
        vals={d:state.power_value(d.lower()) for d in ("A","B","C","D")}
        if action.id == "steady":
            for d in vals:
                vals[d]-=10.0
        elif action.id == "root_secure":
            vals["A"]+=20.0
            vals["B"]+=17.5
            vals["C"]+=17.5
            vals["D"]+=15.0
        elif action.id == "branch_boost":
            vals["A"]+=15.0
            vals["B"]+=20.0
            vals["C"]+=20.0
            vals["D"]+=20.0
        for d,v in vals.items():
            powers[d.lower()]=ProductivePowerState(d.lower(),v)
        return ActionProjection(action.id,WorldState(state.time,powers,dict(state.metadata)),True)

    def project_policy(self,state,action_ids):
        s=state
        # Each candidate in this world contains one discretionary action.
        for aid in action_ids:
            if aid == "steady":
                continue
            return self.project(s,type("A",(),{"id":aid})())
        return ActionProjection("policy:steady",state,True)

    def execute(self,state,action_id):
        pr=self.project(state,type("A",(),{"id":action_id})())
        return ExecutionResult(action_id,pr.next_state,pr.feasible,pr.reasons)
