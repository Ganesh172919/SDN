"""Publication figures and a PDF atlas, generated only from saved measurements."""
from __future__ import annotations
import csv
import json
from pathlib import Path
from statistics import mean
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import MaxNLocator

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'output/benchmarks/v2'
FIG=ROOT/'output/figures/benchmarks'
COLORS={'A0':'#93a5a0','B1':'#467d91','B2':'#a277b3','A1':'#328f9c','A2':'#d28244','H1':'#234f7d','A3':'#007d64','O1':'#423c48'}
SHORT={'mixed':'Mixed load','flash':'Flash crowd','alternate':'Busy alternate','shift':'Load shift','overload':'Dual overload','light':'Light load'}


def read():
    s=json.loads((FOLDER/'summary.json').read_text(encoding='utf-8'))
    rows=list(csv.DictReader((FOLDER/'metrics.csv').open(encoding='utf-8')))
    return s,rows


def chart_data(s,rows):
    order=list(s['controllers']);scenarios=list(s['scenarios'])
    overall={}
    for condition in order:
        per_seed={}
        for seed in s['seeds']:
            per_seed[str(seed)]={metric:mean(s['groups'][scenario][condition]['seed_metrics'][str(seed)][metric] for scenario in scenarios)
                                  for metric in ('latency_ms','throughput_kbps','loss_pct','control_elapsed_ms','window_latency_p95_ms')}
        overall[condition]={metric:mean(p[metric] for p in per_seed.values()) for metric in next(iter(per_seed.values()))}
        overall[condition]['vetoes']=sum(s['groups'][scenario][condition]['vetoes'] for scenario in scenarios)
        overall[condition]['seed_means']=per_seed
        selected=[float(r['control_elapsed_ms']) for r in rows if r['condition']==condition]
        overall[condition]['decision_p95_ms']=float(np.quantile(selected,.95))
    return {'overall':overall,'scenario_latency':{sc:{c:s['groups'][sc][c]['metrics']['latency_ms']['mean'] for c in order} for sc in scenarios},
            'count':s['window_count'],'seeds':len(s['seeds']),'cycles':s['cycles'],'scenarios':s['scenarios'],'controllers':s['controllers'],'wall_seconds':s['wall_seconds'],
            'paired':s['paired_comparisons']}


def create():
    s,rows=read();d=chart_data(s,rows);FIG.mkdir(parents=True,exist_ok=True)
    order=list(s['controllers']);scenarios=list(s['scenarios'])
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':14,'text.color':'#15343b','axes.labelcolor':'#15343b','axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white'})
    pdf=ROOT/'output/submission/SELF_X_Benchmark_Atlas.pdf';pdf.parent.mkdir(parents=True,exist_ok=True)
    inventory=[]
    with PdfPages(pdf) as atlas:
        def save(fig,name,title,caption):
            fig.suptitle(title,x=.03,ha='left',fontsize=16,fontweight='bold')
            fig.text(.03,.015,caption,fontsize=8,color='#536c70',ha='left')
            fig.savefig(FIG/(name+'.png'),dpi=190)
            fig.savefig(FIG/(name+'.svg'))
            atlas.savefig(fig)
            inventory.append({'id':name,'title':title,'caption':caption,'png':str((FIG/(name+'.png')).relative_to(ROOT)),'svg':str((FIG/(name+'.svg')).relative_to(ROOT))})
            plt.close(fig)
        fig,ax=plt.subplots(figsize=(12.5,6.6));fig.subplots_adjust(top=.84,bottom=.18,left=.18,right=.95)
        matrix=np.array([[s['groups'][sc][c]['metrics']['latency_ms']['mean'] for c in order] for sc in scenarios])
        im=ax.imshow(matrix,cmap='YlGnBu',aspect='auto',vmin=8,vmax=max(45,matrix.max()))
        ax.set_xticks(range(len(order)),order);ax.set_yticks(range(len(scenarios)),[SHORT[sc] for sc in scenarios])
        for i in range(len(scenarios)):
            for j in range(len(order)):ax.text(j,i,f'{matrix[i,j]:.2f}',ha='center',va='center',color='white' if matrix[i,j]>30 else '#102e36',fontsize=14)
        fig.colorbar(im,ax=ax,label='Mean modeled delay (ms)',shrink=.8)
        save(fig,'scenario_latency_matrix','Delay across six traffic scenarios','10 paired seeds × 120 windows × 8 controllers. Analytical simulation; lower delay is better. O1 is a myopic model reference.')
        fig,axes=plt.subplots(2,3,figsize=(12.5,7));fig.subplots_adjust(top=.84,bottom=.14,hspace=.5,wspace=.3)
        for ax,sc in zip(axes.flat,scenarios):
            stats=[s['groups'][sc][c]['metrics']['latency_ms'] for c in order];vals=np.array([v['mean'] for v in stats]);lo=np.array([v['ci95'][0] for v in stats]);hi=np.array([v['ci95'][1] for v in stats])
            ax.bar(order,vals,color=[COLORS[c] for c in order],yerr=np.maximum(0,np.vstack([vals-lo,hi-vals])),capsize=2,width=.65)
            ax.set_title(s['scenarios'][sc],loc='left',fontsize=13);ax.set_ylabel('Modeled delay (ms)');ax.grid(axis='y',alpha=.13);ax.set_axisbelow(True)
        save(fig,'scenario_latency_intervals','Seed uncertainty by scenario','95% percentile bootstrap intervals across seed means (4,000 resamples). Exploratory comparisons; no multiplicity correction.')
        fig,axes=plt.subplots(1,2,figsize=(12.5,6.6));fig.subplots_adjust(top=.82,bottom=.15,left=.17,wspace=.45,right=.95)
        for ax,pair,title in zip(axes,['A3_minus_A2','A3_minus_H1'],['A3 minus original memory A2','A3 minus guarded no-memory H1']):
            vals=[s['paired_comparisons'][sc][pair]['latency_ms'] for sc in scenarios]
            y=np.arange(len(scenarios));v=np.array([x['mean_difference'] for x in vals]);lo=np.array([x['ci95'][0] for x in vals]);hi=np.array([x['ci95'][1] for x in vals])
            ax.errorbar(v,y,xerr=np.maximum(0,np.vstack([v-lo,hi-v])),fmt='o',color=COLORS['A3'],capsize=4)
            ax.axvline(0,color='#c58652',linestyle='--',linewidth=1);ax.set_yticks(y,[SHORT[sc] for sc in scenarios])
            ax.invert_yaxis();ax.set_title(title,fontsize=14);ax.set_xlabel('Paired delay difference (ms)');ax.grid(axis='x',alpha=.13)
        save(fig,'paired_memory_effect','Memory effect and the guard ablation','Negative differences favor A3. Pairing uses identical scenario and seed. A3 versus H1 isolates memory after the common guard.')
        fig,axes=plt.subplots(1,2,figsize=(12.5,6.6));fig.subplots_adjust(top=.82,bottom=.16,wspace=.3)
        for ax,metric,label in zip(axes,['latency_ms','loss_pct'],['Modeled mean-window delay (ms)','Mean-window total loss (%)']):
            for c in ['A0','B1','A1','A2','H1','A3','O1']:
                values=np.sort([float(r[metric]) for r in rows if r['condition']==c]);cdf=np.arange(1,len(values)+1)/len(values)
                ax.plot(values,cdf,color=COLORS[c],label=c,linewidth=1.6,linestyle='--' if c in ('H1','O1') else '-')
            ax.set_xlabel(label);ax.set_ylabel('Empirical cumulative probability');ax.grid(alpha=.12)
        axes[0].legend(ncol=4,frameon=False,loc='lower right')
        save(fig,'distribution_ecdf','Distributions across all evaluated windows','Equally sampled scenarios and seeds are pooled. These are distributions of model window means, not individual packet measurements.')
        fig,axes=plt.subplots(1,2,figsize=(12.5,6.6));fig.subplots_adjust(top=.82,bottom=.16,wspace=.28)
        for c in order:
            item=d['overall'][c]
            for ax,ykey,scale in [(axes[0],'loss_pct',1),(axes[1],'throughput_kbps',.001)]:
                offset=({'H1':(-34,-13),'O1':(8,7),'A1':(6,-14),'A2':(6,-14)} if ykey=='loss_pct' else {'H1':(-38,-5),'O1':(8,5),'A3':(8,-10),'A1':(8,4),'A2':(8,6)}).get(c,(6,5))
                ax.scatter(item['latency_ms'],item[ykey]*scale,color=COLORS[c],s=65,marker='s' if c=='O1' else 'o')
                ax.annotate(c,(item['latency_ms'],item[ykey]*scale),xytext=offset,textcoords='offset points',fontsize=12)
                ax.grid(alpha=.12);ax.set_xlabel('Mean modeled delay (ms)')
        axes[0].set_ylabel('Mean total loss (%)');axes[1].set_ylabel('Mean delivered goodput (Mbps)')
        save(fig,'metric_tradeoffs','Delay must be assessed with loss and goodput','Each point averages equally over six scenarios and ten seeds. Prefer lower delay and loss, with higher delivered goodput.')
        fig,axes=plt.subplots(1,2,figsize=(12.5,6.6));fig.subplots_adjust(top=.82,bottom=.17,wspace=.25)
        veto=[d['overall'][c]['vetoes'] for c in order];bars=axes[0].bar(order,veto,color=[COLORS[c] for c in order]);axes[0].bar_label(bars,padding=4);axes[0].set_ylabel('Rejected proposals');axes[0].set_ylim(0,max(veto)*1.25 if max(veto) else 1);axes[0].set_title('Safety gate outcomes',loc='left')
        actions=['no_op','reroute','rate_limit'];bottom=np.zeros(len(order))
        for action,color in zip(actions,['#a8b9b4','#2f8a89','#d6a265']):
            values=[100*sum(s['groups'][sc][c]['actions'].get(action,0) for sc in scenarios)/(s['cycles']*len(s['seeds'])*len(scenarios)) for c in order]
            axes[1].bar(order,values,bottom=bottom,label=action,color=color);bottom+=values
        axes[1].set_ylabel('Installed windows (%)');axes[1].legend(frameon=False,ncol=3,fontsize=8,loc='upper center',bbox_to_anchor=(.5,1.16));axes[1].set_ylim(0,100)
        save(fig,'actions_and_vetoes','Guarded retrieval removes infeasible action reuse','A3 validates retrieval candidates against current demand. B2 is an ECMP-style hash with the same independent safety gate.')
        fig,axes=plt.subplots(2,2,figsize=(12.5,6.6));fig.subplots_adjust(top=.82,bottom=.15,hspace=.5,wspace=.24)
        for ax,c in zip(axes.flat,['A1','A2','H1','A3']):
            selected=[r for r in rows if r['scenario']=='shift' and r['condition']==c and int(r['seed'])==s['seeds'][0]]
            q=np.array([[float(r['queue_primary_mbit']),float(r['queue_alternate_mbit'])] for r in selected]).T
            image=ax.imshow(q,aspect='auto',cmap='YlGnBu',vmin=0,vmax=.5,extent=[0,len(selected),1.5,-.5]);ax.axvline(len(selected)/2,color='#d28244',linestyle='--')
            ax.set_yticks([0,1],['Primary','Alternate']);ax.set_xlabel('Window');ax.set_title(c,loc='left')
        fig.colorbar(image,ax=list(axes.flat),label='Queue (Mbit)',shrink=.8,pad=.03)
        save(fig,'queue_shift_heatmap','Queue occupancy before and after a traffic shift','One illustrative trace (seed 1740); alternate background load increases halfway through. This figure is not an aggregate estimator.')
        fig,ax=plt.subplots(figsize=(12.5,6.6));fig.subplots_adjust(top=.82,bottom=.18,left=.12,right=.95)
        med=[d['overall'][c]['control_elapsed_ms'] for c in order];tail=[d['overall'][c]['decision_p95_ms'] for c in order]
        x=np.arange(len(order));ax.bar(x-.18,med,.34,label='Mean control-loop computation',color='#007d64');ax.bar(x+.18,tail,.34,label='P95 control-loop computation',color='#7c9da3');ax.set_xticks(x,order);ax.set_yscale('log');ax.set_ylabel('Elapsed milliseconds (log scale)');ax.legend(frameon=False);ax.grid(axis='y',alpha=.13);ax.set_axisbelow(True)
        save(fig,'offline_control_overhead','Measured offline control overhead','Machine-dependent timing from .venv. Includes observation, decision, validation and measurement; excludes final batched memory persistence.')
    manifest={'schema':'selfx.visuals.v2','figures':inventory,'atlas':str(pdf.relative_to(ROOT)),'chart_data':d}
    (FIG/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (ROOT/'output/benchmark_chart_data.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
    print(f'Created {len(inventory)} PNG/SVG figure pairs and {pdf.name}')
    return d


if __name__=='__main__':create()
