import { appendBenchmarkSlides } from './benchmark_slides.mjs';
// Used inside Artifact Session: build(presentation, parsed deck_content.json).
// Native charts, tables and architecture diagrams remain editable in PowerPoint.
const C={ink:'#102E36',muted:'#60777B',teal:'#007D76',paper:'#F6F8F3',line:'#D9E3DF',light:'#E8F0E9',white:'#FFFFFF'};
function text(slide,value,x,y,w,h,size=26,color=C.ink,bold=false){
  const shape=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0},text:{text:value,style:{typeface:'Arial',fontSize:size,color,bold}}});
  shape.text.insets=0;return shape;
}
function base(p,title,num,note='',dark=false){
  const s=p.slides.add({width:1280,height:720,background:{fill:dark?C.ink:C.paper}});
  if(title)text(s,title,64,48,1152,100,44,dark?C.white:C.ink);
  text(s,`${String(num).padStart(2,'0')} / SELF-X`,64,668,400,22,15,dark?'#A7C0BA':C.muted);
  if(note)text(s,note,475,665,740,30,15,dark?'#A7C0BA':C.muted);
  return s;
}
function body(s,lines,x=66,y=176,w=1130,size=28,gap=89){lines.forEach((line,i)=>text(s,line,x,y+i*gap,w,gap-10,size));}
function table(s,values,x=64,y=176,w=1152,h=350,widths){
  const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,values,columnWidths:widths});
  t.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length}).assign({fill:C.paper,textStyle:{typeface:'Arial',fontSize:24,color:C.ink},margins:{top:12,bottom:12,left:12,right:12}});
  t.cells.block({row:0,column:0,rowCount:1,columnCount:values[0].length}).assign({fill:C.light,textStyle:{typeface:'Arial',fontSize:23,bold:true,color:C.ink}});
  t.borders.assign({fill:C.line,width:1,style:'solid'});
  return t;
}
function bar(s,values,title,x=70,y=185,w=720,h=390){
  const chart=s.charts.add('bar',{position:{left:x,top:y,width:w,height:h},categories:['A0','B1','A1','A2'],
    series:[{name:title,values:values.map(v=>Number(v.toFixed(6))),fill:C.teal}],hasLegend:false,barOptions:{direction:'column',grouping:'clustered',gapWidth:120},
    dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.00',numberFormatSourceLinked:false,textStyle:{typeface:'Arial',fontSize:23}},
    xAxis:{textStyle:{typeface:'Arial',fontSize:23}},
    yAxis:{min:0,numberFormatCode:'0.0',textStyle:{typeface:'Arial',fontSize:19},majorGridlines:{fill:C.line,width:1,style:'solid'}},
    chartFill:C.paper,plotAreaFill:C.paper});
  return chart;
}
function box(s,label,x,y,w=190,h=90){
  const q=s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill:C.light,line:{fill:C.teal,width:1.4},text:{text:label,style:{typeface:'Arial',fontSize:25,color:C.ink,bold:true}}});
  return q;
}
function connect(s,a,b){s.shapes.connect(a,b,{kind:'elbow',fromSide:'right',toSide:'left',line:{fill:C.teal,width:2}});}
function f(n,d=2){return Number(n).toFixed(d)}
export async function build(p,d){
  if(p.slides.items.length)p.slides.keep([]);
  p.theme.defaultFont='Arial';
  const off=d.runs.offline.conditions,g=d.runs.gemini_paced.conditions,or=d.runs.openrouter.conditions;
  const source='Source: saved experiment CSV and JSONL; network provenance: simulation';
  let s=base(p,'',1,'20 October 2026',true);
  text(s,'SELF-X',66,110,1145,155,100,C.white,true);
  text(s,'SDN control with\nstate embedding memory',70,292,1040,160,51,C.white);
  text(s,'Measured simulation with live Gemini and free OpenRouter decisions',72,514,1100,80,26,'#B7D6CD');
  s.speakerNotes.text='Project submission. Network metrics are produced by a documented finite-buffer fluid model. Provider calls are real. The report distinguishes technical execution from an empirical improvement claim.';

  s=base(p,'Project purpose',2);
  text(s,'Can a controller reuse its own experience\nto manage repeated congestion?',66,184,1120,140,43,C.teal);
  body(s,['Observe traffic and choose one bounded flow intervention.','Retrieve earlier states, outcomes and reflections before deciding.','Use the local website to compare results and inspect every action.'],68,372,1110,27,79);
  s.speakerNotes.text='The original selfx folder contained a Python SDN agent, reward, memory and evaluation code, without a website UI. The local dashboard adds a review and replay surface. The research question compares A2 with the same controller without memory, A1.';

  s=base(p,'Control architecture',3);
  const names=['Observe','Retrieve','Decide','Validate','Measure','Reflect'];
  const a=names.map((name,i)=>box(s,name,70+(i%3)*393,i<3?205:425,345,95));
  connect(s,a[0],a[1]);connect(s,a[1],a[2]);connect(s,a[3],a[4]);connect(s,a[4],a[5]);
  s.shapes.connect(a[2],a[3],{kind:'elbow',fromSide:'bottom',toSide:'top',line:{fill:C.teal,width:2}});
  ['Demand + queues','Earlier episodes','Typed JSON','Independent gate','Outcome + reward','Bounded memory'].forEach((v,i)=>text(s,v,76+(i%3)*393,i<3?318:538,332,48,23,C.muted));
  s.speakerNotes.text='The portable runner orchestrates shared modules directly. The retained Ryu adapter uses the original LangGraph pipeline. Invalid output or unsafe actions become visible no-op outcomes. Source: docs/ARCHITECTURE.md.';

  s=base(p,'Two-path fluid topology',4,'A logical network model; no packet testbed is claimed');
  const si=box(s,'s1 / ingress',70,300,240,95),s2=box(s,'s2 / primary',515,180,250,95),s3=box(s,'s3 / alternate',515,440,250,95),so=box(s,'s4 / egress',975,300,240,95);
  connect(s,si,s2);connect(s,si,s3);connect(s,s2,so);connect(s,s3,so);
  text(s,'10 Mbps per path\n0.5 Mbit buffer',445,307,400,100,29,C.teal,true);
  text(s,'8 ms propagation component; five-second windows; one elephant flow plus path-specific background traffic',70,576,1140,65,25);
  s.speakerNotes.text='The diamond is an aggregate two-bottleneck fluid model with logical endpoints, not eight instantiated hosts. Each new window starts its elephant flow on the primary; actions expire per window and queues persist. The separate original Mininet topology remains linear and has no alternate route.';

  s=base(p,'State embedding and episodic memory',5);
  text(s,'Traffic demand + queue occupancy',66,185,1100,65,36,C.teal);
  text(s,'Normalize features → unit vector → cosine similarity',66,280,1130,74,34);
  body(s,['Retrieve four earlier episodes from a memory of at most 30.','Store state, installed action, reward and a concise reflection.','Weights remain fixed. The embedding is a hand-designed numeric representation.'],68,393,1125,27,77);
  s.speakerNotes.text='Features: primary background/10, alternate background/10, elephant/10, primary queue/0.5, alternate queue/0.5, total primary load/10, constant 0.1; then L2 normalization. Lowest-reward pruning retains 30 episodes. A1 has disabled memory. Every seed and condition resets memory. Motivation: Shinn et al., Reflexion, https://arxiv.org/abs/2303.11366 .';

  s=base(p,'Actions and deterministic safety',6);
  table(s,[['Action','Required checks'],['Reroute','Exact flow and switch; alternate load ≤ 90% capacity'],['Rate limit','At most 20% reduction; minimum 512 kbps'],['No-op','Safe fallback for invalid actions or provider failure'] ],64,188,1152,340,[235,917]);
  text(s,'Typed output is necessary. A separate gate decides whether the action can be applied.',66,557,1145,74,28,C.teal);
  s.speakerNotes.text='Simulation validation rejects unknown switches, incomplete or mismatched flow identifiers and invalid output ports. Deterministic bounds are local safety constraints, not a proof of network stability or SLA compliance. Reference for separate Ryu flow/meter API: https://ryu.readthedocs.io/en/latest/app/ofctl_rest.html .';

  s=base(p,'Experimental design',7);
  table(s,[['Experiment','Seeds','Windows each','A1 and A2 backend'],['Portable study','5','120','Deterministic policies'],['Paced Gemini','3','24','Real Gemini 3.5 Flash-Lite'],['Free-router diagnostic','1','12','Real free model or visible fallback']],64,183,1152,315,[345,105,210,492]);
  text(s,'A0: static route    B1: feasible least-loaded route\nA1: no episode memory    A2: similar-state memory',68,531,1120,100,28);
  s.speakerNotes.text='Same traffic bytes and zero initial queues for every condition. SHA256 values are stored in summaries. Main offline experiment: 5×120×4=2400 windows, 600 simulated seconds per seed and condition. API pilots are smaller and are not real-time packet emulation. Paired seed-level Student-t intervals avoid treating windows as independent replicates.';

  s=base(p,'Offline latency results',8,'Five seeds; 600 windows per controller; modeled delay in ms');
  bar(s,Object.values(off).map(v=>v.latency_ms),'Modeled latency (ms)');
  text(s,'Memory did not improve\nthe offline controller',860,205,340,125,34,C.teal,true);
  text(s,`A1: ${f(off.A1.latency_ms)} ms\nA2: ${f(off.A2.latency_ms)} ms\n\nA2 minus A1:\n+${f(off.A2.latency_ms-off.A1.latency_ms)} ms`,865,367,330,220,29);
  s.speakerNotes.text=source+'. These are deterministic policy results, not LLM benchmark scores. A2 has lower delay than static A0 but higher delay than A1. The same-controller memory comparison is the central question.';

  s=base(p,'Goodput and total loss',9,'Mean window loss includes deliberate meter drops');
  table(s,[['Controller','Goodput Mbps','Mean total loss %','Safety vetoes'],...Object.entries(off).map(([k,v])=>[k,f(v.throughput_kbps/1000,3),f(v.loss_pct,3),String(v.safety_vetoes)])],64,183,1152,350,[255,299,338,260]);
  text(s,'A2 traded lower delay than A0 for lower goodput and more loss.\nLatency alone is insufficient evidence of a better controller.',68,557,1130,76,27,C.teal);
  s.speakerNotes.text=source+'. Pooled volume loss differs from the arithmetic mean of per-window loss; both statistics are retained in summary.json. A2 reuse sometimes proposes an infeasible action, which is vetoed.';

  s=base(p,'Interpreting reflection and memory',10);
  text(s,`${off.A2.safety_vetoes} vetoes in the offline memory condition`,65,190,1145,85,43,C.teal);
  body(s,['A similar state can require a different feasible action.','Reward pruning can discard informative failed episodes.','A stored explanation supports adaptation; it does not guarantee improvement.'],67,325,1120,30,98);
  s.speakerNotes.text='The submitted offline trace contains 62 vetoes for A2. Future studies could compare feasibility-aware retrieval, negative-example retention and recent-window memory. These are hypotheses requiring fresh experiments, not implemented claims of better results. Shinn et al., https://arxiv.org/abs/2303.11366 .';

  s=base(p,'Gemini integration results',11,'Three seeds × 24 windows per controller; network results are simulated');
  bar(s,Object.values(g).map(v=>v.latency_ms),'Modeled latency (ms)',70,190,720,380);
  const coverage=d.coverage.gemini_paced;
  text(s,'288 / 288',860,190,355,90,54,C.teal,true);
  text(s,'successful decision and\nreflection API calls',866,285,335,90,25);
  text(s,`A1 decisions: ${coverage.A1[0]}/${coverage.A1[1]}\nA2 decisions: ${coverage.A2[0]}/${coverage.A2[1]}\n\nVetoes: ${g.A1.safety_vetoes} → ${g.A2.safety_vetoes}`,866,407,330,170,27);
  text(s,`A2 latency differs from A1 by ${f(g.A2.latency_ms-g.A1.latency_ms,3)} ms; goodput and loss are equal.`,70,594,1135,55,25,C.teal);
  s.speakerNotes.text=source+'. Exact endpoint: gemini-3.5-flash-lite. All 288 paced calls succeeded; no decision fallback. A1 and A2 each contain 72 control windows and 72 reflections. The earlier unpaced quota failure is preserved separately. This small difference does not establish a robust performance advantage. Pacing plus two calls exceeds a five-second real-time deadline. Official sources: https://ai.google.dev/gemini-api/docs/models and https://ai.google.dev/gemini-api/docs/rate-limits .';

  s=base(p,'Free model availability',12,'One structured healthy-network check per discovered zero-price model ID');
  text(s,`${d.free_models.ok} / ${d.free_models.checked}`,65,186,610,150,88,C.teal,true);
  text(s,'models returned valid decisions',72,343,640,70,32);
  text(s,`${d.free_models.checked-d.free_models.ok} checks were unavailable\nor unsuitable in this run.`,750,200,450,120,31);
  text(s,`Free-router diagnostic:\nA1 API decisions ${d.coverage.openrouter.A1[0]}/${d.coverage.openrouter.A1[1]}\nA2 API decisions ${d.coverage.openrouter.A2[0]}/${d.coverage.openrouter.A2[1]}`,750,376,450,170,28);
  text(s,'Availability and JSON compatibility are separate from control quality.',70,572,1135,55,29,C.teal);
  s.speakerNotes.text=`Source: output/free_model_checks.json and output/experiments/openrouter/provider_calls.json. The catalog returned ${d.free_models.checked} zero-price :free IDs; ${d.free_models.ok} passed. Some errors were HTTP 403/429 or incomplete/non-JSON output. Router model identity varies and is recorded. Paid OpenRouter model IDs are blocked by the adapter. https://openrouter.ai/docs/guides/routing/routers/free-router .`;

  s=base(p,'Related work',13);
  table(s,[['Work','Relevance','Comparison boundary'],['Reflexion (2023)','Verbal feedback and episode memory','Different tasks; no SDN score transfer'],['RouteNet (2019)','Topology-aware network KPI modeling','15.4% worst-case MRE is prediction error'],['Local A0 and B1','Static and feasible greedy baselines','Measured on the same demand']],64,187,1152,340,[285,415,452]);
  text(s,'Published measurements retain their original task and units.\nThey are not substituted for local experimental results.',68,564,1130,77,27,C.teal);
  s.speakerNotes.text='Shinn et al., Reflexion: https://arxiv.org/abs/2303.11366 . Rusek et al., RouteNet: https://arxiv.org/abs/1910.01508 . RouteNet reports worst-case mean relative error 15.4% for its KPI prediction evaluation; this is not a latency reduction and is not reproduced here.';

  s=base(p,'Engineering corrections and validation',14);
  body(s,['Outputs and experiment paths stay inside selfx.','Metered OpenFlow rules preserve observed forwarding.','Rerouting requires a validated alternative egress.','Tests cover conservation, reproducibility, provider fallback and dashboard access.'],68,180,1125,31,108);
  s.speakerNotes.text='Tests include the original graph, safety, memory, reward, counter and result writer tests plus portable simulation and dashboard checks. Browser validation covers decision navigation, offline replay, JavaScript errors and mobile overflow. Linux Mininet/Ryu deployment remains unvalidated on Windows.';

  s=base(p,'Limitations and next experiments',15);
  body(s,['The fluid model is not packet capture or a physical-network measurement.','The hand-designed embedding has no formal learning or stability guarantee.','Paced live API calls do not meet a five-second real-time deadline.','Next: endpoint-instrumented Linux tests, fixed models, more workloads and topologies.'],68,183,1120,30,109);
  s.speakerNotes.text='No TCP dynamics, scheduling, real NetFlow collection, packet RTT or p95 measurement is implemented in the portable model. Captured dataset calibration and generalization studies remain. Request quotas are external constraints. The scientific conclusion is limited to the implemented workload and topology.';

  const finalSlide=d.benchmark ? appendBenchmarkSlides(p,d,{base,text,table}) : 16;
  s=base(p,'Reproduce and inspect the evidence',finalSlide,'Run from C:\\Users\\RAVIPRAKASH\\SDN\\SDN\\selfx',true);
  text(s,'.\\run.ps1 all\n.\\run.ps1 benchmark\n.\\run.ps1 dashboard',70,182,1120,205,38,C.white);
  text(s,'README → project guide → architecture → experimental protocol',72,444,1105,65,27,'#B7D6CD');
  text(s,'CSV + JSONL evidence · Editable DOCX and PPTX · Report and slide PDFs',72,541,1105,65,25,'#B7D6CD');
  s.speakerNotes.text='Saved API evidence can be inspected without new calls. New live experiments require credentials and remaining quota. All source and deliverable paths remain inside selfx. The package excludes .env, caches and local dependency folders.';
  return {slides:p.slides.items.length};
}
