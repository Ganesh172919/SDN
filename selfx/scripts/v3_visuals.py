"""Latest benchmark PNGs, SVGs and PDF atlas from audited saved measurements."""
import csv,hashlib,json,textwrap
from pathlib import Path
from statistics import mean
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from eval.run_benchmarks import bootstrap_interval

ROOT=Path(__file__).resolve().parents[1];FOLDER=ROOT/'output/benchmarks/v3';FIG=FOLDER/'figures'
COLORS={'A0':'#93a5a0','B1':'#467d91','B2':'#a277b3','A1':'#328f9c','A2':'#d28244','H1':'#234f7d','A3':'#5e9c92','O1':'#423c48','A4':'#007d64'}
SHORT={'mixed':'Mixed','flash':'Flash','alternate':'Alt busy','shift':'Shift','overload':'Overload','light':'Light','recurring':'Recurring','volatile':'Volatile'}
MODES=['legacy','compact','hybrid'];MODE_LABELS=['Two calls','Compact','Hybrid']

def load():
    s=json.loads((FOLDER/'summary.json').read_text());rows=list(csv.DictReader((FOLDER/'metrics.csv').open()))
    live=json.loads((FOLDER/'latency_gemini/summary.json').read_text());lr=list(csv.DictReader((FOLDER/'latency_gemini/metrics.csv').open()))
    sensitivity=json.loads((FOLDER/'memory_sensitivity/summary.json').read_text());sr=list(csv.DictReader((FOLDER/'memory_sensitivity/metrics.csv').open()))
    free=json.loads((FOLDER/'free_model_checks.json').read_text())
    return s,rows,live,lr,sensitivity,sr,free

def data(s,rows,live,sensitivity,free):
    overall={}
    for c in s['controllers']:
        per_seed={str(seed):{m:mean(s['groups'][sc][c]['seed_metrics'][str(seed)][m] for sc in s['scenarios']) for m in ('latency_ms','throughput_kbps','loss_pct','reward','control_elapsed_ms')} for seed in s['seeds']}
        selected=[r for r in rows if r['condition']==c]
        overall[c]={**{m:mean(v[m] for v in per_seed.values()) for m in next(iter(per_seed.values()))},'seed_means':per_seed,
            'vetoes':sum(s['groups'][sc][c]['vetoes'] for sc in s['scenarios']),
            'decision_p95_ms':float(np.quantile([float(r['control_elapsed_ms']) for r in selected],.95)),
            'retrieval_windows':sum(int(r['memory_examples'])>0 for r in selected)}
    paired={}
    for base in ('A3','H1'):
        paired[base]={}
        for metric in ('latency_ms','throughput_kbps','loss_pct','reward'):
            differences=[overall['A4']['seed_means'][str(seed)][metric]-overall[base]['seed_means'][str(seed)][metric] for seed in s['seeds']]
            paired[base][metric]={'mean_difference':mean(differences),'ci95':bootstrap_interval(differences)}
    legacy=live['groups']['legacy']['control_elapsed_ms']
    return {'primary':s,'overall':overall,'overall_paired':paired,'live':live,'sensitivity':sensitivity,
        'free_models':{'ok':sum(x['status']=='ok' for x in free['models']),'checked':len(free['models'])},
        'latency_reduction_pct':{m:100*(1-live['groups'][m]['control_elapsed_ms']/legacy) for m in ('compact','hybrid')}}

def create():
    s,rows,live,lr,sensitivity,sr,free=load();d=data(s,rows,live,sensitivity,free)
    d['learning_curve']={}
    for c in sensitivity['controllers']:
        selected=[r for r in sr if r['scenario']=='excess_0001' and r['condition']==c]
        rewards=[mean(float(r['reward']) for r in selected if int(r['cycle'])==i) for i in range(120)]
        d['learning_curve'][c]=(np.cumsum(rewards)/np.arange(1,121)).tolist()
    runtime=json.loads((ROOT/'output/runtime_validation.json').read_text())
    d['test_summary']=runtime['checks'][0]['output_tail'].strip().splitlines()[-1]
    FIG.mkdir(parents=True,exist_ok=True);final=ROOT/'output/submission';final.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'text.color':'#15343b','axes.labelcolor':'#15343b','axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white'})
    order=list(s['controllers']);scenarios=list(s['scenarios']);inventory=[]
    with PdfPages(final/'SELF_X_Benchmark_Atlas.pdf') as atlas:
        def save(fig,name,title,caption):
            fig.suptitle(title,x=.025,ha='left',fontsize=17,fontweight='bold');fig.text(.025,.075,textwrap.fill(caption,170),ha='left',va='top',fontsize=9,color='#536c70')
            fig.savefig(FIG/(name+'.png'),dpi=190);fig.savefig(FIG/(name+'.svg'));atlas.savefig(fig)
            inventory.append({'id':name,'title':title,'caption':caption,'png':str((FIG/(name+'.png')).relative_to(ROOT)),'svg':str((FIG/(name+'.svg')).relative_to(ROOT))});plt.close(fig)
        fig,axes=plt.subplots(2,4,figsize=(14,7.5));fig.subplots_adjust(top=.86,bottom=.18,left=.06,right=.98,hspace=.6,wspace=.33)
        for ax,sc in zip(axes.flat,scenarios):
            trace=json.loads((FOLDER/f'traffic_{sc}_{s["seeds"][0]}.json').read_text())
            ax.plot([v['primary_background_mbps']+v['elephant_mbps'] for v in trace],label='Primary offered',color=COLORS['A4'])
            ax.plot([v['alternate_background_mbps'] for v in trace],label='Alternate background',color=COLORS['H1'],alpha=.8)
            ax.axhline(10,color='#c58652',ls='--',lw=1);ax.set_title(SHORT[sc],loc='left');ax.set_ylabel('Mbps');ax.set_xlabel('Window')
        axes.flat[0].legend(fontsize=7,frameon=False)
        save(fig,'traffic_scenarios','Generated traffic used by every controller','Illustrative seed 1760. Ten matched seeds per scenario; virtual five-second windows. These are synthetic aggregate flow demands.')
        fig,ax=plt.subplots(figsize=(14,7.5));fig.subplots_adjust(top=.86,bottom=.16,left=.13,right=.96)
        matrix=np.array([[s['groups'][sc][c]['metrics']['latency_ms']['mean'] for c in order] for sc in scenarios])
        im=ax.imshow(matrix,cmap='YlGnBu',vmin=8,vmax=40,aspect='auto');ax.set_xticks(range(len(order)),order);ax.set_yticks(range(len(scenarios)),[SHORT[sc] for sc in scenarios])
        for i in range(len(scenarios)):
            for j in range(len(order)):ax.text(j,i,f'{matrix[i,j]:.2f}',ha='center',va='center',color='white' if matrix[i,j]>29 else '#102e36')
        fig.colorbar(im,ax=ax,shrink=.8,label='Mean modeled delay (ms)')
        save(fig,'scenario_latency_matrix','Held-out delay across eight traffic scenarios','86,400 windows = 8 scenarios × 10 held-out seeds × 120 windows × 9 controllers. O1 is a privileged myopic model reference.')
        for baseline,name,title in [('A3','paired_memory_effect','Adaptive memory compared with previous guarded memory'),('H1','guard_ablation','The memory ablation after the same base guard')]:
            fig,axes=plt.subplots(1,2,figsize=(14,7.5));fig.subplots_adjust(top=.83,bottom=.16,left=.13,right=.96,wspace=.35)
            for ax,metric,label in zip(axes,('latency_ms','loss_pct'),('Modeled delay difference (ms)','Total loss difference (percentage points)')):
                stats=[s['paired_comparisons'][sc]['A4_minus_'+baseline][metric] for sc in scenarios];values=np.array([v['mean_difference'] for v in stats]);low=np.array([v['ci95'][0] for v in stats]);high=np.array([v['ci95'][1] for v in stats]);y=np.arange(len(stats))
                ax.errorbar(values,y,xerr=np.maximum(0,np.vstack([values-low,high-values])),fmt='o',capsize=4,color=COLORS['A4']);ax.set_yticks(y,[SHORT[sc] for sc in scenarios]);ax.invert_yaxis();ax.axvline(0,color='#c58652',ls='--');ax.set_xlabel(label);ax.grid(axis='x',alpha=.13)
            save(fig,name,title,f'A4 minus {baseline}. Negative favors A4. 95% paired seed bootstrap intervals, 4,000 draws; exploratory with no multiplicity correction.')
        fig,axes=plt.subplots(1,2,figsize=(14,7.5));fig.subplots_adjust(top=.84,bottom=.17,wspace=.3,left=.08,right=.96)
        for ax,metric,label in zip(axes,('loss_pct','throughput_kbps'),('Mean total loss (%)','Mean delivered goodput (Mbps)')):
            for c in order:
                v=d['overall'][c];factor=.001 if metric=='throughput_kbps' else 1
                marker='s' if c=='O1' else 'o';ax.scatter(v['latency_ms'],v[metric]*factor,s=75,color=COLORS[c],marker=marker)
                if c!='H1':
                    offsets=({'A4':(8,5),'O1':(8,-15),'A3':(8,10)} if metric=='loss_pct' else {'A4':(8,0),'O1':(8,20),'A3':(8,-15)})
                    ax.annotate('H1 / A4' if c=='A4' else c,(v['latency_ms'],v[metric]*factor),xytext=offsets.get(c,(8,4)),textcoords='offset points',fontsize=11)
            ax.set_xlabel('Mean modeled delay (ms)');ax.set_ylabel(label);ax.grid(alpha=.13)
        save(fig,'metric_tradeoffs','Delay must be judged together with loss and goodput','Equal weights across the eight primary scenarios and ten paired seeds. A4 overlaps H1; their estimates are identical in this suite.')
        fig,axes=plt.subplots(1,2,figsize=(14,7.5));fig.subplots_adjust(top=.84,bottom=.18,wspace=.3,left=.08,right=.96)
        for ax,metric,label in zip(axes,('latency_ms','loss_pct'),('Modeled mean-window delay (ms)','Mean-window total loss (%)')):
            for c in ('A0','A2','A3','H1','A4','O1'):
                values=np.sort([float(r[metric]) for r in rows if r['condition']==c]);ax.plot(values,np.arange(1,len(values)+1)/len(values),label=c,color=COLORS[c],ls='--' if c in ('H1','O1') else '-')
            ax.set_xlabel(label);ax.set_ylabel('Empirical cumulative probability');ax.grid(alpha=.13)
        axes[0].legend(frameon=False,ncol=3,loc='lower right')
        save(fig,'distribution_ecdf','Distributions over the measured simulation windows','These are distributions of modeled window means, not packet-delay distributions. A4 and H1 curves overlap.')
        fig,axes=plt.subplots(1,2,figsize=(14,7.5));fig.subplots_adjust(top=.84,bottom=.18,wspace=.28,left=.07,right=.97)
        values=[d['overall'][c]['vetoes'] for c in order];bars=axes[0].bar(order,values,color=[COLORS[c] for c in order]);axes[0].bar_label(bars,padding=4);axes[0].set_ylim(0,max(values)*1.2);axes[0].set_ylabel('Rejected proposals')
        bottom=np.zeros(len(order))
        for action,color in zip(('no_op','reroute','rate_limit'),('#a8b9b4','#2f8a89','#d6a265')):
            vals=[100*sum(r['installed_action']==action for r in rows if r['condition']==c)/(s['window_count']/len(order)) for c in order]
            axes[1].bar(order,vals,bottom=bottom,label=action,color=color);bottom+=vals
        axes[1].set_ylabel('Installed windows (%)');axes[1].legend(frameon=False,ncol=3,fontsize=9,loc='upper center',bbox_to_anchor=(.5,1.1))
        save(fig,'actions_and_vetoes','Action feasibility and installed behavior','All controllers share the independent action validator. A4 had zero rejected proposals; this does not by itself prove a performance improvement.')
        fig,axes=plt.subplots(2,2,figsize=(14,7.5));fig.subplots_adjust(top=.84,bottom=.17,left=.1,right=.86,hspace=.55,wspace=.35)
        for ax,c in zip(axes.flat,('A2','A3','H1','A4')):
            selected=[r for r in rows if r['scenario']=='shift' and r['condition']==c and int(r['seed'])==1760]
            values=np.array([[float(r['queue_primary_mbit']),float(r['queue_alternate_mbit'])] for r in selected]).T
            im=ax.imshow(values,aspect='auto',vmin=0,vmax=.5,cmap='YlGnBu');ax.axvline(60,color='#c58652',ls='--');ax.set_title(c,loc='left');ax.set_yticks([0,1],['Primary','Alternate']);ax.set_xlabel('Window')
        fig.colorbar(im,ax=list(axes.flat),shrink=.8,label='Queue (Mbit)',pad=.04)
        save(fig,'queue_shift_heatmap','Queue occupancy around the alternate-path traffic shift','One illustrative trace, seed 1760. The dashed line marks the demand shift; it is not an aggregate estimator.')
        fig,ax=plt.subplots(figsize=(14,7.5));fig.subplots_adjust(top=.84,bottom=.17,left=.1,right=.97);x=np.arange(len(order))
        ax.bar(x-.18,[d['overall'][c]['control_elapsed_ms'] for c in order],.36,label='Mean',color=COLORS['A4']);ax.bar(x+.18,[d['overall'][c]['decision_p95_ms'] for c in order],.36,label='P95',color='#7c9da3');ax.set_xticks(x,order);ax.set_ylabel('Local computation (ms, log scale)');ax.set_yscale('log');ax.legend(frameon=False)
        save(fig,'offline_control_overhead','Measured control computation in the isolated virtual environment','Includes the control computation, observation and measurement; excludes final batched memory persistence. Timing depends on this computer.')
        fig,axes=plt.subplots(1,2,figsize=(14,7.5));fig.subplots_adjust(top=.84,bottom=.18,left=.08,right=.97,wspace=.3)
        bottom=np.zeros(3)
        for field,label,color in [('pacing_ms','Request pacing','#aabbb5'),('transport_ms','HTTP and service','#467d91')]:
            values=np.array([live['groups'][m][field]/1000 for m in MODES]);axes[0].bar(MODE_LABELS,values,bottom=bottom,label=label,color=color);bottom+=values
        local=np.array([max(0,(live['groups'][m]['control_elapsed_ms']-live['groups'][m]['pacing_ms']-live['groups'][m]['transport_ms'])/1000) for m in MODES]);axes[0].bar(MODE_LABELS,local,bottom=bottom,label='Local work',color=COLORS['A4']);axes[0].axhline(5,ls='--',color='#c58652');axes[0].set_ylabel('Mean full cycle (seconds)');axes[0].legend(frameon=False,fontsize=10)
        values=[live['groups'][m]['p95_control_ms']/1000 for m in MODES];bars=axes[1].bar(MODE_LABELS,values,color=['#d28244','#467d91','#007d64']);axes[1].bar_label(bars,fmt='%.2f',label_type='center',color='white',fontweight='bold');axes[1].set_ylim(0,max(values)*1.2);axes[1].axhline(5,ls='--',color='#c58652');axes[1].set_ylabel('P95 full cycle (seconds)')
        save(fig,'api_latency_compare','Actual Gemini control latency after the pipeline changes','Two fresh seeds, 24 cycles per mode. Full-cycle timing includes reflection and pacing. Smaller call counts do not prove a faster provider server.')
        fig,axes=plt.subplots(1,2,figsize=(14,7.5));fig.subplots_adjust(top=.84,bottom=.18,left=.08,right=.97,wspace=.3)
        origins=['api','api_cache','episodic_memory','healthy_bypass','fallback_heuristic','fallback_no_op'];bottom=np.zeros(3)
        for origin,color in zip(origins,('#467d91','#007d64','#7db0a4','#aabbb5','#d28244','#b44c47')):
            values=np.array([live['groups'][m]['origins'].get(origin,0) for m in MODES]);axes[0].bar(MODE_LABELS,values,bottom=bottom,label=origin,color=color);bottom+=values
        axes[0].set_ylabel('Decision windows');axes[0].legend(frameon=False,fontsize=9,ncol=2,loc='lower center',bbox_to_anchor=(.5,1.02))
        values=[live['groups'][m]['api_calls'] for m in MODES];bars=axes[1].bar(MODE_LABELS,values,color=['#d28244','#467d91','#007d64']);axes[1].bar_label(bars,padding=4);axes[1].set_ylim(0,max(values)*1.2);axes[1].set_ylabel('Actual provider requests')
        save(fig,'api_call_origins','Provider work and local reuse are counted separately','Cache, bypass, memory reuse and provider failures are never labeled as new successful API decisions. Local reflection makes no provider request.')
        fig,axes=plt.subplots(1,2,figsize=(14,7.5));fig.subplots_adjust(top=.84,bottom=.18,left=.08,right=.97,wspace=.25)
        for ax,seed in zip(axes,live['seeds']):
            for mode,color in zip(MODES,('#d28244','#467d91','#007d64')):
                selected=[r for r in lr if int(r['seed'])==seed and r['mode']==mode];ax.plot([int(r['cycle'])+1 for r in selected],[float(r['control_elapsed_ms'])/1000 for r in selected],'-o',ms=4,label=mode,color=color)
            ax.axhline(5,color='#c58652',ls='--');ax.set_title(f'Seed {seed}',loc='left');ax.set_ylabel('Full cycle (seconds)');ax.set_xlabel('Window');ax.legend(frameon=False)
        save(fig,'api_timeline','Measured full-cycle latency by simulated traffic window','Mode order reverses on the second seed. Timing includes all decision and reflection work; the dashed line is the five-second target.')
        fig,ax=plt.subplots(figsize=(14,7.5));fig.subplots_adjust(top=.85,bottom=.16,left=.48,right=.94)
        models=free['models'];values=[sum(a.get('elapsed_ms',0) for a in m['audit'])/1000 for m in models]
        ax.barh(range(len(models)),values,color=['#007d64' if m['status']=='ok' else '#d28244' for m in models]);ax.set_yticks(range(len(models)),[m['model'] for m in models],fontsize=10);ax.invert_yaxis();ax.set_xlabel('Elapsed request time including pacing (seconds)')
        from matplotlib.patches import Patch
        ax.legend(handles=[Patch(color='#007d64',label='Valid action JSON'),Patch(color='#d28244',label='Unavailable or unsuitable')],loc='lower right',frameon=False,fontsize=10)
        save(fig,'free_model_availability',f'Compact free-model checks: {d["free_models"]["ok"]}/{len(models)} valid responses','One healthy-network schema check for every discovered zero-price :free model. Availability is not a congestion-control quality benchmark.')
        fig,axes=plt.subplots(1,3,figsize=(14,7.5));fig.subplots_adjust(top=.82,bottom=.21,left=.07,right=.98,wspace=.35)
        levels=list(sensitivity['levels_mbps']);labels=[str(sensitivity['levels_mbps'][k]) for k in levels]
        for ax,metric,label in zip(axes,('reward','loss_pct','latency_ms'),('Mean reward','Mean total loss (%)','Mean modeled delay (ms)')):
            for c in ('H1','A3','A4','O1'):
                ax.plot(labels,[sensitivity['groups'][k][c]['metrics'][metric]['mean'] for k in levels],marker='o',label=c,color=COLORS[c],ls='--' if c in ('A3','O1') else '-')
            ax.set_xlabel('Primary excess above 10 Mbps');ax.set_ylabel(label);ax.tick_params(axis='x',rotation=30);ax.grid(alpha=.13)
        axes[0].legend(frameon=False,ncol=2)
        save(fig,'memory_sensitivity','Targeted memory diagnostic near the capacity boundary','Post-hoc constructed stress test, separate from the primary average. Ten seeds per level; all cold-start windows retained. Higher reward trades delay against goodput and loss.')
        fig,axes=plt.subplots(1,2,figsize=(14,7.5));fig.subplots_adjust(top=.84,bottom=.18,left=.08,right=.97,wspace=.28)
        for c in ('H1','A3','A4','O1'):
            selected=[r for r in sr if r['scenario']=='excess_0001' and r['condition']==c]
            reward=[mean(float(r['reward']) for r in selected if int(r['cycle'])==i) for i in range(120)]
            rate=[100*mean(r['installed_action']=='rate_limit' for r in selected if int(r['cycle'])==i) for i in range(120)]
            axes[0].plot(range(1,121),np.cumsum(reward)/np.arange(1,121),label=c,color=COLORS[c],ls='--' if c in ('A3','O1') else '-');axes[1].plot(range(1,121),rate,label=c,color=COLORS[c],ls='--' if c in ('A3','O1') else '-')
        axes[0].set_ylabel('Cumulative mean observed reward');axes[1].set_ylabel('Seeds choosing rate_limit (%)');axes[0].legend(frameon=False,ncol=2)
        for ax in axes:ax.set_xlabel('Window');ax.grid(alpha=.13)
        save(fig,'memory_learning','Memory adapts after observed harmful throttling','Constructed excess = 0.0001 Mbps diagnostic. A4 learns from earlier action outcomes; the plotted privileged O1 reference has simulator access.')
    sources=[FOLDER/'summary.json',FOLDER/'metrics.csv',FOLDER/'latency_gemini/summary.json',FOLDER/'latency_gemini/metrics.csv',FOLDER/'memory_sensitivity/summary.json',FOLDER/'free_model_checks.json']
    manifest={'schema':'selfx.visuals.v3','figures':inventory,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'atlas_pages':len(inventory)}
    (FIG/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');(FOLDER/'chart_data.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
    print(f'Created {len(inventory)} PNG/SVG pairs and the benchmark atlas');return d

if __name__=='__main__':create()
