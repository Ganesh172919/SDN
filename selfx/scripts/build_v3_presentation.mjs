// Artifact Session authoring. All tables, charts and flow diagrams are editable.
const C={ink:'#102E36',muted:'#60777B',teal:'#007D76',paper:'#F6F8F3',line:'#D9E3DF',light:'#E8F0E9',white:'#FFFFFF'};
function text(s,t,x,y,w,h,size=28,color=C.ink,bold=false){const q=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0},text:{text:t,style:{typeface:'Arial',fontSize:size,color,bold}}});q.text.insets=0;return q;}
function base(p,title,n,note='',dark=false){const s=p.slides.add({width:1280,height:720,background:{fill:dark?C.ink:C.paper}});if(title)text(s,title,64,45,1150,110,42,dark?C.white:C.ink);text(s,`${String(n).padStart(2,'0')} / SELF-X`,64,670,350,24,15,dark?'#A7C0BA':C.muted);if(note)text(s,note,420,667,795,33,14,dark?'#A7C0BA':C.muted);return s;}
function table(s,values,x=64,y=178,w=1152,h=410,widths,font=24){const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,values,columnWidths:widths});t.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length}).assign({fill:C.paper,textStyle:{typeface:'Arial',fontSize:font,color:C.ink},margins:{top:6,bottom:6,left:10,right:10}});t.cells.block({row:0,column:0,rowCount:1,columnCount:values[0].length}).assign({fill:C.light,textStyle:{typeface:'Arial',fontSize:font,bold:true,color:C.ink}});t.borders.assign({fill:C.line,width:1,style:'solid'});return t;}
function body(s,lines,y=185,size=29,gap=100){lines.forEach((v,i)=>text(s,v,68,y+i*gap,1135,gap-12,size));}
const values=a=>a.map(x=>Number(x.toFixed(6)));
function bar(s,categories,series,{x=100,y=190,w=1090,h=350,format='0.00',legend=false,stacked=false,show=true}={}){return s.charts.add('bar',{position:{left:x,top:y,width:w,height:h},categories,series:series.map(v=>({...v,values:values(v.values)})),hasLegend:legend,legend:legend?{position:'top',textStyle:{typeface:'Arial',fontSize:19}}:undefined,barOptions:{direction:'column',grouping:stacked?'stacked':'clustered',gapWidth:120},dataLabels:{showValue:show,position:stacked?'center':'outEnd',numberFormatCode:format,numberFormatSourceLinked:false,textStyle:{typeface:'Arial',fontSize:22}},xAxis:{textStyle:{typeface:'Arial',fontSize:21}},yAxis:{min:Math.min(0,...series.flatMap(v=>v.values))*1.15,max:Math.max(...series.flatMap(v=>v.values))<=0?0:undefined,numberFormatCode:format,textStyle:{typeface:'Arial',fontSize:18},majorGridlines:{fill:C.line,width:1,style:'solid'}},chartFill:C.paper,plotAreaFill:C.paper});}
function box(s,t,x,y,w=190,h=90){return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill:C.light,line:{fill:C.teal,width:1.5},text:{text:t,style:{typeface:'Arial',fontSize:27,color:C.ink,bold:true}}});}
const fmt=(x,d=3)=>Number(x).toFixed(d);
export async function build(p,d){
 if(p.slides.items.length)p.slides.keep([]);p.theme.defaultFont='Arial';
 const s0=d.primary,overall=d.overall,g=d.live.groups,scenarios=Object.keys(s0.scenarios),short={mixed:'Mixed',flash:'Flash',alternate:'Alt busy',shift:'Shift',overload:'Overload',light:'Light',recurring:'Recurring',volatile:'Volatile'};
 const modes=['legacy','compact','hybrid'],labels=['Two calls','Compact','Hybrid'],source='Source: saved v3 CSV, JSON and provider audits; network values are simulated';
 let s=base(p,'',1,'Measured revision 3 · 20 October 2026',true);
 text(s,'SELF-X',68,98,1135,140,96,C.white,true);text(s,'Adaptive episodic memory\nand lower API control delay',72,270,1120,170,49,C.white);text(s,'Generated traffic · Paired benchmarks · Real provider requests',74,508,1115,85,29,'#B7D6CD');
 s.speakerNotes.text='This submission evaluates a state-embedding memory revision and API pipeline changes inside selfx. The primary suite is separate from a constructed post-hoc memory diagnostic and a small live Gemini timing pilot. No packet or physical-network performance is claimed.';

 s=base(p,'Project goal and control architecture',2,source);
 text(s,'Reuse earlier local experience to choose a bounded flow intervention',68,160,1135,83,33,C.teal);
 const names=['Observe','Retrieve','Decide','Validate','Measure','Reflect'];const boxes=names.map((name,i)=>box(s,name,70+(i%3)*400,292+Math.floor(i/3)*178,330,82));
 for(let i=0;i<5;i++)s.shapes.connect(boxes[i],boxes[i+1],{kind:'elbow',fromSide:i===2?'bottom':'right',toSide:i===2?'top':'left',line:{fill:C.teal,width:1.7}});
 s.speakerNotes.text='The local website exposes traffic, state embeddings, decision origins, action safety, outcomes and editable submission files. The portable fluid simulation is the validated path on this Windows machine; Linux Mininet/Ryu remains a separate unvalidated adapter.';

 s=base(p,'Memory retrieval changes',3,'A4 learns only from completed earlier episodes');
 table(s,[['Component','Previous A3','Current A4'],['State match','Normalized cosine','Magnitude and capacity margins'],['Action evidence','Optimistic local reward','Separate value per action'],['Storage','30 balanced episodes','96 diverse episodes'],['Support','Similar positive episodes','At least 3 matched observations'],['Selection','Feasible historical preference','Conservative local evidence gate']],64,176,1152,410,[235,385,532],24);
 text(s,'Current parameters are rebuilt and independently validated for every action.',68,603,1135,53,26,C.teal);
 s.speakerNotes.text='Source: agent/adaptive_memory.py. Eight context coordinates preserve absolute capacity-scaled demand, three congestion/headroom margins and queue occupancy. Up to eight matched observations per action use distance and recency weights. Four retained observations per action/context cell allow the three-observation gate to be met. The local spread margin is heuristic, not a calibrated confidence interval. No simulator candidate outcomes enter policy selection.';

 s=base(p,'API work and local reuse',4,'Cache hits and local bypasses are never counted as new API decisions');
 body(s,['Legacy: full decision call, then a second API reflection call.','Compact: one short action choice; local parameters and reflection.','Hybrid: exact-context cache, healthy bypass and supported memory.','Pacing and HTTP/service time are recorded separately.'],180,30,108);
 s.speakerNotes.text='Compact calls use pooled HTTP connections, a 384-token output cap and Gemini minimal thinking. The prompt includes locally computed totals and feasibility flags. The 64-entry cache expires after 12 windows and includes demand, queue, capacity, buffer and observed route-port context. All hits are revalidated. Google model and thinking references: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite and https://ai.google.dev/gemini-api/docs/generate-content/whats-new-gemini-3.5 .';

 s=base(p,'Generated traffic and primary benchmark coverage',5,'Finite-buffer two-path fluid model; no packet capture');
 text(s,s0.window_count.toLocaleString(),68,170,1130,110,80,C.teal,true);text(s,'measured primary control windows',73,285,1120,65,34);
 body(s,['8 scenarios × 10 held-out seeds × 120 windows × 9 controllers','10 Mbps per path · 0.5 Mbit buffer · 5-second action windows','9,600 generated aggregate flow records exported as CSV'],392,28,77);
 s.speakerNotes.text='Source: output/benchmarks/v3/summary.json and traffic/simulated_netflow.csv. Scenarios include mixed load, flash crowd, busy alternate, a distribution shift, dual overload, light load, recurring contexts and volatile changes. NetFlow-style CSV describes synthetic aggregate demand, not captured packets or wire-format IPFIX. See RFC 7011 https://www.rfc-editor.org/rfc/rfc7011 .';

 s=base(p,'Experimental comparisons and evidence boundaries',6,'Every primary controller receives the same demand for each scenario and seed');
 table(s,[['Study','Sample','Interpretation'],['Primary held-out suite','86,400 windows; 10 seeds','Ordinary workload comparison'],['Near-capacity diagnostic','19,200 windows; 10 seeds','Post-hoc mechanism stress test'],['Fresh Gemini pilot','72 cycles; 2 seeds','System latency and integration'],['Free model sweep',`${d.free_models.ok}/${d.free_models.checked} valid checks`,'Availability, not control quality']],64,180,1152,375,[285,365,502],24);
 text(s,'H1 isolates the base guard. O1 has privileged simulator access.',68,586,1130,62,29,C.teal);
 s.speakerNotes.text='Primary held-out seeds 1760..1769 differ from development seeds 1740 and 1741. The targeted near-capacity diagnostic was constructed after inspecting the main suite and is excluded from its aggregate. The final API pilot uses fresh seeds 1790 and 1791; an earlier prompt-arithmetic pilot on 1770 and 1771 is preserved. Paired seed bootstrap intervals use 4,000 draws, RNG 4099, and no multiplicity correction. O1 is myopic, not a long-horizon upper bound.';

 s=base(p,'Primary scenario delay results',7,'Mean modeled delay in milliseconds; 1,200 windows per cell');
 const ids=Object.keys(s0.controllers);table(s,[['Scenario',...ids],...scenarios.map(sc=>[short[sc],...ids.map(c=>fmt(s0.groups[sc][c].metrics.latency_ms.mean,2))])],64,176,1152,430,[162,...ids.map(()=>110)],21);
 text(s,'A4 matches H1; it removes A3 regressions on mixed, flash and volatile traffic.',68,615,1130,43,25,C.teal);
 s.speakerNotes.text='Source: output/benchmarks/v3/summary.json. IDs: A0 static primary, B1 least loaded, B2 guarded ECMP-style hash, A1 original threshold, A2 original reward-pruned memory, H1 guarded no memory, A3 previous balanced memory, O1 myopic simulator reference, A4 new action-conditioned memory. B2 motivation: RFC 2992 https://www.rfc-editor.org/rfc/rfc2992 .';

 s=base(p,'Overall primary modeled delay',8,'Equal weighting across eight primary scenarios and ten paired seeds');
 const focus=['A2','A3','H1','A4','O1'];bar(s,focus,[{name:'Mean modeled delay ms',values:focus.map(c=>overall[c].latency_ms),fill:C.teal}],{format:'0.000'});
 text(s,`A4: ${fmt(overall.A4.latency_ms)} ms. Previous A3: ${fmt(overall.A3.latency_ms)} ms.\nH1 has the same primary network outcome as A4.`,72,578,1120,83,28,C.teal);
 s.speakerNotes.text='Source: output/benchmarks/v3/chart_data.json. Primary means are paired by scenario and seed, with cold-start windows and all outcomes retained. A4 is an observed regression reduction relative to A3, not proof of an additional memory benefit over the common guard.';

 s=base(p,'Paired adaptive memory effects',9,'A4 minus A3; negative delay differences favor A4');
 table(s,[['Scenario','Delay difference ms','Paired 95% interval'],...scenarios.map(sc=>{const v=s0.paired_comparisons[sc].A4_minus_A3.latency_ms;return[short[sc],fmt(v.mean_difference),`[${fmt(v.ci95[0])}, ${fmt(v.ci95[1])}]`]})],64,177,1152,420,[265,365,522],24);
 text(s,'Exploratory comparisons; intervals do not correct for multiple testing.',68,610,1130,45,25,C.teal);
 s.speakerNotes.text='Source: raw paired seed means in output/benchmarks/v3/summary.json. Seed means, not individual windows, are the resampling units. Ten paired seeds and 4,000 fixed-RNG bootstrap draws define the 95% percentile intervals.';

 s=base(p,'The guard-only memory ablation',10,'The primary experiment does not show an additional gain over H1');
 bar(s,scenarios.map(sc=>short[sc]),['H1','A4'].map((c,i)=>({name:c,values:scenarios.map(sc=>s0.groups[sc][c].metrics.latency_ms.mean),fill:i?C.teal:'#234F7D'})),{legend:true,format:'0.0',x:85,w:1120,show:false});
 text(s,'A4 and H1 chose the same installed actions in all 9,600 primary windows.',68,590,1135,61,27,C.teal);
 s.speakerNotes.text='The no-memory guard ablation is essential for attribution. Supported retrieval does not imply that memory changed an action or improved performance. A4 matches H1 on all primary network metrics; this conclusion is retained rather than presenting guard improvements as learning gains.';

 s=base(p,'Delay goodput loss and feasibility',11,'Loss includes deliberate rate-meter drops; all values are simulated');
 table(s,[['ID','Delay ms','Goodput Mbps','Total loss %','Vetoes'],...ids.map(c=>{const v=overall[c];return[c,fmt(v.latency_ms),fmt(v.throughput_kbps/1000),fmt(v.loss_pct),String(v.vetoes)]})],64,176,1152,420,[100,240,285,285,242],23);
 text(s,'A4 has zero vetoes. Feasibility and performance are separate outcomes.',68,610,1130,44,26,C.teal);
 s.speakerNotes.text='Source: output/benchmarks/v3/chart_data.json. Lower delay must be evaluated together with discarded offered traffic and delivered goodput. Means are equal-weight scenario averages; pooled traffic-volume loss is a distinct statistic available in the raw summary.';

 s=base(p,'Near-capacity memory sensitivity',12,'Constructed post-hoc diagnostic; excluded from the primary average');
 const levels=Object.keys(d.sensitivity.levels_mbps);bar(s,levels.map(k=>String(d.sensitivity.levels_mbps[k])),['H1','A4'].map((c,i)=>({name:c,values:levels.map(k=>d.sensitivity.groups[k][c].metrics.loss_pct.mean),fill:i?C.teal:'#234F7D'})),{legend:true,format:'0.00'});
 text(s,'Total loss (%) versus primary excess above 10 Mbps.\nA4 retains more traffic while allowing higher queue delay.',72,580,1120,79,28,C.teal);
 s.speakerNotes.text='Source: output/benchmarks/v3/memory_sensitivity/summary.json. Four primary excess levels, ten paired seeds, 120 windows and four controllers produce 19,200 windows. The test was deliberately constructed to exercise negative-experience learning. It does not establish generalization to ordinary or captured traffic.';

 s=base(p,'Learning after harmful throttling',13,'0.0001 Mbps excess diagnostic; all cold-start windows retained');
 const points=[1,3,10,30,60,120];bar(s,points.map(String),[{name:'A4 minus H1 cumulative reward',values:points.map(n=>d.learning_curve.A4[n-1]-d.learning_curve.H1[n-1]),fill:C.teal}],{format:'0.000'});
 text(s,`Bars: A4 minus H1 cumulative reward; positive favors A4.\nWindow 120 raw means: A4 ${fmt(d.learning_curve.A4[119])}; H1 ${fmt(d.learning_curve.H1[119])}.`,72,578,1120,82,26,C.teal);
 s.speakerNotes.text='Source: full sensitivity CSV. Bars show A4 minus H1 cumulative mean no-op-relative observed reward at windows 1, 3, 10, 30, 60 and 120, averaged across ten seeds. Positive differences favor A4. The actual negative raw cumulative rewards at window 120 remain in the slide text and editable report. A4 requires at least three matched earlier observations before rejecting a repeatedly harmful base action. This is episodic adaptation, not model-weight training.';

 s=base(p,'Measured full-cycle Gemini latency',14,'Two fresh seeds; 24 cycles per mode; pacing and reflection included');
 bar(s,[...labels,'5-second target'],[{name:'Mean full cycle seconds',values:[...modes.map(m=>g[m].control_elapsed_ms/1000),5],fill:C.teal}],{format:'0.000'});
 text(s,`Compact mean reduction: ${fmt(d.latency_reduction_pct.compact,1)}%. Hybrid: ${fmt(d.latency_reduction_pct.hybrid,1)}%.\nThis measures the whole system, including fewer requests and local reuse.`,72,578,1120,81,28,C.teal);
 s.speakerNotes.text='Source: output/benchmarks/v3/latency_gemini/summary.json and provider_calls.json. The compact path makes one provider call per cycle; the legacy path makes two. Hybrid reuses validated exact contexts. HTTP/network/service time and request pacing are recorded separately. This is not an isolated provider-server speed benchmark.';

 s=base(p,'Provider calls and decision origins',15,'Fresh API responses remain separate from local cache and bypass decisions');
 const origins=[['api','API','#467D91'],['api_cache','Cache','#007D64'],['episodic_memory','Memory','#7DB0A4'],['healthy_bypass','Healthy bypass','#AABBB5'],['fallback_heuristic','Fallback','#D28244']];
 bar(s,labels,origins.map(([key,name,fill])=>({name,values:modes.map(m=>g[m].origins[key]||0),fill})),{legend:true,stacked:true,show:false,format:'0'});
 text(s,`Actual provider requests: ${g.legacy.api_calls} → ${g.compact.api_calls} → ${g.hybrid.api_calls}.\nLocal measured reflection makes no provider request.`,72,582,1120,78,29,C.teal);
 s.speakerNotes.text='Source: output/benchmarks/v3/latency_gemini/metrics.csv. Origins are mutually exclusive window labels. Provider request counts include reflection for legacy, so API-window counts differ from total request counts. Any cache, healthy bypass or memory reuse is explicitly local.';

 s=base(p,'Live pilot network outcomes',16,'Faster execution must be assessed together with action quality');
 table(s,[['Mode','Delay ms','Goodput Mbps','Total loss %','Reward'],...modes.map((m,i)=>[labels[i],fmt(g[m].latency_ms),fmt(g[m].throughput_kbps/1000),fmt(g[m].loss_pct),fmt(g[m].reward)])],64,195,1152,300,[195,230,280,260,187],25);
 text(s,`Hybrid loss minus legacy: ${fmt(g.hybrid.loss_pct-g.legacy.loss_pct)} percentage points.\nA latency reduction does not establish a uniform network-quality gain.`,70,553,1130,92,29,C.teal);
 s.speakerNotes.text='The corrected compact prompt uses current-state totals and flags after an earlier diagnostic exposed arithmetic mistakes. The final fresh pilot uses different seeds from that diagnostic. Its small sample cannot establish broad LLM effectiveness or a cross-model quality ranking. All network values remain simulated.';

 s=base(p,'Five-second deadline misses',17,'Observed tail latency remains a practical limitation');
 bar(s,labels,[{name:'Misses out of 24 cycles',values:modes.map(m=>g[m].deadline_misses),fill:C.teal}],{format:'0'});
 text(s,`P95 full cycle: ${modes.map((m,i)=>labels[i]+' '+fmt(g[m].p95_control_ms/1000,2)+' s').join(' · ')}\nThe pilot does not establish a production deadline guarantee.`,70,581,1130,80,27,C.teal);
 s.speakerNotes.text='Source: measured full-cycle perf_counter timings. Requests may exceed the target under network or provider variability. No API work or reflection is excluded from the measured full cycle. There are only two independent traffic seeds; individual windows are not independent seed replications.';

 s=base(p,'Local memory computation overhead',18,'Measured in .venv; excludes the final batched memory flush');
 bar(s,ids,[{name:'Mean local control milliseconds',values:ids.map(c=>overall[c].control_elapsed_ms),fill:C.teal}],{format:'0.000'});
 text(s,`Primary suite wall time: ${fmt(s0.wall_seconds,2)} seconds.\nA4 mean: ${fmt(overall.A4.control_elapsed_ms)} ms; P95: ${fmt(overall.A4.decision_p95_ms)} ms.`,72,578,1120,81,28,C.teal);
 s.speakerNotes.text='Source: output/benchmarks/v3/metrics.csv. This is machine-dependent local computation, separate from the real Gemini waiting-time study. A larger episode budget can cost more CPU than A3 even when it improves retrieval reliability.';

 s=base(p,'Validation and remaining limits',19,'All project modifications and evidence remain inside selfx');
 body(s,[`${d.test_summary} in the isolated virtual environment.`,`${d.free_models.ok}/${d.free_models.checked} compact free-model schema checks returned valid actions.`,'Primary memory matches H1; targeted benefits have a delay tradeoff.','Network metrics are simulated; Linux packet deployment remains unvalidated.'],178,29,109);
 s.speakerNotes.text='Tests cover conservation, reproducibility, context magnitude, earlier-only retrieval, memory support and bounds, negative-action learning, cache expiry/state changes, API fallback and the original graph modules. Automatic source checks exclude credentials from the submission package. No real-network, global-stability or production-SLA claim is made.';

 s=base(p,'Reproduce and inspect the results',20,'Run every command from the selfx folder',true);
 text(s,'.\\run.ps1 all\n.\\run.ps1 latency\n.\\run.ps1 dashboard -Port 8766',72,184,1120,215,38,C.white);
 text(s,'output/benchmarks/v3 → CSV, traffic, API audits and 15 PNG/SVG figures',72,441,1110,80,29,'#B7D6CD');
 text(s,'Editable report and presentation · Report, slide and graph PDFs',72,548,1110,65,27,'#B7D6CD');
 s.speakerNotes.text='README.md and docs/BENCHMARKS_V3.md give setup and detailed commands. .env stores credentials; .venv is the isolated Python environment. The submission ZIP excludes credentials and dependency caches. Existing saved API evidence can be inspected without new requests; new live runs require available quota.';
 return {slides:p.slides.items.length};
}
