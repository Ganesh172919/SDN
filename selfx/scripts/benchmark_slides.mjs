export function appendBenchmarkSlides(p,d,{base,text,table}){
 const b=d.benchmark,keys=Object.keys(b.controllers),colors=['#D28244','#234F7D','#007D64'];let s;
 function chart(slide,categories,series,format='0.00',legend=false){return slide.charts.add('bar',{position:{left:70,top:180,width:1135,height:380},categories,series,hasLegend:legend,
  legend:{position:'top',textStyle:{fontSize:22}},barOptions:{direction:'column',grouping:'clustered',gapWidth:90},
  dataLabels:{showValue:!legend,position:'outEnd',numberFormatCode:format,textStyle:{fontSize:21}},
  xAxis:{textStyle:{fontSize:21}},yAxis:{min:0,numberFormatCode:format,textStyle:{fontSize:19},majorGridlines:{fill:'#D9E3DF',width:1}},chartFill:'#F6F8F3',plotAreaFill:'#F6F8F3'});}
 function values(list){return list.map(v=>Number(v.toFixed(6)));}
 s=base(p,'Expanded benchmark coverage',16,'Offline decisions; all network values are simulated');
 text(s,b.count.toLocaleString(),67,178,1100,110,80,'#007D76',true);
 text(s,'measured control windows',72,298,1100,65,33);
 table(s,[['Traffic scenarios','Paired seeds','Windows per condition'],['6','10','120 per seed'],['8 controllers','600 simulated seconds','per scenario and seed']],64,398,1152,180,[380,380,392]);
 text(s,'Includes original A2, guarded H1 and A3, plus a myopic model reference.',68,602,1135,45,25);
 s.speakerNotes.text='Source: output/benchmarks/v2/summary.json. Six scenarios: mixed demand, flash crowd, busy alternate, distribution shift, persistent overload and light load. Eight controllers × six scenarios × ten seeds × 120 windows = 57,600. B2 is a guarded ECMP-style stable flow hash motivated by RFC 2992, https://www.rfc-editor.org/rfc/rfc2992 . O1 has privileged simulator knowledge and is not a long-horizon upper bound.';
 s=base(p,'Scenario delay benchmark',17,'Mean modeled delay in milliseconds; 1,200 windows per cell');
 const short={mixed:'Mixed',flash:'Flash',alternate:'Alt busy',shift:'Shift',overload:'Overload',light:'Light'};
 table(s,[['Scenario',...keys],...Object.entries(b.scenario_latency).map(([sc,v])=>[short[sc],...keys.map(c=>v[c].toFixed(2))])],64,179,1152,350,[184,...keys.map(()=>121)]);
 text(s,'H1: guarded controller without memory\nA3: the same base controller with balanced, feasible memory',70,558,1130,90,27);
 s.speakerNotes.text='Source: output/benchmarks/v2/summary.json. IDs: A0 static; B1 least-loaded; B2 guarded ECMP-style; A1 original threshold; A2 original memory; H1 guarded no memory; A3 guarded balanced memory; O1 myopic model reference. Both paths saturated in persistent overload, so every controller has the same delay mean. Light load is a negative control. Uncertainty intervals and paired differences are in the report and atlas.';
 s=base(p,'Memory after the same guard',18,'Mean modeled delay in ms; bootstrap intervals are in the report');
 const scenarios=Object.keys(b.scenarios);
 chart(s,scenarios.map(sc=>short[sc]),['A2','H1','A3'].map((c,i)=>({name:c,values:values(scenarios.map(sc=>b.scenario_latency[sc][c])),fill:colors[i]})),'0.0',true);
 const delta=b.paired.mixed.A3_minus_H1.latency_ms;
 text(s,`Mixed load: A3 minus H1 = +${delta.mean_difference.toFixed(3)} ms.\nThe added memory did not improve this comparison.`,70,585,1130,70,27,'#007D76');
 s.speakerNotes.text='The shared guard must be isolated from memory. A3 reuses only feasible current actions and balances positive, negative and recent episodes. It never evaluates simulator outcomes to select a policy action. The paired mixed-load bootstrap interval is '+JSON.stringify(delta.ci95)+' ms. Resampling uses ten paired seed differences and 4,000 draws. Exploratory comparisons have no multiplicity correction.';
 s=base(p,'Aggregate performance and feasibility',19,'Equal weights across six scenarios and ten seeds');
 const performanceTable=table(s,[['ID','Delay ms','Goodput Mbps','Mean loss %','Vetoes'],...keys.map(c=>{const v=b.overall[c];return[c,v.latency_ms.toFixed(3),(v.throughput_kbps/1000).toFixed(3),v.loss_pct.toFixed(3),String(v.vetoes)]})],64,177,1152,410,[110,250,280,270,242]);
 performanceTable.cells.block({row:0,column:0,rowCount:9,columnCount:5}).assign({textStyle:{fontSize:23},margins:{top:6,bottom:6,left:12,right:12}});
 text(s,`A2: ${b.overall.A2.vetoes} rejected proposals. A3: ${b.overall.A3.vetoes}. Performance remains a separate question.`,68,609,1135,45,25,'#007D76');
 s.speakerNotes.text='Source: output/benchmark_chart_data.json. Loss includes deliberate meter drops. Lower delay alone is insufficient; the report and atlas contain tradeoffs and empirical distributions. No claim of global learning or stability is made.';
 s=base(p,'Measured offline computation overhead',20,'Mean control-loop computation in ms; excludes final memory flush');
 chart(s,keys,[{name:'Mean elapsed ms',values:values(keys.map(c=>b.overall[c].control_elapsed_ms)),fill:'#007D76'}],'0.000');
 text(s,`Full suite: ${b.wall_seconds.toFixed(2)} seconds in .venv.\nTiming depends on this computer and excludes external API waiting.`,70,586,1130,72,27);
 s.speakerNotes.text='Source: measured perf_counter timings in output/benchmarks/v2/metrics.csv. Each controller uses identical batching for memory persistence to make local computation timing comparable. O1 evaluates several candidates and has a different information advantage. The benchmark atlas also shows P95 computation time and queue heatmaps.';
 s=base(p,'Live API latency and the control deadline',21,'Fresh Gemini pilot executed in the isolated .venv');
 const g=d.fresh_gemini.conditions;
 chart(s,['A1 live cycle','A2 live cycle','5-second budget'],[{name:'Wall seconds per cycle',values:values([g.A1.control_elapsed_ms/1000,g.A2.control_elapsed_ms/1000,5]),fill:'#007D76'}],'0.00');
 text(s,`${d.fresh_gemini_calls.ok}/${d.fresh_gemini_calls.total} fresh API calls succeeded. Pacing keeps the demo reliable;\nthis execution does not establish a five-second real-time controller.`,70,586,1130,73,26,'#007D76');
 s.speakerNotes.text='Source: output/experiments/gemini_venv/summary.json and provider_calls.json. One seed × twelve windows × A1/A2 × decision/reflection gives 48 calls. API timing includes request pacing. Network time is simulated independently. The earlier three-seed, 288-call pilot is retained. The refreshed free-model sweep currently passes '+d.free_models.ok+'/'+d.free_models.checked+' access/schema checks; that is not a network-control ranking.';
 return 22;
}
