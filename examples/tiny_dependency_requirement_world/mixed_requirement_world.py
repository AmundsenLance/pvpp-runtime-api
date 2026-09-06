from pvpp_runtime import ActionProjection, ExecutionResult, ProductivePowerState, WorldState


class MixedRequirementWorld:
    """Five governing domains for (A OR B) AND C -> D with downstream D -> E."""

    def perceive(self, state):
        return state

    def domain_value(self, state, domain_id):
        return state.power_value(domain_id.lower())

    def project(self, state, action):
        powers = dict(state.powers)
        vals = {d: state.power_value(d.lower()) for d in ("A", "B", "C", "D", "E")}
        if action.id == "steady":
            for d in vals:
                vals[d] -= 10.0
        elif action.id == "keep_a_c":
            vals.update(A=50.0, B=40.0, C=50.0, D=60.0, E=60.0)
        elif action.id == "keep_b_c":
            vals.update(A=40.0, B=50.0, C=50.0, D=60.0, E=60.0)
        elif action.id == "lose_ab_keep_c":
            vals.update(A=40.0, B=40.0, C=50.0, D=60.0, E=60.0)
        elif action.id == "keep_a_lose_c":
            vals.update(A=50.0, B=40.0, C=40.0, D=60.0, E=60.0)
        elif action.id == "lose_ab_c":
            vals.update(A=40.0, B=40.0, C=40.0, D=60.0, E=60.0)
        for d, v in vals.items():
            powers[d.lower()] = ProductivePowerState(d.lower(), v)
        return ActionProjection(action.id, WorldState(state.time, powers, dict(state.metadata)), True)

    def project_policy(self, state, action_ids):
        if not action_ids:
            return ActionProjection("policy:empty", state, True)
        return self.project(state, type("A", (), {"id": action_ids[0]})())

    def execute(self, state, action_id):
        pr = self.project(state, type("A", (), {"id": action_id})())
        return ExecutionResult(action_id, pr.next_state, pr.feasible, pr.reasons)
