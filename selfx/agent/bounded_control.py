"""Deadline-bounded provider suggestions, loss-aware local parameters and reuse."""
from collections import OrderedDict
import json
from agent.deadline_provider import DeadlineProvider
from agent.loss_aware_memory import loss_aware_policy,capacity_policy,meter_decision,HEADROOMS
from eval.simulator import decision_for
from agent.providers import ProviderError


def suggestion_messages(summary,examples,local):
    s=summary['simulation']
    observation={k:s[k] for k in ('capacity_mbps','primary_background_mbps','alternate_background_mbps','elephant_mbps','queues_mbit')}
    observation.update(primary_congested=s['primary_background_mbps']+s['elephant_mbps']>s['capacity_mbps'],
        alternate_safe=s['alternate_background_mbps']+s['elephant_mbps']<=.9*s['capacity_mbps'],
        local_recommendation=local.model_dump(exclude_none=True),
        previous_episodes=[{'cycle':r['cycle'],'action':r['action'],'reward':round(r['reward'],5),'meter_kbps':r['params'].get('rate_limit_kbps')} for r in examples[:3]])
    return [{'role':'system','content':'Suggest one action using the CURRENT flags: primary_congested=false: no_op. Otherwise alternate_safe=true: reroute. Otherwise: rate_limit. Local software constructs the smallest bounded meter and validates the exact flow, port and rate. Prior episodes are evidence, not current commands. Return JSON action and a short rationale (at most 12 words).'},
        {'role':'user','content':json.dumps(observation,separators=(',',':'))}]


class BoundedController:
    def __init__(self,provider='gemini',hybrid=True,model=None,budget_seconds=3.8):
        if provider=='auto':provider='gemini'
        self.llm=DeadlineProvider(provider,model,budget_seconds)
        self.hybrid=hybrid;self.cache=OrderedDict();self.last_explanation={}

    def decide(self,net,summary,demand,memory,cycle):
        local,used=loss_aware_policy(net,summary,demand,memory,cycle)
        s=summary['simulation'];self.last_explanation={'local_recommendation':local.model_dump(),'provider_suggestion':None}
        signature=tuple(s[k] for k in ('capacity_mbps','buffer_mbit','primary_background_mbps','alternate_background_mbps','elephant_mbps','valid_reroute_out_port','current_output_port'))+tuple(s['queues_mbit'])
        if self.hybrid:
            if local.action=='no_op':return local,'healthy_bypass',used,''
            scores,matched=memory.meter_estimates(summary,cycle)
            chosen=min(HEADROOMS,key=lambda h:abs(meter_decision(summary,demand,h).rate_limit_kbps-(local.rate_limit_kbps or 0)))
            supported=scores.get(chosen,{})
            if local.action=='rate_limit' and supported.get('support',0)>=3 and supported.get('lower',0)>.005:
                self.last_explanation['parameter_evidence']=scores
                return local,'episodic_memory',used,''
            cached=self.cache.get(signature)
            if cached and cycle-cached['cycle']<=12:
                candidate=local if cached['action']=='rate_limit' and local.action=='rate_limit' else decision_for(cached['action'],demand,'Exact-context cached action')
                if net.validate(demand,candidate).allowed:
                    self.last_explanation['cached_source']=cached.get('source','api')
                    return candidate,'api_cache' if cached.get('source','api')=='api' else 'local_rule_cache',used,''
        try:
            choice=self.llm.choose(suggestion_messages(summary,memory.few_shot_examples(k=3,query=summary),local))
            self.last_explanation['provider_suggestion']=choice
            decision=local.model_copy(update={'rationale':choice['rationale']}) if choice['action']=='rate_limit' else decision_for(choice['action'],demand,choice['rationale'])
            # Rebuild all flow parameters locally. Provider cannot install arbitrary rules.
            if choice['action']=='rate_limit' and local.action!='rate_limit':decision=meter_decision(summary,demand,.1,choice['rationale'])
            guard=net.validate(demand,decision)
            if not guard.allowed:
                self.last_explanation['proposal_rejected']=guard.reason
                if self.hybrid:self.remember(signature,local,cycle,'validation_fallback')
                return local,'validation_fallback',used,'invalid_action_from_provider'
            if self.hybrid:
                self.remember(signature,decision,cycle,'api')
            return decision,'api',used,''
        except ProviderError as exc:
            if self.hybrid:self.remember(signature,local,cycle,'local_fallback')
            return local,'deadline_fallback' if str(exc)=='local_deadline' else 'provider_fallback',used,str(exc)

    def remember(self,signature,decision,cycle,source):
        self.cache[signature]={'action':decision.action,'cycle':cycle,'source':source}
        while len(self.cache)>64:self.cache.popitem(last=False)
