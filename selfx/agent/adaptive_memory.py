"""Magnitude-preserving, action-conditioned episodic advantage estimates.

Only completed earlier episodes train the memory. No candidate simulator
outcomes or future demand are consulted by this policy.
"""
from __future__ import annotations
import math
from collections import defaultdict
from statistics import mean
from agent.memory import MemoryStore
from agent.guarded_memory import guarded_base
from eval.simulator import decision_for


def context(state):
    s=state['simulation'];c=s['capacity_mbps'];p=s['primary_background_mbps']/c
    a=s['alternate_background_mbps']/c;e=s['elephant_mbps']/c
    q=[v/s['buffer_mbit'] for v in s['queues_mbit']]
    return [p,a,e,p+e-1,a+e-.9,p+.8*e-1,*q]


def regime(vector):
    return tuple(v>1e-8 for v in vector[3:6])


class AdaptiveMemory(MemoryStore):
    """96 diverse episodes, cached contexts, action-local support and uncertainty."""
    limit=96

    def _prune(self):
        buckets=defaultdict(list)
        for r in self._records:
            r.setdefault('context_v3',context(r['state_summary']))
            v=r['context_v3']
            key=(r['action'],regime(v),tuple(round(x/.12) for x in v[:3]))
            buckets[key].append(r)
        # Four observations allow the three-neighbor support gate to be met.
        retained=[]
        for records in buckets.values():
            retained.extend(records[-4:])
        self._records=sorted(retained,key=lambda r:r['cycle'])[-self.limit:]

    def estimates(self,state,cycle):
        query=context(state);candidates=defaultdict(list)
        for r in self.all_records():
            if r['cycle']>=cycle:continue
            vector=r.get('context_v3') or context(r['state_summary'])
            if regime(vector)!=regime(query):continue
            delta=[abs(a-b) for a,b in zip(vector,query)]
            if max(delta[:6])>.18 or max(delta[6:])>.51:continue
            distance=sum(d*d for d in delta[:6])+sum(.08*d*d for d in delta[6:])
            weight=math.exp(-distance/.025)*math.exp(-(cycle-r['cycle'])/120)
            candidates[r['action']].append((distance,weight,r))
        estimates={};used=[]
        for action,entries in candidates.items():
            entries=sorted(entries,key=lambda x:x[0])[:8]
            if len(entries)<3:continue
            weight=sum(x[1] for x in entries);mu=sum(w*r['reward'] for _,w,r in entries)/weight
            effective=weight*weight/sum(w*w for _,w,_ in entries)
            variance=sum(w*(r['reward']-mu)**2 for _,w,r in entries)/weight
            uncertainty=1.96*math.sqrt(variance/max(1,effective))+.002
            estimates[action]={'mean':mu,'lower':mu-uncertainty,'upper':mu+uncertainty,'support':len(entries)}
            used.extend(r['cycle'] for _,_,r in entries)
        return estimates,sorted(set(used))


def adaptive_policy(net,summary,demand,memory,cycle):
    base=guarded_base(summary,demand)
    estimates,retrieved=memory.estimates(summary,cycle)
    # No-op has exactly zero advantage under the common no-op-relative reward.
    base_score=estimates.get(base.action,{'mean':0,'lower':0,'upper':0})
    if base.action!='no_op' and base.action in estimates and base_score['upper']<0:
        return decision_for('no_op',demand,'Adaptive memory: repeated local evidence predicts a harmful base action'),retrieved
    for action,score in sorted(estimates.items(),key=lambda x:x[1]['lower'],reverse=True):
        candidate=decision_for(action,demand,'Adaptive memory: action-local advantage with supported margin')
        if score['lower']>max(0,base_score['upper'])+.005 and net.validate(demand,candidate).allowed:
            return candidate,retrieved
    return base,retrieved
