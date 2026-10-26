"""Revision 4 figures, exact chart data and atlas from preserved raw evidence."""
import csv,hashlib,json,textwrap
from collections import Counter
from statistics import mean
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from matplotlib.backends.backend_pdf import PdfPages
from eval.run_benchmarks import bootstrap_interval

ROOT=Path(__file__).resolve().parents[1];FOLDER=ROOT/'output/benchmarks/v4';FIG=FOLDER/'figures'
COLORS={'A0':'#93a5a0','B1':'#467d91','A2':'#d28244','H1':'#234f7d','A3':'#5e9c92','V3':'#8d7ba0','H2':'#59a4ac','A4':'#007d64','O2':'#423c48'}
SHORT={'mixed':'Mixed','flash':'Flash','alternate':'Alt busy','shift':'Shift','overload':'Overload','light':'Light','recurring':'Recurring','volatile':'Volatile'}

def load_json(path):return json.loads(path.read_text(encoding='utf-8'))
def load_rows(path):return list(csv.DictReader(path.open(encoding='utf-8')))

def create():
    s=load_json(FOLDER/'summary.json');rows=load_rows(FOLDER/'metrics.csv')
    live={p:load_json(FOLDER/f'latency_{p}_pooled/summary.json') for p in ('gemini','openrouter')}
    lr={p:load_rows(FOLDER/f'latency_{p}_pooled/metrics.csv') for p in live}
    free=load_json(FOLDER/'free_model_checks.json');overall={}
    for c in s['controllers']:
        per_seed={str(seed):{k:mean(s['groups'][sc][c]['seed_metrics'][str(seed)][k] for sc in s['scenarios']) for k in ('latency_ms','throughput_kbps','loss_pct','reward','control_elapsed_ms')} for seed in s['seeds']}
        selected=[r for r in rows if r['condition']==c]
        overall[c]={**{k:mean(v[k] for v in per_seed.values()) for k in next(iter(per_seed.values()))},'seed_means':per_seed,
            'vetoes':sum(r['safety_allowed']=='False' for r in selected),'p95_control_ms':float(np.quantile([float(r['control_elapsed_ms']) for r in selected],.95)),
            'retrieval_windows':sum(int(r['memory_examples'])>0 for r in selected)}
    paired={}
    for baseline in ('H1','H2','V3','A2','O2'):
        paired[baseline]={}
        for k in ('latency_ms','loss_pct','throughput_kbps','reward'):
            delta=[overall['A4']['seed_means'][str(seed)][k]-overall[baseline]['seed_means'][str(seed)][k] for seed in s['seeds']]
            paired[baseline][k]={'mean_difference':mean(delta),'ci95':bootstrap_interval(delta)}
    d={'primary':s,'overall':overall,'overall_paired':paired,'live':live,'free':free,
        'test_summary':load_json(ROOT/'output/runtime_validation.json')['checks'][0]['output_tail'].strip().splitlines()[-1]}
    d['learning_curve']={c:[mean(float(r['reward']) for r in rows if r['condition']==c and int(r['cycle'])<=i) for i in range(s['cycles'])] for c in ('H1','H2','A4')}
    d['meter_share']={c:dict(Counter(r['rate_limit_kbps'] for r in rows if r['condition']==c and r['installed_action']=='rate_limit')) for c in ('H2','A4')}
    FIG.mkdir(parents=True,exist_ok=True);inventory=[]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'pdf.fonttype':42,'ps.fonttype':42,'text.color':'#15343b','axes.labelcolor':'#15343b','axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white'})
    def canvas(n=1):
        fig,axs=plt.subplots(1,n,figsize=(12.4,7.0),squeeze=False);fig.subplots_adjust(left=.08,right=.96,top=.84,bottom=.21,wspace=.28);return fig,axs[0]
    with PdfPages(ROOT/'output/submission/SELF_X_Benchmark_Atlas.pdf') as atlas:
        def save(fig,name,title,caption):
            fig.suptitle(title,x=.025,ha='left',fontsize=17,fontweight='bold')
            fig.text(.025,.105,textwrap.fill(caption,165),ha='left',va='top',fontsize=9,color='#536c70')
            fig.savefig(FIG/(name+'.png'),dpi=180);fig.savefig(FIG/(name+'.svg'));atlas.savefig(fig);plt.close(fig)
            inventory.append({'id':name,'title':title,'caption':caption,'png':(FIG/(name+'.png')).relative_to(ROOT).as_posix(),'svg':(FIG/(name+'.svg')).relative_to(ROOT).as_posix()})
        fig,axs=plt.subplots(2,4,figsize=(12.4,7));fig.subplots_adjust(left=.07,right=.97,top=.84,bottom=.21,hspace=.6,wspace=.3)
        for ax,sc in zip(axs.flat,s['scenarios']):
            trace=load_json(FOLDER/f'traffic_{sc}_{s["seeds"][0]}.json')
            for key,label,color in [('primary_background_mbps','Primary','#234f7d'),('alternate_background_mbps','Alternate','#d28244'),('elephant_mbps','Elephant','#007d64')]:ax.plot([r[key] for r in trace],label=label,color=color,lw=.85)
            ax.set_title(SHORT[sc],loc='left',fontsize=11);ax.set_ylim(0,12);ax.set_xlabel('Window');ax.set_ylabel('Mbps')
        axs.flat[0].legend(fontsize=7,frameon=False)
        save(fig,'traffic_scenarios','Generated traffic on eight held-out scenarios','One seed shown (1900). 10 paired seeds × 120 windows × 8 scenarios; capacities 10 Mbps per path. Demand traces are synthetic and hash-verified.')
        fig,axes=canvas();ax=axes[0];order=list(s['controllers']);scenarios=list(s['scenarios'])
        matrix=np.array([[s['groups'][sc][c]['metrics']['latency_ms']['mean'] for c in order] for sc in scenarios]);im=ax.imshow(matrix,cmap='YlGnBu',aspect='auto')
        ax.set_xticks(range(len(order)),order);ax.set_yticks(range(8),[SHORT[sc] for sc in scenarios]);fig.colorbar(im,ax=ax,label='Modeled delay (ms)')
        for i in range(8):
            for j in range(len(order)):ax.text(j,i,f'{matrix[i,j]:.1f}',ha='center',va='center',color='white' if matrix[i,j]>35 else '#15343b',fontsize=9)
        save(fig,'scenario_latency_matrix','Modeled delay by scenario and controller','86,400 controller windows, 9,600 unique workload windows. Queue-based fluid delay; no packet RTT or physical-network measurements.')
        fig,axes=canvas(2)
        for ax,k,label in zip(axes,('loss_pct','latency_ms'),('Total loss difference (pp)','Delay difference (ms)')):
            vals=[s['paired_comparisons'][sc]['A4_minus_H1'][k] for sc in scenarios];y=np.arange(8);v=np.array([x['mean_difference'] for x in vals]);ci=np.array([x['ci95'] for x in vals]);ax.errorbar(v,y,xerr=[np.maximum(0,v-ci[:,0]),np.maximum(0,ci[:,1]-v)],fmt='o',color=COLORS['A4'],capsize=3);ax.axvline(0,color='#999',lw=1);ax.set_yticks(y,[SHORT[sc] for sc in scenarios]);ax.invert_yaxis();ax.set_xlabel(label)
        save(fig,'paired_memory_effect','A4 versus H1: loss improves, delay has a tradeoff','A4 minus H1 with paired 95% seed bootstrap intervals (4,000 draws). Negative favors A4. Improvements over H1 include capacity-aware meter logic, not only memory.')
        fig,axes=canvas(2)
        for ax,k,label in zip(axes,('reward','loss_pct'),('Reward difference','Total loss difference (pp)')):
            vals=[s['paired_comparisons'][sc]['A4_minus_H2'][k] for sc in scenarios];v=np.array([x['mean_difference'] for x in vals]);ci=np.array([x['ci95'] for x in vals]);ax.errorbar(v,np.arange(8),xerr=[np.maximum(0,v-ci[:,0]),np.maximum(0,ci[:,1]-v)],fmt='o',color=COLORS['A4'],capsize=3);ax.axvline(0,color='#999',lw=1);ax.set_yticks(range(8),[SHORT[sc] for sc in scenarios]);ax.invert_yaxis();ax.set_xlabel(label);ax.xaxis.set_major_locator(MaxNLocator(5))
        save(fig,'guard_ablation','Matched H2 ablation isolates episodic parameter selection','H2 shares the capacity-aware meter and uses a fixed 0.1 Mbps headroom. A4 explores 0, 0.1 and 0.3 Mbps, then selects using observed prior reward. Cold-start exploration stays in results.')
        fig,axes=canvas(3)
        for ax,k,label,scale in zip(axes,('latency_ms','loss_pct','throughput_kbps'),('Delay (ms)','Total loss (%)','Goodput (Mbps)'),(1,1,.001)):
            cs=['A0','A2','H1','H2','A4','O2'];v=[overall[c][k]*scale for c in cs];bars=ax.bar(cs,v,color=[COLORS[c] for c in cs]);ax.bar_label(bars,labels=[f'{x:.2f}' for x in v],fontsize=8,padding=3);ax.set_ylim(0,max(v)*1.22);ax.set_title(label,fontsize=11);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
        save(fig,'metric_tradeoffs','Delay, loss and delivered goodput together','Equal weight per scenario and seed. All loss includes deliberate meter drops and buffer overflow. H1 and previous v3 A4 match; H2 and A4 differ in parameter selection.')
        fig,axes=canvas(2)
        for ax,k,label in zip(axes,('latency_ms','loss_pct'),('Modeled window delay (ms)','Window total loss (%)')):
            for c in ('H1','H2','A4'):
                v=np.sort([float(r[k]) for r in rows if r['condition']==c]);ax.plot(v,np.arange(1,len(v)+1)/len(v),label=c,color=COLORS[c])
            ax.set_xlabel(label);ax.set_ylabel('Empirical cumulative fraction');ax.legend(frameon=False)
        save(fig,'distribution_ecdf','Distribution of modeled window outcomes','9,600 windows per controller, including overload, transitions and cold start. Individual windows within a seed are dependent; these curves are descriptive.')
        fig,axes=canvas(2)
        for action,color in [('no_op','#93a5a0'),('reroute','#467d91'),('rate_limit','#007d64')]:
            counts=[sum(s['groups'][sc][c]['actions'].get(action,0) for sc in scenarios) for c in order]
            bottom=getattr(axes[0],'_selfx_bottom',np.zeros(len(order)));axes[0].bar(order,counts,bottom=bottom,label=action,color=color);axes[0]._selfx_bottom=bottom+counts
        axes[0].legend(frameon=False,fontsize=9,loc='lower center',bbox_to_anchor=(.5,1.02),ncol=3);axes[0].set_ylabel('Installed windows');axes[1].bar(order,[overall[c]['vetoes'] for c in order],color=[COLORS[c] for c in order]);axes[1].set_ylabel('Safety vetoes')
        save(fig,'actions_and_vetoes','Installed actions and independent safety checks','The unchanged safety limits enforce exact target/route, alternate utilization ≤90%, rate reduction ≤20% and minimum meter 512 kbps.')
        fig,axes=canvas();ax=axes[0]
        for c in ('H1','H2','A4'):
            selected=[r for r in rows if r['scenario']=='shift' and r['condition']==c and int(r['seed'])==1900];ax.plot([int(r['cycle'])+1 for r in selected],[float(r['queue_primary_mbit']) for r in selected],label=c,color=COLORS[c])
        ax.axvline(60.5,color='#d28244',ls='--',label='Alternate load shift');ax.legend(frameon=False);ax.set_xlabel('Window');ax.set_ylabel('Primary queue (Mbit)')
        save(fig,'queue_shift_heatmap','Queue response through a traffic distribution shift','Seed 1900 shown. Queues carry between windows; changing a rule does not erase queued traffic. Each intervention expires after five virtual seconds.')
        fig,axes=canvas();ax=axes[0];cs=['H1','V3','H2','A4'];x=np.arange(4)
        ax.bar(x-.18,[overall[c]['control_elapsed_ms'] for c in cs],.36,label='Mean',color='#007d64');ax.bar(x+.18,[overall[c]['p95_control_ms'] for c in cs],.36,label='P95',color='#467d91');ax.set_xticks(x,cs);ax.set_ylabel('Local control computation (ms)');ax.legend(frameon=False)
        save(fig,'offline_control_overhead','Actual local computation in the isolated .venv','Per-window time includes selection, safety, fluid outcome, reward and memory update. Final batched memory flush excluded. Local timings depend on this machine and concurrent load.')
        fig,axes=canvas(2)
        for ax,p in zip(axes,live):
            groups=live[p]['groups'];x=np.arange(2);ax.bar(x-.18,[groups[m]['control_elapsed_ms']/1000 for m in ('previous','bounded')],.36,label='Mean',color='#007d64');ax.bar(x+.18,[groups[m]['p95_control_ms']/1000 for m in ('previous','bounded')],.36,label='P95',color='#467d91');ax.axhline(5,color='#d28244',ls='--',label='5 s target');ax.set_xticks(x,['Previous','Bounded']);ax.set_title(p.capitalize(),loc='left');ax.set_ylabel('Full control cycle (s)');ax.legend(frameon=False,fontsize=9)
        save(fig,'api_latency_compare','Measured provider integration with five-second traffic arrivals','Two fresh seeds, 24 windows per mode/provider. Observation idle time is separately recorded; all control work, pacing, process startup, cancellation and cleanup is included. Timeouts remain in metrics.')
        fig,axes=canvas(2);fig.subplots_adjust(top=.72)
        origins=['api','api_cache','healthy_bypass','episodic_memory','deadline_fallback','provider_fallback','validation_fallback','fallback_heuristic','local_rule_cache'];colors=['#007d64','#467d91','#aabbb5','#7db0a4','#d28244','#bd6d66','#a277b3','#999','#b4a35b']
        for ax,p in zip(axes,live):
            bottom=np.zeros(2)
            for origin,color in zip(origins,colors):
                v=[live[p]['groups'][m]['origins'].get(origin,0) for m in ('previous','bounded')];ax.bar(['Previous','Bounded'],v,bottom=bottom,label=origin,color=color);bottom+=v
            ax.set_title(p.capitalize(),loc='left');ax.set_ylabel('Control windows')
        fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,.91),ncol=3,frameon=False,fontsize=8)
        save(fig,'api_call_origins','Fresh suggestions, local reuse and fallbacks are separate','A provider timeout is a local client deadline, not a successful response. Admission deferrals start no request. No API work is silently moved outside the control interval.')
        fig,axes=canvas(2)
        for ax,p in zip(axes,lr):
            for mode,color in [('previous','#467d91'),('bounded','#007d64')]:
                v=[float(r['control_elapsed_ms'])/1000 for r in lr[p] if r['mode']==mode];ax.plot(range(1,len(v)+1),v,'o-',label=mode,color=color,ms=3)
            ax.axhline(5,color='#d28244',ls='--');ax.set_title(p.capitalize(),loc='left');ax.set_xlabel('Ordered control window (two seeds)');ax.set_ylabel('Full cycle (s)');ax.legend(frameon=False)
        save(fig,'api_timeline','Control tail latency with all windows retained','Modes use reversed order on the second seed to reduce order bias. Provider variability remains. A 3.8-second local wait budget leaves time for validation and measurement; it is not a hard real-time OS guarantee.')
        fig,axes=canvas();fig.subplots_adjust(left=.43);ax=axes[0];models=free['models'];v=[next((a.get('elapsed_ms',0)/1000 for a in reversed(r['audit']) if a.get('status')=='ok'),0) for r in models];labels=[r['model'].split('/')[-1].replace(':free','') for r in models]
        ax.barh(range(len(models)),v,color=['#007d64' if r['status']=='ok' else '#d28244' for r in models]);ax.set_yticks(range(len(models)),[x[:45] for x in labels],fontsize=8);ax.invert_yaxis();ax.set_xlabel('Schema-valid response time (s)')
        save(fig,'free_model_availability','Availability of every discovered zero-price OpenRouter model',f"{sum(r['status']=='ok' for r in models)}/{len(models)} healthy-network schema checks valid. Zero bar marks unavailable/error, not zero latency. Availability check is separate from network-control quality or provider ranking.")
        fig,axes=canvas(2)
        for ax,c in zip(axes,('H2','A4')):
            selected=[r for r in rows if r['condition']==c and r['installed_action']=='rate_limit'];ratios=[float(r['rate_limit_kbps'])/(1000*float(r['elephant_mbps'])) for r in selected];ax.hist(ratios,bins=np.linspace(.79,1.01,23),color=COLORS[c],edgecolor='white');ax.set_title(c,loc='left');ax.set_xlabel('Admitted elephant fraction');ax.set_ylabel('Meter windows')
        save(fig,'memory_sensitivity','Meter parameters retain more traffic than the fixed 80% rule','H2 uses a capacity-fitting meter with 0.1 Mbps headroom. A4 varies headroom through bounded prior-outcome exploration. The safety floor clips all candidates at at least 80% of elephant demand.')
        fig,axes=canvas();ax=axes[0]
        for c,curve in d['learning_curve'].items():ax.plot(range(1,len(curve)+1),curve,label=c,color=COLORS[c])
        ax.legend(frameon=False);ax.set_xlabel('Prefix length (windows)');ax.set_ylabel('Mean reward over all scenario/seed prefixes')
        save(fig,'memory_learning','Episodic learning includes cold-start exploration cost','Primary evaluation, all eight scenarios and ten seeds. Higher reward is better. H2 is the matched no-memory ablation; an A4 advantage over H1 alone cannot prove an extra memory benefit.')
        fig,axes=canvas(2);fig.subplots_adjust(right=.91,wspace=.45)
        for ax,p in zip(axes,live):
            records=[json.loads(l) for l in (FOLDER/f'latency_{p}_pooled/trace.jsonl').read_text(encoding='utf-8').splitlines()];records=[r for r in records if r['metrics']['mode']=='bounded' and r['metrics']['seed']==1980]
            x=[r['metrics']['cycle'] for r in records];ax.step(x,[r['rule_event']['effective_output_port'] for r in records],where='post',label='Output port',color='#467d91');ax.set_yticks([2,3],['2 primary','3 alternate']);ax.set_xlabel('Window (rules expire after 5 s)');ax.set_title(p.capitalize(),loc='left')
            other=ax.twinx();other.plot(x,[(r['rule_event']['meter_kbps'] or np.nan)/1000 for r in records],'o',color='#d28244',label='Meter');other.set_ylabel('Meter cap (Mbps)',color='#a65f27')
        save(fig,'rule_lifecycle','Complete simulated rule changes: port, meter and expiry','Saved real-provider and fallback decisions drive a simulated OpenFlow table. Exact match, cookie, instructions, meter cap, prior-rule expiry and final default restoration are recorded. No physical switch is contacted.')
        fig,axes=canvas();ax=axes[0];cs=['H1','H2','A4'];meter=[];overflow=[]
        for c in cs:
            selected=[r for r in rows if r['condition']==c];offered=sum(float(r['offered_mbit']) for r in selected);m=sum(float(r['meter_dropped_mbit']) for r in selected);total=sum(float(r['dropped_mbit']) for r in selected);meter.append(100*m/offered);overflow.append(100*(total-m)/offered)
        ax.bar(cs,meter,label='Meter drops',color='#d28244');ax.bar(cs,overflow,bottom=meter,label='Buffer overflow',color='#467d91');ax.set_ylim(0,max(np.array(meter)+np.array(overflow))*1.23);ax.legend(frameon=False);ax.set_ylabel('Pooled loss / all offered traffic (%)')
        save(fig,'loss_breakdown','Loss accounting keeps deliberate drops visible','Pooled volume loss differs from the arithmetic mean of window loss reported in primary tables. Conservation: prior queues + offered = delivered + all dropped + final queues.')
    sources=['output/benchmarks/v4/summary.json','output/benchmarks/v4/metrics.csv','output/runtime_validation.json','output/benchmarks/v4/free_model_checks.json']
    sources += [f'output/benchmarks/v4/latency_{p}_pooled/{n}' for p in live for n in ('summary.json','metrics.csv','trace.jsonl')]
    (FIG/'manifest.json').write_text(json.dumps({'source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sources},'figures':inventory},indent=2),encoding='utf-8')
    (FOLDER/'chart_data.json').write_text(json.dumps(d,indent=2),encoding='utf-8');return d

if __name__=='__main__':create()
