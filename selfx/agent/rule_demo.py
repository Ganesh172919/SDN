"""Auditable simulated OpenFlow rule lifecycle, with five-second expiry."""
from eval.simulator import FLOW_MATCH


class SimulatedRuleTable:
    def __init__(self):self.active=None

    def apply(self,decision,cycle,origin,suggestion=None,explanation=None):
        now=cycle*5;expired=[]
        if self.active and self.active['expires_virtual_seconds']<=now:
            expired=[self.active];self.active=None
        rule=None
        if decision.action!='no_op':
            instructions=[]
            if decision.action=='rate_limit':instructions.append({'type':'METER','meter_id':cycle+1,'rate_kbps':decision.rate_limit_kbps})
            instructions.append({'type':'APPLY_ACTIONS','actions':[{'type':'OUTPUT','port':3 if decision.action=='reroute' else 2}]})
            rule={'cookie':cycle+1,'command':'ADD','dpid':1,'match':dict(FLOW_MATCH),'priority':100,'hard_timeout':5,
                'installed_virtual_seconds':now,'expires_virtual_seconds':now+5,'instructions':instructions}
            self.active=rule
        return {'cycle':cycle,'virtual_seconds':now,'backend':'simulated_rule_table','physical_switch_contacted':False,
            'origin':origin,'provider_suggestion':suggestion,'explanation':explanation or {},'expired_rules':expired,
            'installed_rule':rule,'effective_output_port':3 if decision.action=='reroute' else 2,
            'meter_kbps':decision.rate_limit_kbps,'final_decision':decision.model_dump(),
            'lifecycle':'Expire previous five-second rule; validate current action; install bounded rule or use default port 2'}

    def finish(self,cycles):
        expired=[self.active] if self.active else [];self.active=None
        return {'virtual_seconds':cycles*5,'expired_rules':expired,'active_rules':[],'effective_output_port':2,'meter_kbps':None}
