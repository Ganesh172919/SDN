let ruleRecords=[],ruleTimer=null;
const put=(id,value)=>document.getElementById(id).textContent=value;
function renderRule(){
  const seed=Number(document.getElementById('rule-seed').value),records=ruleRecords.filter(r=>r.metrics.seed===seed),i=Number(document.getElementById('rule-window').value),r=records[i];if(!r)return;
  const m=r.metrics,e=r.rule_event,s=r.state.simulation,p=e.provider_suggestion,audit=r.provider_calls;
  put('rule-window-label',`Window ${m.cycle+1} of ${records.length} · virtual ${e.virtual_seconds}–${e.virtual_seconds+5} seconds`);
  put('rule-traffic',`Primary background ${s.primary_background_mbps.toFixed(3)} Mbps + elephant ${s.elephant_mbps.toFixed(3)} Mbps. Alternate background ${s.alternate_background_mbps.toFixed(3)} Mbps. Each path: ${s.capacity_mbps} Mbps. Prior queues: ${s.queues_mbit.map(x=>x.toFixed(3)).join(' / ')} Mbit.`);
  put('rule-suggestion',p?`${p.action}: ${p.rationale}`:`No fresh provider response in this window. Decision source: ${m.origin}.`);
  put('rule-provider-audit',audit.length?audit.map(a=>`${a.provider} / ${a.actual_model||a.requested_model||'configured model'} / ${a.status}${a.error_code?' / '+a.error_code:''}`).join('\n'):'No API request: local reuse or healthy-load bypass.');
  put('rule-validation',`Validation: ${r.safety.allowed?'allowed':'rejected'} · ${r.safety.reason}. Final action: ${r.decision.action}. ${r.decision.rationale}`);
  put('rule-installed',e.installed_rule?`ADD cookie ${e.installed_rule.cookie}, priority 100, hard_timeout 5 s. Match: in_port 1, IPv4 destination 10.0.0.8. OUTPUT ${e.effective_output_port}${e.meter_kbps?`; METER ${e.meter_kbps} kbps`:''}.`:'No intervention rule. Default forwarding uses primary port 2.');
  put('rule-expiry',`${e.expired_rules.length} prior rule(s) expired at virtual ${e.virtual_seconds} s. ${e.installed_rule?`Current rule expires at ${e.installed_rule.expires_virtual_seconds} s.`:'No active intervention.'} At the end of replay, all intervention rules expire and port 2 is restored.`);
  put('rule-outcome',`Installed: delay ${m.latency_ms.toFixed(3)} ms · loss ${m.loss_pct.toFixed(3)}% · goodput ${(m.throughput_kbps/1000).toFixed(3)} Mbps. Same-state no-op comparison: delay ${r.no_op_outcome.latency_ms.toFixed(3)} ms · loss ${r.no_op_outcome.loss_pct.toFixed(3)}%. Control ${(m.control_elapsed_ms/1000).toFixed(3)} s; ${m.deadline_miss?'missed':'met'} 5 s target.`);
  put('rule-memory',`Retrieved completed cycles: ${JSON.parse(m.retrieved_cycles).join(', ')||'none'}. Measured reward ${m.reward.toFixed(6)}. ${r.reflection}`);
  put('rule-raw',JSON.stringify(r,null,2));
  document.getElementById('rule-path-primary').classList.toggle('active-path',e.effective_output_port===2);document.getElementById('rule-path-alternate').classList.toggle('active-path',e.effective_output_port===3);
  put('rule-meter',e.meter_kbps?`Meter: ${(e.meter_kbps/1000).toFixed(3)} Mbps`:'Meter: none');
}
async function loadRules(){
  if(ruleTimer){clearInterval(ruleTimer);ruleTimer=null;put('rule-play','Play saved demo');}
  const provider=document.getElementById('rule-provider').value,r=await fetch('/api/rule-demo?provider='+encodeURIComponent(provider));if(!r.ok){put('rule-traffic','Saved demo is unavailable.');return;}
  const data=await r.json();ruleRecords=data.records;const select=document.getElementById('rule-seed');select.replaceChildren();
  [...new Set(ruleRecords.map(r=>r.metrics.seed))].forEach(seed=>{const o=document.createElement('option');o.value=seed;o.textContent=seed;select.append(o);});resetRules();
}
function resetRules(){const count=ruleRecords.filter(r=>r.metrics.seed===Number(document.getElementById('rule-seed').value)).length;const slider=document.getElementById('rule-window');slider.max=Math.max(0,count-1);slider.value=0;renderRule();}
document.getElementById('rule-provider').addEventListener('change',loadRules);document.getElementById('rule-seed').addEventListener('change',resetRules);document.getElementById('rule-window').addEventListener('input',renderRule);
document.getElementById('rule-next').addEventListener('click',()=>{const slider=document.getElementById('rule-window');slider.value=Math.min(Number(slider.max),Number(slider.value)+1);renderRule();});
document.getElementById('rule-play').addEventListener('click',()=>{if(ruleTimer){clearInterval(ruleTimer);ruleTimer=null;put('rule-play','Play saved demo');return;}put('rule-play','Pause demo');ruleTimer=setInterval(()=>{const slider=document.getElementById('rule-window');if(Number(slider.value)>=Number(slider.max)){clearInterval(ruleTimer);ruleTimer=null;put('rule-play','Play saved demo');return;}slider.value=Number(slider.value)+1;renderRule();},1200);});
loadRules().catch(()=>put('rule-traffic','Saved provider demo could not be loaded.'));
