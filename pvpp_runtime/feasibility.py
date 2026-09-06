from __future__ import annotations
from itertools import combinations
from typing import Mapping
from .models import ActiveRecoveryCorridor, CapacityCalendar, CorridorFeasibilityReport, ScheduledRecoveryStep


def _demand_for_action(registry, action_id: str) -> Mapping[str, float]:
    action = registry.actions[action_id]
    raw = action.metadata.get("capacity_demands", {})
    return {str(k): float(v) for k, v in raw.items()}


def _can_fit(used, cap, demands):
    return all(used.get(r, 0.0) + amt <= cap.get(r, 0.0) + 1e-12 for r, amt in demands.items())


def _schedule_subset(registry, corridors, calendar: CapacityCalendar, now: float):
    # Exact small-prototype search. Each remaining action is a one-period step.
    ids = tuple(sorted(c.plan_id for c in corridors))
    by_id = {c.plan_id: c for c in corridors}
    positions = {cid: 0 for cid in ids}
    steps = []
    periods = tuple(sorted(calendar.capacities))
    demand_cache={}
    def demand_for(aid):
        if aid not in demand_cache:
            demand_cache[aid]=_demand_for_action(registry,aid)
        return demand_cache[aid]

    def done():
        return all(positions[cid] >= len(by_id[cid].remaining_actions) for cid in ids)

    # Memoize failed search states. A state is completely determined by the
    # calendar period being considered and the next action position of each
    # corridor. The path used to reach that state does not affect future
    # feasibility, so revisiting it is redundant.
    dead_states=set()

    def rec(period_index):
        if done():
            return tuple(steps)
        if period_index >= len(periods):
            return None

        state=(period_index, tuple(positions[cid] for cid in ids))
        if state in dead_states:
            return None

        # Cheap horizon/deadline pruning. Every unfinished one-period step
        # must occupy some remaining calendar period no later than its
        # corridor deadline. If a corridor has more remaining ordered steps
        # than eligible periods, this state cannot succeed.
        remaining_periods=periods[period_index:]
        unfinished=[]
        for cid in ids:
            c=by_id[cid]
            remaining_steps=len(c.remaining_actions)-positions[cid]
            if remaining_steps <= 0:
                continue
            unfinished.append(cid)
            eligible=sum(1 for p in remaining_periods if now+p <= c.deadline+1e-12)
            if remaining_steps > eligible:
                dead_states.add(state)
                return None

        # Cumulative resource/deadline bound. For every represented deadline
        # cutoff, all remaining demand belonging to corridors due by that
        # cutoff must fit inside the remaining capacity available by then.
        # This is only a necessary feasibility condition, so it cannot reject
        # a schedule that could actually work, but it eliminates large
        # families of impossible backtracking states very cheaply.
        cutoffs=sorted({by_id[cid].deadline for cid in unfinished})
        for cutoff in cutoffs:
            demand={}
            for cid in unfinished:
                c=by_id[cid]
                if c.deadline > cutoff+1e-12:
                    continue
                for aid in c.remaining_actions[positions[cid]:]:
                    for r,a in demand_for(aid).items():
                        demand[r]=demand.get(r,0.0)+a
            if not demand:
                continue
            capacity={r:0.0 for r in demand}
            for rp in remaining_periods:
                if now+rp > cutoff+1e-12:
                    continue
                vals=calendar.capacities[rp]
                for r in capacity:
                    capacity[r]+=float(vals.get(r,0.0))
            if any(demand[r] > capacity.get(r,0.0)+1e-12 for r in demand):
                dead_states.add(state)
                return None

        p = periods[period_index]
        cap = calendar.capacities[p]
        available = [cid for cid in ids if positions[cid] < len(by_id[cid].remaining_actions)]

        # Enumerate only capacity-feasible same-period corridor choices. The
        # earlier implementation generated every subset and rejected almost
        # all of them afterward; with many corridors and tight capacity that
        # created a 2^N cost even for trivially schedulable cases.
        def iter_choices(i=0, chosen=(), used=None):
            # Include-first lazy traversal prefers fuller use of the current
            # period but does not materialize the power set. This matters when
            # capacity is generous: the all-in choice can succeed immediately.
            if used is None: used={}
            if i >= len(available):
                yield chosen
                return
            cid=available[i]
            c=by_id[cid]
            if now+p <= c.deadline+1e-12:
                aid=c.remaining_actions[positions[cid]]
                dem=demand_for(aid)
                if _can_fit(used,cap,dem):
                    nxt=dict(used)
                    for r,a in dem.items(): nxt[r]=nxt.get(r,0.0)+a
                    yield from iter_choices(i+1,chosen+(cid,),nxt)
            yield from iter_choices(i+1,chosen,used)

        for chosen in iter_choices():
            local_demands={}; local=[]; valid=True
            for cid in chosen:
                c=by_id[cid]
                aid=c.remaining_actions[positions[cid]]
                dem=demand_for(aid)
                if not _can_fit(local_demands,cap,dem):
                    valid=False; break
                for r,a in dem.items(): local_demands[r]=local_demands.get(r,0.0)+a
                local.append((cid,aid,dem))
            if not valid: continue
            for cid,aid,dem in local:
                positions[cid]+=1; steps.append(ScheduledRecoveryStep(p,cid,aid,dem))
            ans=rec(period_index+1)
            if ans is not None: return ans
            for cid,aid,dem in reversed(local):
                positions[cid]-=1; steps.pop()

        dead_states.add(state)
        return None
    return rec(0)


def _deadline_slack(corridors, schedule, now):
    completion={}
    for s in schedule:
        completion[s.corridor_id]=max(completion.get(s.corridor_id, float('-inf')), now+s.period_offset)
    return {c.plan_id: c.deadline-completion[c.plan_id] for c in corridors if c.plan_id in completion}


def _resource_bottlenecks(registry, corridors, calendar, now):
    """Diagnostic necessary-condition check, not an arbitration rule.

    A resource is named when aggregate demand for the corridor subset exceeds the
    aggregate resource capacity available no later than the latest corridor deadline.
    This is intentionally conservative: an infeasible set can exist for ordering/deadline
    reasons even when no aggregate resource bottleneck is identified.
    """
    if not corridors: return ()
    latest=max(c.deadline for c in corridors)
    resources=set(); demand={}
    for c in corridors:
        for aid in c.remaining_actions:
            for r,a in _demand_for_action(registry,aid).items():
                resources.add(r); demand[r]=demand.get(r,0.0)+a
    cap={r:0.0 for r in resources}
    for p,vals in calendar.capacities.items():
        if now+p <= latest+1e-12:
            for r in resources: cap[r]+=float(vals.get(r,0.0))
    return tuple(sorted(r for r in resources if demand.get(r,0.0) > cap.get(r,0.0)+1e-12))



def _residual_capacity(calendar, schedule):
    residual={p:{str(r):float(v) for r,v in vals.items()} for p,vals in calendar.capacities.items()}
    for step in schedule:
        bucket=residual.setdefault(step.period_offset,{})
        for r,a in step.demands.items():
            bucket[r]=float(bucket.get(r,0.0))-float(a)
    return {p:{r:max(0.0,v) for r,v in vals.items()} for p,vals in residual.items()}


def _minimal_infeasible_witness(registry, active, calendar, now):
    """Return one inclusion-minimal infeasible corridor subset.

    Feasibility is monotone under corridor removal for the fixed calendar used
    here: removing obligations cannot make a feasible set infeasible. Starting
    from an already-infeasible set, greedily discard any corridor whose
    removal leaves the remainder infeasible. The fixed point is therefore an
    inclusion-minimal infeasible witness. This avoids exhaustive enumeration
    of every minimal conflict set on the ordinary runtime path.
    """
    current=list(sorted(active, key=lambda c:c.plan_id))
    changed=True
    while changed and len(current)>1:
        changed=False
        for c in tuple(current):
            trial=tuple(x for x in current if x.plan_id != c.plan_id)
            if trial and _schedule_subset(registry,trial,calendar,now) is None:
                current=list(trial)
                changed=True
                break
    return tuple(c.plan_id for c in current)


def _all_minimal_infeasible_sets(registry, active, calendar, now):
    """Exhaustive diagnostic mode retained for small/offline analyses."""
    bad=[]; ids=tuple(sorted(c.plan_id for c in active)); by={c.plan_id:c for c in active}
    bottlenecks={}
    for n in range(1,len(ids)+1):
        for subset in combinations(ids,n):
            if any(set(prev).issubset(subset) for prev in bad):
                continue
            cs=tuple(by[x] for x in subset)
            if _schedule_subset(registry,cs,calendar,now) is None:
                bad.append(subset)
                bottlenecks[subset]=_resource_bottlenecks(registry,cs,calendar,now)
    return tuple(bad), bottlenecks


def assess_joint_feasibility(registry, corridors, calendar: CapacityCalendar, now: float = 0.0, diagnostic_mode: str = "witness"):
    active=tuple(c for c in corridors if c.status=="active" and c.remaining_actions)
    schedule=_schedule_subset(registry,active,calendar,now)
    if schedule is not None:
        return CorridorFeasibilityReport(
            jointly_feasible=True, schedule=schedule,
            deadline_slack=_deadline_slack(active,schedule,now),
            residual_capacity=_residual_capacity(calendar,schedule),
            infeasible_sets_complete=True,
            notes=("all active recovery corridors are jointly schedulable in the supplied prototype capacity calendar",)
        )

    if diagnostic_mode == "all_minimal":
        bad,bottlenecks=_all_minimal_infeasible_sets(registry,active,calendar,now)
        complete=True
        mode_note="all inclusion-minimal infeasible corridor sets were exhaustively enumerated"
    elif diagnostic_mode == "witness":
        witness=_minimal_infeasible_witness(registry,active,calendar,now) if active else ()
        bad=(witness,) if witness else ()
        by={c.plan_id:c for c in active}
        cs=tuple(by[x] for x in witness) if witness else ()
        bottlenecks={witness:_resource_bottlenecks(registry,cs,calendar,now)} if witness else {}
        complete=False
        mode_note="one inclusion-minimal infeasible corridor witness is reported; exhaustive conflict-set enumeration was not run"
    else:
        raise ValueError("diagnostic_mode must be 'witness' or 'all_minimal'")

    return CorridorFeasibilityReport(
        jointly_feasible=False, infeasible_corridor_sets=bad,
        bottleneck_resources=bottlenecks, infeasible_sets_complete=complete,
        notes=("joint restoration set is infeasible under supplied shared capacities/deadlines", mode_note, "no priority or sacrifice rule has been applied")
    )
