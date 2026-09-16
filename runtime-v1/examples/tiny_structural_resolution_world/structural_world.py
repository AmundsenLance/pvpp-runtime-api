from __future__ import annotations
from dataclasses import replace
from pvpp_runtime import *
from pvpp_runtime.models import ActionProjection

class StructuralResolutionWorld:
    """Two crossing productive policies, one excluded by a represented hard constraint."""
    def perceive(self, state):
        return state

    def domain_value(self, state, domain_id):
        return state.power_value({"F":"food","M":"material"}[domain_id])

    def project(self, state, action):
        f=state.power_value("food")
        m=state.power_value("material")
        if action.id == "steady":
            nf,nm=f-10,m-10
        elif action.id == "favor_food":
            nf,nm=f+20,m+15
        elif action.id == "favor_material":
            # This action is feasible alone; the policy-level constraint is evaluated
            # by project_policy because the prohibited combination is contextual.
            nf,nm=f+15,m+20
        else:
            return ActionProjection(action.id,state,False,("unknown action",))
        return ActionProjection(action.id, WorldState(state.time+1,{
            "food":ProductivePowerState("food",nf),
            "material":ProductivePowerState("material",nm),
        },dict(state.metadata)), True)

    def project_policy(self, state, action_ids):
        ids=tuple(action_ids)
        if "favor_material" in ids and state.metadata.get("material_policy_blocked",False):
            return ActionProjection("policy", state, False, ("binding host constraint prohibits favor_material in the current configuration",))
        # Same-period policy: apply one baseline period, then action effects once.
        f=state.power_value("food")-10
        m=state.power_value("material")-10
        if "favor_food" in ids:
            f += 30; m += 25
        if "favor_material" in ids:
            f += 25; m += 30
        return ActionProjection("policy", WorldState(state.time+1,{
            "food":ProductivePowerState("food",f),
            "material":ProductivePowerState("material",m),
        },dict(state.metadata)), True)


def build_runtime(block_material=True):
    reg=PVPPRegistry()
    reg.register_domain(DomainDefinition("F","food continuity",0,3))
    reg.register_domain(DomainDefinition("M","material continuity",0,3))
    reg.register_power(ProductivePowerDefinition("food","F","food stock"))
    reg.register_power(ProductivePowerDefinition("material","M","material stock"))
    reg.register_action(ActionDefinition("steady","no discretionary action",("F","M")))
    reg.register_action(ActionDefinition("favor_food","food-favoring restoration",("F","M"),{"policy_role":"discretionary"}))
    reg.register_action(ActionDefinition("favor_material","material-favoring restoration",("F","M"),{"policy_role":"discretionary"}))
    world=StructuralResolutionWorld()
    rt=PVPPRuntime(reg,world)
    state=WorldState(0,{"food":ProductivePowerState("food",25),"material":ProductivePowerState("material",25)},
                     {"material_policy_blocked":block_material})
    return rt,state
