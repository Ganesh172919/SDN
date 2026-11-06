"""Render a concise submission report directly from verified Ganesh artifacts."""
from pathlib import Path
from xml.sax.saxutils import escape
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak,Preformatted

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'output/self_improvement/ganesh_20261106/bounded_adoption'
OUTPUT=ROOT/'output/submission/ganesh/Ganesh_Submission_Report.pdf'
WIDTH=A4[0]-88
NAVY=colors.HexColor('#10263F');BLUE=colors.HexColor('#146EB4');LINE=colors.HexColor('#CDD7E2');MUTED=colors.HexColor('#53657A')
S={
 'title':ParagraphStyle('title',fontName='Helvetica-Bold',fontSize=27,leading=32,textColor=NAVY,spaceAfter=10),
 'h1':ParagraphStyle('h1',fontName='Helvetica-Bold',fontSize=17,leading=21,textColor=NAVY,spaceAfter=9),
 'h2':ParagraphStyle('h2',fontName='Helvetica-Bold',fontSize=11,leading=14,textColor=BLUE,spaceBefore=12,spaceAfter=5),
 'body':ParagraphStyle('body',fontName='Helvetica',fontSize=9.5,leading=13.4,textColor=NAVY,spaceAfter=7),
 'small':ParagraphStyle('small',fontName='Helvetica',fontSize=8,leading=10.8,textColor=MUTED,spaceAfter=5),
 'cell':ParagraphStyle('cell',fontName='Helvetica',fontSize=8.7,leading=11.9,textColor=NAVY),
 'head':ParagraphStyle('head',fontName='Helvetica-Bold',fontSize=8.7,leading=11.9,textColor=colors.white),
 'code':ParagraphStyle('code',fontName='Courier',fontSize=7.6,leading=10.8,textColor=NAVY),
}


def p(text,style='body'):return Paragraph(text,S[style])


def table(rows,widths):
    t=Table([[p(escape(str(c)),'head' if i==0 else 'cell') for c in row] for i,row in enumerate(rows)],colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F1F5F9')]),
        ('GRID',(0,0),(-1,-1),.35,LINE),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    return t


def footer(canvas,doc):
    canvas.saveState();canvas.setStrokeColor(LINE);canvas.line(44,34,A4[0]-44,34)
    canvas.setFont('Helvetica',8);canvas.setFillColor(MUTED)
    canvas.drawString(44,21,'SELF-X | Ganesh submission | Verified 06 November 2026 (IST)')
    canvas.drawRightString(A4[0]-44,21,str(doc.page));canvas.restoreState()


def main():
    load=lambda name:json.loads((E/name).read_text(encoding='utf-8'))
    ready=load('submission_readiness.json');completion=load('completion.json');verified=load('submission_verification.json')
    if ready['status']!='ready' or verified['status']!='passed':raise ValueError('verification must pass before report creation')
    h=completion['holdout_summary'];a=completion['weight_attribution'];fresh=verified['fresh_model_predictions'];tests=ready['tests']
    story=[Spacer(1,20),p('EC466 - Software Defined Networks','h2'),p('SELF-X', 'title'),p('Ganesh: Submission Report','h1'),
        p('T20-T25 | IIIT Dharwad | Team SDN_07 | 06 November 2026','small'),Spacer(1,12),
        table([['Submission status','Verified scope'],['READY - GANESH COMPONENT','CPU-trained LoRA action policy, frozen-replay evaluation, audited activation and rollback.']],[185,WIDTH-185]),
        p('What was delivered','h2'),
        p('The component turns approved completed network episodes into training data, fine-tunes real LoRA weights in a pinned pretrained language model, evaluates candidate policies against an incumbent, and activates only candidates that pass a frozen non-regression campaign. The approved bounded-adoption policy is active in its local registry.'),
        table([['Task','Completed implementation / retained evidence'],
            ['T20','Replay curation; source/split hashes; independent seed groups; original-input reconstruction; excluded-case audit.'],
            ['T21','Pinned CPU model backend, constrained action tokens, local structured interface and independent action safety.'],
            ['T22','One actual 120-step LoRA fit; 460,800 trainable parameters; frozen base verified after reloading saved weights.'],
            ['T23','Frozen 576-case stress gate, raw metric replay, training lineage checks and fresh LM decision verification.'],
            ['T24','Promotion, rejection, unchanged pointer on rejection, controlled failure rollback and hash-linked registry audit.'],
            ['T25','Sealed six-seed holdout attribution with identical prompts and memory disabled; 24 on-policy episodes for a later cycle.'],
        ],[45,WIDTH-45]),
        p('Research boundary','h2'),
        p('All network outcomes are calibrated fluid-model or frozen-replay measurements. The selected policy uses a 25% observation-hash rollout threshold for adapted weights and the pinned bare base elsewhere. Live Mininet integration, full governance/DPP coupling, A1-A5 evaluation and topology transfer remain separate team tasks.'),
        p('Data and model record','h2'),
        p('Training/stress/holdout: 1,122 / 576 / 864 episodes. Thirty rejected training cases are retained. Base: HuggingFaceTB/SmolLM2-135M-Instruct, revision 12fd25f77366fa6b3b4b768ec3050bf629380bac. Only LoRA q_proj/v_proj matrices were optimized.','small'),
        PageBreak(),p('Verification and corrections','h1'),
        table([['Check','Result'],
            ['Project regression tests',f"{tests['project_total']} main tests passed plus {tests['subtests']} subtests: {tests['project_selfx']} selfx/evaluation, {tests['slow_loop']} slow-loop and {tests['web']} Web."],
            ['Clean environment',f"{tests['clean_environment']} focused tests passed in a new Python 3.12 environment; pinned dependencies and pip check passed."],
            ['Relocated package',f"{tests['portable_tests']} focused tests, model reload verification and a 12-window backend smoke run passed with original project reads guarded. No forbidden reads or cloud inference calls."],
            ['Replay provenance','All three original replay inputs reproduce the curated train/stress/holdout files and excluded-case audit exactly. Portable source map retained.'],
            ['Actual model decisions',f"{fresh['decisions_checked']:,} decisions checked with fresh inference; no retained cache used. All actions matched. Maximum probability difference {max(c['max_probability_difference'] for c in fresh['campaigns']):.2e} (tolerance {fresh['probability_tolerance']:.0e})."],
            ['Tensor integrity','Reloaded frozen-base parameter hash matches the pre-training hash. Reloaded adapter hash matches the trained artifact and differs from initialization.'],
            ['Lifecycle evidence','Accepted bounded policy; rejected weak checkpoint; rejected full-adapter trial; controlled automatic rollback; approved policy restored.'],
        ],[128,WIDTH-128]),
        p('Issues corrected before submission','h2'),
        p('Malformed active-pointer files now remain inside the explicit no-op/rollback boundary. Rollback predecessors are checked against authorized activation history. Completed rewards and outcomes are independently recomputed. Promotion verifies action probabilities, exact installed decisions, provenance and dataset lineage. Source maps remove reliance on historical absolute replay locations.'),
        p('Retained verification files','h2'),
        p('submission_verification.json contains the fresh inference and source-rebuild results. submission_readiness.json links the passed tests, portability checks and 44 verified source-file hashes. submission_validation/ contains machine-readable test results and relocated-run outputs.','small'),
        PageBreak(),p('Measurements and attribution','h1'),
        table([['Holdout metric','Bare base','Bounded LoRA adoption'],
            ['Cumulative reward, six seeds',f"{h['incumbent']['cumulative_reward']:.6f}",f"{h['candidate']['cumulative_reward']:.6f}"],
            ['Mean reward / observation',f"{h['incumbent']['mean_reward']:.6f}",f"{h['candidate']['mean_reward']:.6f}"],
            ['Modeled latency (ms)',f"{h['incumbent']['latency_ms']:.6f}",f"{h['candidate']['latency_ms']:.6f}"],
            ['Total loss (%)',f"{h['incumbent']['loss_pct']:.6f}",f"{h['candidate']['loss_pct']:.6f}"],
            ['Throughput (Mbps)',f"{h['incumbent']['throughput_kbps']/1000:.6f}",f"{h['candidate']['throughput_kbps']/1000:.6f}"],
            ['Unsafe proposals vetoed',h['incumbent']['proposed_unsafe'],h['candidate']['proposed_unsafe']],
            ['Installed safety violations','0','0'],
        ],[220,130,WIDTH-350]),
        p('Independent seed-level result','h2'),
        p(f"Across six independent seeds and three profiles, mean cumulative reward gain per seed was <b>{a['mean_cumulative_reward_gain']:.6f}</b>; 95% CI [{a['ci95'][0]:.6f}, {a['ci95'][1]:.6f}]. Two-sided paired t-test: <b>p = {a['p_value']:.7f}</b>. Both conditions used the same frozen prompt and memory was disabled. The only learned difference was the LoRA weights within the fixed rollout mask."),
        p('Tradeoffs and selection record','h2'),
        p('Modeled latency and reward improved; loss rose by 0.034125 percentage points and throughput fell slightly. The first full-adapter candidate improved reward but exceeded the unchanged 0.10-point loss-regression allowance and was rejected. The accepted 25% hash-threshold variant selected 136/576 stress and 231/864 holdout observations for adapted weights. Holdout data did not select the deployment variant.'),
        p('Interpretation','h2'),
        p('The result supports bounded weight-adaptation benefit relative to the pinned bare base in this replay model. Learning imitates approved bootstrap behavior. It does not establish superiority to the bootstrap heuristic, full-system A1-A5 significance, live packet performance or unseen-topology transfer.'),
        p('Evaluation convention','h2'),
        p('Candidate and incumbent act on the same frozen observations and queue states. Outcomes are independently simulated for each decision; this is not a sequential deployment run. Independent seeds are the statistical replication unit.','small'),
        PageBreak(),p('Submission and reviewer quickstart','h1'),
        table([['Artifact','Purpose'],
            ['Ganesh_Submission.zip','Component source, adapters, replay inputs, evaluation traces, tests, pinned environment, reports and integrity manifest.'],
            ['Ganesh_Offline_Model.zip','Optional pinned base-model companion, publisher model card, Apache license and model-file checksums. Extract beside the component archive.'],
            ['SHA256SUMS.txt','Release checksums for both archives and this report.'],
        ],[177,WIDTH-177]),
        p('Run from a new directory','h2'),
        p('Extract to a short path. From Ganesh_Submission/, use Python 3.12. Python packages require installation; the optional model companion avoids downloading the base model. No API credentials are needed.'),
        Preformatted('python tools/verify_bundle.py\npython setup_submission.py\ncd selfx\n.venv\\Scripts\\python.exe -m pytest tests/test_self_improvement.py -q\n.venv\\Scripts\\python.exe -m scripts.verify_self_improvement --output tmp/check.json',S['code']),
        p('On Linux/macOS, replace .venv\\Scripts\\python.exe with .venv/bin/python. The root README includes fresh-inference verification, backend smoke execution and new-cycle training commands.','small'),
        p('Evidence directory','h2'),
        p('selfx/output/self_improvement/ganesh_20261106/bounded_adoption/ contains candidate/, registry/, dataset/, promotion_stress/, rejection_stress/, heldout_attribution/, rollback_demo.json, completion.json, submission_verification.json and submission_readiness.json. Original replay files, source_map.json and the rejected full-adapter evidence are retained in its parent folder.','small'),
        p('Integrity and reproducibility','h2'),
        p('Archive paths and CRCs are validated, files have SHA256 manifests, and the packaged implementation must match the 44 source hashes that passed relocation. API keys, .env files, virtual environments, Git state and unrelated student artifacts are excluded. Historical absolute paths in immutable manifests are preserved as provenance; runtime loaders and source maps resolve packaged files.'),
        p('Team handoff','h2'),
        p('The accompanying pending-work audit records Ganesh T20-T25 completed in CPU/frozen-replay scope and preserves the other 33 assignments. The overall course submission still requires those owners to complete their live integration, evaluation and final-system deliverables.'),
    ]
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    SimpleDocTemplate(str(OUTPUT),pagesize=A4,leftMargin=44,rightMargin=44,topMargin=43,bottomMargin=49,
        title='SELF-X Ganesh Submission Report',author='Ganesh / Team SDN_07',subject='Verified T20-T25 component and reproducible evidence').build(story,onFirstPage=footer,onLaterPages=footer)
    print(OUTPUT)


if __name__=='__main__':main()
