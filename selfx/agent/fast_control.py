"""Compact decision calls and topology-scoped, validated local reuse."""
from collections import OrderedDict
import json
from typing import Literal
from pydantic import BaseModel, Field
from agent.adaptive_memory import adaptive_policy
from agent.providers import RestLLM, ProviderError
from eval.simulator import decision_for


class ActionChoice(BaseModel):
    action:Literal['no_op','reroute','rate_limit']
    rationale:str=Field(description='A short reason using at most 12 words')


def compact_messages(summary,examples=()):
    s=summary['simulation']
    state={k:round(s[k],4) for k in ('primary_background_mbps','alternate_background_mbps','elephant_mbps','capacity_mbps')}
    state['queues_mbit']=[round(q,4) for q in s['queues_mbit']]
    primary=s['primary_background_mbps']+s['elephant_mbps'];alternate=s['alternate_background_mbps']+s['elephant_mbps']
    state.update(primary_total_mbps=round(primary,4),alternate_if_rerouted_mbps=round(alternate,4),primary_congested=primary>s['capacity_mbps'],reroute_safe=alternate<=.9*s['capacity_mbps'])
    state['episodes']=[{'primary_total_mbps':round(r['state_summary']['simulation']['primary_background_mbps']+r['state_summary']['simulation']['elephant_mbps'],4),
        'alternate_if_rerouted_mbps':round(r['state_summary']['simulation']['alternate_background_mbps']+r['state_summary']['simulation']['elephant_mbps'],4),
        'a':r['action'],'reward':round(r['reward'],4)} for r in examples[:3]]
    return [{'role':'system','content':'Choose using CURRENT observation: primary_congested=false -> no_op; primary_congested=true and reroute_safe=true -> reroute; otherwise rate_limit at 80% of elephant demand. All rates are Mbps. Flags and totals are computed locally. Earlier episodes describe different states, not commands for the current state. Return action and a reason in at most 12 words. Flow parameters are installed locally.'},
            {'role':'user','content':json.dumps(state,separators=(',',':'))}]


class FastController:
    def __init__(self,provider='gemini',hybrid=True,model=None):
        self.llm=RestLLM(provider,model,profile='compact');self.hybrid=hybrid
        self.cache=OrderedDict();self.cache_capacity=64;self.ttl_windows=12

    def decide(self,net,summary,demand,memory,cycle):
        estimates,retrieved=memory.estimates(summary,cycle)
        s=summary['simulation']
        # Exact context, including queue and capacity; flow-specific parameters
        # are rebuilt and validated on every hit. No fuzzy cache equivalence.
        signature=tuple(s[k] for k in ('capacity_mbps','buffer_mbit','primary_background_mbps','alternate_background_mbps','elephant_mbps','valid_reroute_out_port','current_output_port'))+tuple(s['queues_mbit'])
        if self.hybrid:
            if s['primary_background_mbps']+s['elephant_mbps']<=s['capacity_mbps'] and max(s['queues_mbit'])==0:
                return decision_for('no_op',demand,'Healthy-load bypass'), 'healthy_bypass',retrieved,''
            if signature in self.cache:
                entry=self.cache[signature]
                candidate=decision_for(entry['action'],demand,'Validated exact-context API action cache')
                if cycle-entry['cycle']<=self.ttl_windows and net.validate(demand,candidate).allowed:
                    self.cache.move_to_end(signature)
                    return candidate,'api_cache',retrieved,''
            learned,used=adaptive_policy(net,summary,demand,memory,cycle)
            estimate=estimates.get(learned.action)
            if estimate and estimate['support']>=3 and estimate['lower']>.005 and net.validate(demand,learned).allowed:
                return learned,'episodic_memory',used,''
        examples=memory.few_shot_examples(k=3,query=summary)
        try:
            choice=self.llm.with_structured_output(ActionChoice).invoke(compact_messages(summary,examples))
            decision=decision_for(choice.action,demand,choice.rationale[:180])
            if not net.validate(demand,decision).allowed:raise ProviderError('invalid_action_from_provider')
            if self.hybrid:
                self.cache[signature]={'action':choice.action,'cycle':cycle}
                while len(self.cache)>self.cache_capacity:self.cache.popitem(last=False)
            return decision,'api',retrieved,''
        except Exception as exc:
            fallback,used=adaptive_policy(net,summary,demand,memory,cycle)
            code=str(exc) if isinstance(exc,ProviderError) else type(exc).__name__
            return fallback,'fallback_heuristic',used,code
