"""Bounded episodic selection of small, capacity-aware meter adjustments.

All estimates use completed observations. Selection never calls evaluate().
H2 is the matched no-memory policy, with the same meter candidates as A4.
"""
import math
from collections import defaultdict
from agent.adaptive_memory import AdaptiveMemory, context, regime
from eval.simulator import decision_for

HEADROOMS = (0.0, 0.1, 0.3)  # Mbps; fixed before fresh held-out evaluation


def meter_decision(summary, demand, headroom=.1, reason='Capacity-aware meter'):
    s=summary['simulation'];e=s['elephant_mbps']
    # At most 20% of this flow may be removed. Round UP to preserve that bound.
    cap=max(.8*e, s['capacity_mbps']-s['primary_background_mbps']-headroom, .512)
    cap=min(e,cap)
    d=decision_for('rate_limit',demand,reason)
    d.rate_limit_kbps=math.ceil(cap*1000)
    return d


def capacity_policy(summary,demand):
    s=summary['simulation']
    if s['primary_background_mbps']+s['elephant_mbps']<=s['capacity_mbps']:
        return decision_for('no_op',demand,'Current primary demand fits capacity')
    if s['alternate_background_mbps']+s['elephant_mbps']<=.9*s['capacity_mbps']:
        return decision_for('reroute',demand,'Alternate path satisfies the 90% safety ceiling')
    return meter_decision(summary,demand)


def parameter_key(record):
    return record.get('meter_headroom', .1)


class LossAwareMemory(AdaptiveMemory):
    limit=128

    def add_record(self,cycle,state_summary,action,params,reward,reflection):
        if not self.enabled:return
        # Store the actual parameter, rather than only the action label.
        s=state_summary['simulation'];cap=params.get('rate_limit_kbps')
        feasible=[(abs(meter_decision(state_summary,s,h).rate_limit_kbps-(cap or 0)),h) for h in HEADROOMS]
        from datetime import datetime,timezone
        self._records.append(dict(cycle=cycle,timestamp=datetime.now(timezone.utc).isoformat(),state_summary=state_summary,
            action=action,params=params,reward=reward,reflection=reflection,context_v3=context(state_summary),
            meter_headroom=min(feasible)[1] if action=='rate_limit' else None))
        self._prune()
        if self.autosave:self._save()

    def _prune(self):
        cells=defaultdict(list)
        for r in self._records:
            if 'context_v3' not in r:r['context_v3']=context(r['state_summary'])
            v=r['context_v3']
            cells[(r['action'],parameter_key(r),regime(v),tuple(round(x/.12) for x in v[:3]))].append(r)
        self._records=sorted([r for cell in cells.values() for r in cell[-6:]],key=lambda r:r['cycle'])[-self.limit:]

    def meter_estimates(self,state,cycle):
        q=context(state);candidates=defaultdict(list)
        for r in self._records:
            if r['cycle']>=cycle or r['action']!='rate_limit':continue
            v=r.get('context_v3')
            if v is None:v=context(r['state_summary'])
            delta=[abs(a-b) for a,b in zip(q,v)]
            if regime(q)!=regime(v) or max(delta[:6])>.12 or max(delta[6:])>.51:continue
            distance=sum(x*x for x in delta[:6])+.08*sum(x*x for x in delta[6:])
            w=math.exp(-distance/.02)*math.exp(-(cycle-r['cycle'])/120)
            candidates[parameter_key(r)].append((distance,w,r))
        scores={};used=[]
        for h,entries in candidates.items():
            entries=sorted(entries,key=lambda x:x[0])[:6]
            weight=sum(w for _,w,_ in entries);mu=sum(w*r['reward'] for _,w,r in entries)/weight
            variance=sum(w*(r['reward']-mu)**2 for _,w,r in entries)/weight
            margin=1.96*math.sqrt(variance/len(entries))+.002
            scores[h]={'mean':mu,'lower':mu-margin,'upper':mu+margin,'support':len(entries)}
            used.extend(r['cycle'] for _,_,r in entries)
        return scores,sorted(set(used))


def loss_aware_policy(net,summary,demand,memory,cycle):
    base=capacity_policy(summary,demand)
    if base.action!='rate_limit':return base,[]
    scores,used=memory.meter_estimates(summary,cycle)
    # Identical caps are one candidate: do not repeatedly explore clipped meters.
    unique={}
    for h in HEADROOMS:unique.setdefault(meter_decision(summary,demand,h).rate_limit_kbps,h)
    choices=list(unique.values())
    unsupported=[h for h in choices if scores.get(h,{}).get('support',0)<3]
    if unsupported:
        h=min(unsupported,key=lambda h:(scores.get(h,{}).get('support',0),abs(h-.1)))
        reason=f'Bounded memory exploration: {h:.1f} Mbps headroom; only prior outcomes used'
    else:
        h=max(choices,key=lambda h:scores[h]['lower'])
        reason=f'Episodic parameter selection: {h:.1f} Mbps headroom from supported prior reward'
    return meter_decision(summary,demand,h,reason),used
