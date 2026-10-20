"""Export saved synthetic elephant-demand records, not wire-format IPFIX."""
import csv,json
from pathlib import Path
import config

def export():
    folder=config.PROJECT_ROOT/'output/benchmarks/v4';summary=json.loads((folder/'summary.json').read_text())
    target=folder/'traffic';target.mkdir(exist_ok=True);rows=[]
    for scenario in summary['scenarios']:
        for seed in summary['seeds']:
            for d in json.loads((folder/f'traffic_{scenario}_{seed}.json').read_text()):
                rows.append({'scenario':scenario,'seed':seed,'flow_id':d['flow_id'],'start_virtual_ms':d['cycle']*5000,'end_virtual_ms':(d['cycle']+1)*5000,
                    'logical_src':'10.0.0.1','logical_dst':'10.0.0.8','elephant_bytes_offered':round(d['elephant_mbps']*1e6*5/8),
                    'primary_background_mbps':d['primary_background_mbps'],'alternate_background_mbps':d['alternate_background_mbps'],
                    'provenance':'synthetic_aggregate_not_packet_capture'})
    with (target/'simulated_netflow.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (target/'README.md').write_text('# Simulated traffic records\n\n9,600 generated aggregate flow records feed the primary paired experiment. Virtual time advances in five-second windows. Bytes describe elephant demand only; background path loads are separate. These records are NetFlow-style tabular observations, not captured packets or RFC 7011 IPFIX messages. The original JSON demand traces and SHA256 hashes remain alongside the experiment.\n',encoding='utf-8')
    print(f'Exported {len(rows)} synthetic records to {target}')

if __name__=='__main__':export()
