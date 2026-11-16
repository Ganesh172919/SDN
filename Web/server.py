#!/usr/bin/env python3
"""
server.py - Full-Stack REST Bridge & Web Server for SELF-X SDN Flow Manager
Connects the web dashboard directly to your live Mininet OpenFlow testbed,
Ryu REST Controller (ofctl_rest), LangGraph agent memory, and evaluation logs.

Read-only endpoint contract used by the public dashboard:
        - GET /login -> redirects to the public dashboard; the old login flow is retired.
        - GET /api/status -> {status, ryu_controller, connected_switches, project, course, team}
- GET /api/memory -> {success, is_live_project, source, count, entries} when memory exists,
    otherwise {success: false, is_live_project: false, message}.
- GET /api/ablation -> {success, conditions}, where conditions contains any available
    A0/A1/A2 CSV rows.
- GET /api/results -> validated saved-run metadata summaries.
- GET /api/results/<run_id>/summary -> one validated run summary.
- GET /api/results/<run_id>/metrics -> validated metric time series.
- GET /api/results/<run_id>/trace -> validated safe diagnostic trace, when present.

Network-control helpers remain disabled and return HTTP 409. Arbitrary Ryu proxy
    access is not exposed publicly. Raw Ryu proxy access is not exposed publicly.
    Simulation actions are browser-local.
"""

import os
import json
import csv
import http.server
import re
import socketserver
import sys
from pathlib import Path
import urllib.request
import urllib.error
from urllib.parse import parse_qs, urlsplit

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(WEB_DIR)
for _path in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "selfx")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

try:
    from selfx.eval.result_schema import (
        ResultValidationError,
        validate_metric_record,
        validate_run_metadata,
        validate_summary,
        validate_trace_record,
    )
    from selfx.eval.result_writer import read_run
except ImportError:
    import importlib
    _schema = importlib.import_module("eval.result_schema")
    _writer = importlib.import_module("eval.result_writer")
    ResultValidationError = _schema.ResultValidationError
    validate_metric_record = _schema.validate_metric_record
    validate_run_metadata = _schema.validate_run_metadata
    validate_summary = _schema.validate_summary
    validate_trace_record = _schema.validate_trace_record
    read_run = _writer.read_run

HOST = os.environ.get("SDN_WEB_HOST", "127.0.0.1")
PORT = int(os.environ.get("SDN_WEB_PORT", 5000))
RYU_BASE_URL = os.environ.get("RYU_REST_BASE", "http://127.0.0.1:8080")
RESULTS_ROOT = Path(os.environ.get("SELFX_RESULTS_ROOT", Path(PROJECT_ROOT) / "results")).resolve()
BENCHMARKS_V4_SUMMARY = (Path(PROJECT_ROOT) / "selfx" / "output" / "benchmarks" / "v4" / "summary.json").resolve()
TABLE2_SUMMARY_PATH = (Path(PROJECT_ROOT) / "selfx" / "output" / "ablation_table2" / "table2_ablation_summary.json").resolve()
TABLE5_SUMMARY_PATH = (Path(PROJECT_ROOT) / "selfx" / "output" / "baseline_table5" / "table5_comparison_summary.json").resolve()
DPP_ACCEPTANCE_PATH = (Path(PROJECT_ROOT) / "selfx" / "output" / "dpp_validation" / "dpp_acceptance_summary.json").resolve()
TRANSFER_PATH = (Path(PROJECT_ROOT) / "selfx" / "output" / "transfer_evaluation" / "zero_shot_transfer_report.json").resolve()

# Historical incremental-pipeline study (S0-S5 and baselines).
PIPELINE_DIR = (Path(PROJECT_ROOT) / "selfx" / "output" / "pipeline_study").resolve()
PIPELINE_FILES = {
    "summary": PIPELINE_DIR / "pipeline_summary.json",
    "runs": PIPELINE_DIR / "pipeline_runs.json",
    "significance": PIPELINE_DIR / "significance.json",
    "vsweep": PIPELINE_DIR / "v_tradeoff.json",
    "transfer": PIPELINE_DIR / "transfer.json",
    "adapter": PIPELINE_DIR / "adapter_report.json",
}
EXPERIMENTS_DIR = (Path(PROJECT_ROOT) / "selfx" / "output" / "experiments").resolve()
COMPARISON_DIR = (Path(PROJECT_ROOT) / "paper" / "comparison").resolve()
COMPARISON_FILES = {
    "index.html", "SELF_X_Algorithm_Comparison.pdf", "effects.csv", "runs.json", "effects.json"
}
COMPARISON_CHART_RE = re.compile(r"(?:0[1-9]|1[0-3])-[a-z0-9-]+\.png")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
RESOURCE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Paths for comparison, topologies, traffic and analytics
EFFECTS_JSON_PATH = (COMPARISON_DIR / "effects.json").resolve()
RUNS_JSON_PATH = (COMPARISON_DIR / "runs.json").resolve()
TOPOLOGIES_DIR = (Path(PROJECT_ROOT) / "selfx" / "output" / "topologies").resolve()
TRAFFIC_DIR = (Path(PROJECT_ROOT) / "selfx" / "output" / "traffic").resolve()
STATISTICAL_TESTS_DIR = (Path(PROJECT_ROOT) / "selfx" / "output" / "statistical_tests").resolve()
PAIRED_TTEST_PATH = (STATISTICAL_TESTS_DIR / "paired_t_test_report.json").resolve()
LATENCY_TARGETS_PATH = (STATISTICAL_TESTS_DIR / "latency_targets_report.json").resolve()
V_TRADEOFF_PATH = (PIPELINE_DIR / "v_tradeoff.json").resolve()
LORA_TRAINING_JSON = (PIPELINE_DIR / "adapter" / "training.json").resolve()
LORA_TRAINING_LOG = (PIPELINE_DIR / "adapter" / "training_log.jsonl").resolve()

# Files published by the local submission portal.
PAPER_DIR = Path(PROJECT_ROOT) / "paper"
FIGURES_DIR = PAPER_DIR / "figures"
SUBMISSION_DIR = Path(PROJECT_ROOT) / "output" / "submission"
CURRENT_SUBMISSION_DIR = SUBMISSION_DIR / "current"
SUBMISSION_LIMIT_BYTES = 100_000_000
SUBMISSION_DEADLINE = "2026-11-19T17:00:00+05:30"
SUBMISSION_FORM_URL = "https://forms.gle/5DbSbyJUqFwpXSYM9"
PAPER_TITLE = "SELF-X: Evaluating Language Model Assistance for Flow Control in Software-Defined Networks"
PAPER_FIGURE_RE = re.compile(r"fig(?:[1-9]|10)_[a-z_]+\.(?:pdf|png)")
AUDITED_FIGURES = {
    "paper_architecture.pdf", "paper_window_traces.pdf",
    "paper_delay_effects.pdf", "paper_delay_loss.pdf",
}
SUBMISSION_ARTIFACTS = {
    "SELF_X_Submission.zip": ("Course Submission ZIP", "Source, evidence, manuscript, review materials, and presentation.", "bundle"),
    "SELF_X_IEEE_Paper.pdf": ("Audited IEEE-format Manuscript", "Course manuscript built from paper/main.tex.", "paper"),
    "Overleaf_Source.zip": ("Overleaf LaTeX Source", "Upload to Overleaf and compile main.tex.", "bundle"),
    "SELF_X_Revision_Report.pdf": ("Revision Report", "Documents the changes made in response to the two Deep Review rounds.", "report"),
    "SELF_X_Revision_Response.md": ("Point-by-point Revision Response", "Editable review response and change log.", "response"),
    "SELF_X_Deep_Review_Round_1.md": ("Deep Review Export (Round 1)", "Original review feedback on the initial draft.", "review"),
    "SELF_X_Deep_Review_Round_2.md": ("Deep Review Export (Round 2)", "Original review feedback on Revision 1.", "review"),
    "SELF_X_Initial_Draft.pdf": ("Initial Draft", "Archived manuscript reviewed in Round 1.", "paper"),
    "SELF_X_Revision_1.pdf": ("Revision 1", "Manuscript after the first Deep Review round.", "paper"),
    "SELF_X_Revision_2.pdf": ("Revision 2", "Manuscript after the second Deep Review round.", "paper"),
    "SELF_X_Revision_2_Expanded.pdf": ("Expanded Revision 2", "Archived expanded revision.", "paper"),
    "SELF_X_Presentation.pdf": ("Course Presentation (PDF)", "Slides summarizing the audited comparison and its limitations.", "report"),
    "SELF_X_Presentation.pptx": ("Course Presentation (PowerPoint)", "Editable presentation slides.", "report"),
    "REPRODUCE.md": ("Reproduction Guide", "Commands for installation, the audited benchmark, and paper compilation.", "report"),
    "SHA256SUMS.txt": ("SHA-256 Checksums", "Hashes for the files in the current release.", "manifest"),
}


def public_file(directory, name):
    target = directory / name
    if target.is_file() and target.resolve() == directory.resolve() / name:
        return target
    return None


def submission_file(name):
    if name not in SUBMISSION_ARTIFACTS:
        return None
    target = public_file(CURRENT_SUBMISSION_DIR, name)
    if target:
        return target
    # A source checkout has these files before a course bundle is assembled.
    if name in {"SELF_X_IEEE_Paper.pdf", "REPRODUCE.md"}:
        return public_file(Path(PROJECT_ROOT), name)
    return None


COMPARISON_CONFIGS = [
    {
        "id": "S0",
        "label": "Static (L2 Switch)",
        "family": "baseline",
        "description": "Default Ryu L2 learning switch with static shortest path routing and zero dynamic flow adaptation."
    },
    {
        "id": "S1",
        "label": "Base LM (Zero-Shot)",
        "family": "agentic",
        "description": "Zero-shot SmolLM2-135M agent generating flow reroute actions without reflection or episodic memory."
    },
    {
        "id": "S2",
        "label": "Base LM + Critique",
        "family": "agentic",
        "description": "SmolLM2-135M agent enhanced with explicit self-critique and candidate action revision."
    },
    {
        "id": "S3",
        "label": "LoRA Policy",
        "family": "agentic",
        "description": "Parameter-efficient fine-tuned SmolLM2-135M (rank 8, alpha 16) trained on successful past trajectories."
    },
    {
        "id": "S4",
        "label": "Agentic at 5s",
        "family": "agentic",
        "description": "Full multi-agent reflection loop operating at 5.0-second control window intervals."
    },
    {
        "id": "S5",
        "label": "SELF-X Agentic",
        "family": "agentic",
        "description": "Flagship SELF-X autonomous agent combining LangGraph reflection, episodic memory bank, and Lyapunov DPP safety governor."
    },
    {
        "id": "threshold",
        "label": "Capacity Threshold",
        "family": "heuristic",
        "description": "Reactive threshold-based controller triggering reroutes when link load exceeds 80% watermark."
    },
    {
        "id": "least_loaded",
        "label": "Least Loaded Path",
        "family": "heuristic",
        "description": "Greedy routing heuristic that directs new and elephant flows to the path with lowest instantaneous queue occupancy."
    },
    {
        "id": "tabular_q",
        "label": "Tabular Q-Learning",
        "family": "rl",
        "description": "Classical reinforcement learning with discrete state-action lookup table over coarse network bins."
    },
    {
        "id": "dqn",
        "label": "Deep Q-Network (DQN)",
        "family": "rl",
        "description": "Deep Q-Network with experience replay buffer, target network synchronization, and epsilon-greedy exploration."
    },
    {
        "id": "marl",
        "label": "Two-Agent IQL (MARL)",
        "family": "rl",
        "description": "Multi-agent independent Q-learning with decentralized controllers coordinating across sub-domains."
    },
    {
        "id": "dpp",
        "label": "DPP Only",
        "family": "control_theoretic",
        "description": "Pure Lyapunov Drift-Plus-Penalty mathematical optimization without language model reasoning."
    },
    {
        "id": "no_lora",
        "label": "Agentic w/o LoRA",
        "family": "ablation",
        "description": "Ablation condition: Complete agentic pipeline operating without parameter-efficient policy adaptation."
    },
    {
        "id": "no_governor",
        "label": "Agentic w/o Governor",
        "family": "ablation",
        "description": "Ablation condition: Complete agentic pipeline without the Lyapunov DPP safety guardrail and veto envelope."
    }
]

_CACHED_RUNS_DATA = None


class SDNRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def translate_path(self, path):
        clean_path = urlsplit(path).path

        for prefix, directory in (
            ("/comparison/", COMPARISON_DIR),
            ("/paper/comparison/", COMPARISON_DIR),
            ("/paper/figures/", FIGURES_DIR),
            ("/paper/", PAPER_DIR),
            ("/downloads/", None),
            ("/output/submission/current/", CURRENT_SUBMISSION_DIR),
            ("/output/submission/", SUBMISSION_DIR),
            ("/output/pdf/", Path(PROJECT_ROOT) / "output" / "pdf"),
        ):
            if not clean_path.startswith(prefix):
                continue
            name = clean_path.removeprefix(prefix)
            target = None
            if directory == COMPARISON_DIR:
                if name in COMPARISON_FILES | AUDITED_FIGURES or COMPARISON_CHART_RE.fullmatch(name):
                    target = public_file(directory, name)
            elif directory == FIGURES_DIR:
                if PAPER_FIGURE_RE.fullmatch(name):
                    target = public_file(directory, name)
            elif directory == PAPER_DIR:
                if name in {"main.tex", "refs.bib", "README_OVERLEAF.md", "COMPARISON.md",
                            "AUDITED_COMPARISON_SPECIFICATION.md"}:
                    target = public_file(directory, name)
            elif directory is None:
                target = submission_file(name)
            elif name in SUBMISSION_ARTIFACTS:
                target = public_file(directory, name)

            # Reserved URLs only serve the files selected above.
            return str(target if target else Path(WEB_DIR) / ".unavailable" / "file")

        return super().translate_path(path)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Referrer-Policy', 'same-origin')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        if path == '/login':
            self.redirect_public_dashboard()
            return
        if path.startswith('/api/auth/'):
            self.send_json(404, {"error": "authentication is disabled for the public website"})
            return

        # API: Real-time System Status & Ryu Controller Health
        if path == '/api/status':
            self.handle_status()
            return

        # API: Research Paper & Final Submission Portal Manifest
        if path == '/api/submission/info':
            self.handle_submission_info()
            return

        # API: Live Episodic Memory Bank
        if path == '/api/memory':
            self.handle_memory()
            return

        # API: Real Ablation Benchmark Logs (A0 vs A1 vs A2 CSVs)
        if path == '/api/ablation':
            self.handle_ablation()
            return

        # API: Table 2 6-stage ablation (A0..A5)
        if path == '/api/ablation/table2':
            self.handle_ablation_table2()
            return

        # API: Table 5 baseline comparison matrix
        if path == '/api/benchmarks/table5':
            self.handle_benchmarks_table5()
            return

        # API: DPP formal bound acceptance
        if path == '/api/dpp/acceptance':
            self.handle_dpp_acceptance()
            return

        # API: archived incremental pipeline study
        if path.startswith('/api/pipeline/'):
            self.handle_pipeline(path.removeprefix('/api/pipeline/'))
            return

        # API: Zero-shot transfer evaluation
        if path == '/api/transfer':
            self.handle_transfer()
            return

        # API: Algorithm Comparison 14-controller dataset & effects
        if path == '/api/comparison/configs':
            self.handle_comparison_configs()
            return
        if path == '/api/comparison/effects':
            self.handle_comparison_effects()
            return
        if path == '/api/comparison/runs':
            self.handle_comparison_runs()
            return

        # API: Multi-Topology Manifests
        if path == '/api/topologies':
            self.handle_topologies_list()
            return
        if path.startswith('/api/topologies/'):
            self.handle_topology_manifest(path.removeprefix('/api/topologies/'))
            return

        # API: Traffic Workload Schedules
        if path == '/api/traffic/schedules':
            self.handle_traffic_schedules_list()
            return
        if path.startswith('/api/traffic/schedules/'):
            self.handle_traffic_schedule(path.removeprefix('/api/traffic/schedules/'))
            return

        # API: Advanced Analytics & Theory Lab
        if path == '/api/analytics/dpp':
            self.handle_analytics_dpp()
            return
        if path == '/api/analytics/statistics':
            self.handle_analytics_statistics()
            return
        if path == '/api/analytics/lora':
            self.handle_analytics_lora()
            return
        if path == '/api/analytics/transfer':
            self.handle_transfer()
            return

        if path == '/api/results':
            self.handle_results_index()
            return
        if path == '/api/results/compare':
            self.handle_results_compare()
            return
        if path.startswith('/api/results/'):
            self.handle_result_resource(path)
            return

        # API: Pre-computed v4 offline benchmark summary
        if path == '/api/benchmarks/summary':
            self.handle_benchmarks_summary()
            return

        # API: Real LLM API diagnostic pilot summaries
        if path == '/api/benchmarks/llm-diagnostics':
            self.handle_benchmarks_llm_diagnostics()
            return

        # Raw Ryu telemetry is private and is no longer proxied publicly.
        if path.startswith('/api/ryu/'):
            self.send_json(404, {"error": "raw controller proxy is not public"})
            return

        # Default static web files
        return super().do_GET()

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0) or 0)
            if length > 0:
                self.rfile.read(min(length, 1048576))
        except Exception:
            pass

        path = urlsplit(self.path).path
        if path.startswith('/api/auth/'):
            self.send_json(404, {"error": "authentication is disabled for the public website"})
            return

        # Raw Ryu writes remain disabled and are not proxied.
        if path.startswith('/api/ryu/'):
            self.handle_disabled_control("raw controller proxy is not public")
            return

        # API: Direct Flow Reroute Helper
        if path == '/api/action/reroute':
            self.handle_action_reroute()
            return

        # API: Direct Rate Limit Helper
        if path == '/api/action/rate_limit':
            self.handle_action_rate_limit()
            return

        self.send_response(404)
        self.end_headers()

    def send_json(self, status, payload, headers=None):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        if headers:
            for key, value in headers.items():
                values = value if isinstance(value, (list, tuple)) else [value]
                for item in values:
                    self.send_header(key, item)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode('utf-8'))

    def redirect_public_dashboard(self):
        self.send_response(302)
        self.send_header('Location', '/')
        self.end_headers()

    def handle_status(self):
        ryu_online = False
        switches = []
        try:
            req = urllib.request.Request(f"{RYU_BASE_URL}/stats/switches", headers={'User-Agent': 'SDN-Dashboard'})
            with urllib.request.urlopen(req, timeout=1.2) as resp:
                if resp.status == 200:
                    payload = json.load(resp)
                    if isinstance(payload, list):
                        ryu_online = True
                        switches = payload
        except (OSError, ValueError):
            pass

        data = {
            "status": "online",
            "ryu_controller": "connected" if ryu_online else "offline",
            "connected_switches": switches,
            "project": "SELF-X SDN Agent",
            "course": "EC466 Software Defined Networks",
            "team": "SDN_07",
            "testbed_mode": "live" if ryu_online else "offline",
            "testbed_message": "Live Ryu controller connected." if ryu_online else "Live testbed disconnected. No live packet measurements currently available.",
            "benchmarks_available": BENCHMARKS_V4_SUMMARY.is_file(),
            "table2_available": TABLE2_SUMMARY_PATH.is_file(),
            "table5_available": TABLE5_SUMMARY_PATH.is_file(),
            "dpp_acceptance_available": DPP_ACCEPTANCE_PATH.is_file(),
            "transfer_available": TRANSFER_PATH.is_file(),
            "pipeline_available": PIPELINE_FILES["summary"].is_file(),
            "pipeline_resources": sorted(k for k, v in PIPELINE_FILES.items() if v.is_file()),
            "comparison_available": EFFECTS_JSON_PATH.is_file() and RUNS_JSON_PATH.is_file(),
            "topologies_available": TOPOLOGIES_DIR.is_dir(),
            "traffic_schedules_available": TRAFFIC_DIR.is_dir(),
            "analytics_available": DPP_ACCEPTANCE_PATH.is_file() and PAIRED_TTEST_PATH.is_file(),
            "submission_available": submission_file("SELF_X_Submission.zip") is not None,
            "submission_deadline": SUBMISSION_DEADLINE,
            "submission_form_url": SUBMISSION_FORM_URL
        }
        self.send_json(200, data)

    def handle_submission_info(self):
        sha_map = {}
        checksum_file = public_file(CURRENT_SUBMISSION_DIR, "SHA256SUMS.txt")
        if checksum_file:
            try:
                for line in checksum_file.read_text(encoding="utf-8").splitlines():
                    digest, separator, filename = line.partition("  ")
                    if separator and re.fullmatch(r"[0-9a-f]{64}", digest):
                        sha_map[filename] = digest
            except (OSError, UnicodeError):
                pass

        artifacts = []
        for filename, (title, description, category) in SUBMISSION_ARTIFACTS.items():
            target = submission_file(filename)
            if target is None:
                continue
            size = target.stat().st_size
            artifacts.append({
                "name": filename,
                "title": title,
                "description": description,
                "category": category,
                "size_bytes": size,
                "size_str": f"{size / 1_000_000:.2f} MB" if size >= 1_000_000 else f"{size / 1_000:.1f} kB",
                "sha256": sha_map.get(filename) if target.parent == CURRENT_SUBMISSION_DIR else None,
                "download_url": f"/downloads/{filename}",
            })

        bundle = next((item for item in artifacts if item["name"] == "SELF_X_Submission.zip"), None)
        size = bundle["size_bytes"] if bundle else None
        info = {
            "success": True,
            "project_title": PAPER_TITLE,
            "short_title": "SELF-X",
            "team_id": "SDN_07",
            "course": "EC466 Software Defined Networks",
            "institution": "IIIT Dharwad",
            "submission_deadline_iso": SUBMISSION_DEADLINE,
            "submission_deadline_human": "19 November 2026, 5:00 PM IST",
            "google_form_url": SUBMISSION_FORM_URL,
            "overleaf_template_url": "https://www.overleaf.com/latex/templates/ieee-conference-template/grfzhhncsfqn",
            "deep_review_portal_url": "https://research.google/deepreview/",
            "max_bundle_size": "100 MB",
            "submission_zip_size_mb": round(size / 1_000_000, 2) if size is not None else None,
            "submission_zip_status": (
                "NOT_BUILT" if size is None else
                "UNDER_100MB" if size < SUBMISSION_LIMIT_BYTES else "OVER_LIMIT"
            ),
            "artifacts": artifacts,
            "deep_review_rounds": [
                {
                    "round": 1,
                    "document_id": "cfc7fbd2-e25a-4205-9cea-2a09f614aa9b",
                    "input_document": "SELF_X_Initial_Draft.pdf",
                    "output_document": "SELF_X_Revision_1.pdf",
                    "status": "RESPONSE DOCUMENTED",
                    "points_addressed": 15,
                    "criticisms_and_solutions": [
                        {"point": "1. Standalone DPP and stage attribution", "solution": "Added the 100 ms DPP-only arm with V=8, initial weights, and shared guard. Compared matched 5s stack and removed LM layers separately."},
                        {"point": "2. Loop interfaces and startup timing", "solution": "S3 applies adapter proposal after 4 slots; S4/S5 use it as bounded preference. Governor updates become available eight slots after an epoch starts."},
                        {"point": "3. Drift units, clipping, and backlog theorem", "solution": "Replaced earlier theorem with actual rate-form score (units of Mbit^2/s). Multiplication by slot duration gives linear term in unclipped quadratic drift. Finite buffer caps occupancy."},
                        {"point": "4. Buffer saturation example", "solution": "Quantified excess arrival: an empty 2 Mbit queue fills in exactly 200 ms at 20 Mbps arrivals and 10 Mbps service."},
                        {"point": "5. Loss floor quantification", "solution": "Removed unsupported 7.97% bufferless claim. Documented that buffer absorption separates instantaneous bursts from true packet drops."},
                        {"point": "6. Action-to-rate mapping & metering", "solution": "Formally defined admitted rates, meter drops, clipping, overflow, served volume, and all five score terms. Bounded V in [0.5, 32.0]."},
                        {"point": "7. Delay estimand & virtual waiting time", "solution": "Replaced Little's Law wording with virtual waiting time proxy at service rate. Defined clipped slot integral and served-volume weighting."},
                        {"point": "8. Telemetry resolution & adapter provenance", "solution": "DPP uses exact simulator state; action prompt rounds rates to 0.5 Mbps; governor prompt rounds to integers. Documented 24-state grid and offline checkpoint."},
                        {"point": "9. Window history & memory replay", "solution": "Clarified that S2 appends last effective action and reward after each 5s window. Documented that no arm retrains adapter during test."},
                        {"point": "10. Control latency & real inference", "solution": "Replaced provider experiment with real local inference and 400 ms per sequential stage. Specialist agents share one stage."},
                        {"point": "11. Sample size & statistical testing", "solution": "Full benchmark: 14 configs × 12 paired traces × 1,800 slots = 302,400 test slots. 13 Holm-adjusted tests + 20,000 bootstrap draws."},
                        {"point": "12. Online tabular baseline exploration", "solution": "Explicitly documented Tabular Q exploration schedule (epsilon-decay) and added offline-trained frozen DQN and IQL benchmarks."},
                        {"point": "13. Position against prior art & LoRA results", "solution": "Positioned against NetLLM and agentic SDN. Reported negative LoRA direct arm and paired result of removing prior from S5."},
                        {"point": "14. Evaluation profiles & generalization", "solution": "Compared all controllers on identical three synthetic test profiles. Avoided unsupported zero-shot transfer claims."},
                        {"point": "15. Figures, rounding, and notation", "solution": "Replaced older plots with clean vector figures and tables from audited data, removing overlapping labels and inconsistent rounding."}
                    ]
                },
                {
                    "round": 2,
                    "document_id": "edb928d1-957f-4f28-9c8e-a6bed8513777",
                    "input_document": "SELF_X_Revision_1.pdf",
                    "output_document": "SELF_X_Revision_2.pdf",
                    "status": "RESPONSE DOCUMENTED",
                    "points_addressed": 11,
                    "criticisms_and_solutions": [
                        {"point": "1. Direction & component interaction", "solution": "Documented that S5 was 0.12 ms slower than DPP alone (p=0.0745 Holm-adjusted). Explained why reducing V increases relative prior penalty."},
                        {"point": "2. Capability boundaries & external validity", "solution": "Explicitly limited claims to SmolLM2-135M-Instruct, prompt design, and synthetic fluid topology. No unsupported hardware claims."},
                        {"point": "3. Current-slot information fairness", "solution": "Distinguished exact current demand access from future demand knowledge. Contrasted reinforcement learning reward with DPP drift-plus-penalty."},
                        {"point": "4. Preference feasibility checks", "solution": "Preference is rechecked on each DPP decision; infeasible preferences are ignored without defaulting to primary."},
                        {"point": "5. Prompt input consistency", "solution": "Direct prompts use 0.5 Mbps rate quantization; governor prompts use integer rounding. Added explicit clipping and renormalization equations."},
                        {"point": "6. Baseline interface & meter rules", "solution": "Specified threshold and tabular meter equations, floor interactions, least-loaded 2-action menu, and IQL binary voting precedence."},
                        {"point": "7. Timing & guard holds", "solution": "Documented that held proposals retain numeric meter caps while per-slot vetoes do not latch. S4 consumes advice at window boundaries."},
                        {"point": "8. Synthetic traffic & metric weighting", "solution": "Added flash-crowd parameters, Poisson event clock, volume-weighted delay, and terminal backlog conservation checks."},
                        {"point": "9. Shared guard & matching neural actions", "solution": "Instrumented replay retrained neural baselines, finding 891 vetoes in 21,600 proposals, where both applied actions were primary."},
                        {"point": "10. Paired effects & precision", "solution": "Reported pointwise confidence intervals, raw p-values, and Holm-adjusted p-values for all 13 comparators. 3-decimal goodput reporting."},
                        {"point": "11. Fixed governor diagnostic control", "solution": "Added fixed governor diagnostic showing that an invariant governor output reproduces all 432 S5 windows and 12 action hashes."}
                    ]
                },
                {
                    "round": 3,
                    "document_id": "Expanded Revision 2",
                    "input_document": "SELF_X_Revision_2.pdf",
                    "output_document": "SELF_X_Revision_2_Expanded.pdf",
                    "status": "LOCAL EDITORIAL REVISION",
                    "points_addressed": 6,
                    "criticisms_and_solutions": [
                        {"point": "1. Full system architecture diagram", "solution": "Restored Fig 1 showing Fast 100ms Lyapunov DPP loop, 5 s action advice, 30 s weight updates, and the shared action guard."},
                        {"point": "2. Algorithm 1: Advice Scheduling", "solution": "Inlined formal pseudocode for asynchronous advice ingestion, preference scoring, and weight updates."},
                        {"point": "3. Algorithm 2: DPP Candidate Scoring", "solution": "Inlined formal pseudocode for queue drift computation, penalty evaluation, and tie-breaking."},
                        {"point": "4. Aligned 6-panel performance dynamics", "solution": "Included Fig 2 showing aligned traffic demand, latency, backlog, loss percentage, throughput, and flow-mod rate."},
                        {"point": "5. Workload decomposition", "solution": "Added breakdown across steady-bursty, flash-crowd, and volatile traffic profiles."},
                        {"point": "6. Overleaf project bundle packaging", "solution": "Built clean Overleaf_Source.zip verified to compile cleanly with standard IEEEtran class."}
                    ]
                }
            ],
            "paper_sections": [
                {"section": "I–II. Introduction and Related Work",
                 "summary": "Tests the contribution of language model advice to a constrained analytic controller."},
                {"section": "III–IV. System Model and Controller",
                 "summary": "Defines the finite-buffer simulator, action guard, 100 ms control slots and advice schedules."},
                {"section": "V–VI. Experimental Setup and Results",
                 "summary": "Compares 14 configurations on 12 paired synthetic traces. SELF-X averages 60.54 ms versus 80.88 ms for static forwarding and 60.42 ms for DPP only."},
            ],
        }
        self.send_json(200, info)

    def handle_pipeline(self, name):
        """Serve one result file of the incremental pipeline study, read-only.

        `name` is matched against a fixed allow-list rather than joined onto a
        path, so no request can walk out of the results directory.
        """
        target = PIPELINE_FILES.get(name)
        if target is None:
            self.send_json(404, {
                "error": "unknown pipeline resource",
                "available": sorted(PIPELINE_FILES),
            })
            return
        if not target.is_file():
            self.send_json(404, {
                "error": f"pipeline {name} not generated yet",
                "available": False,
                "hint": "run scripts/run_all.ps1 (or run_all.sh) to produce it",
            })
            return
        try:
            with open(target, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError:
            self.send_json(502, {"error": f"pipeline {name} is malformed JSON"})
            return
        except Exception as exc:
            self.send_json(500, {"error": f"failed to read pipeline {name}: {exc}"})
            return
        self.send_json(200, data, headers={"Cache-Control": "public, max-age=60"})

    def handle_ablation_table2(self):
        if not TABLE2_SUMMARY_PATH.is_file():
            self.send_json(404, {"error": "Table 2 ablation summary not found", "available": False})
            return
        try:
            with open(TABLE2_SUMMARY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.send_json(200, data, headers={"Cache-Control": "public, max-age=60"})
        except Exception as e:
            self.send_json(500, {"error": f"failed to load Table 2 summary: {str(e)}"})

    def handle_benchmarks_table5(self):
        if not TABLE5_SUMMARY_PATH.is_file():
            self.send_json(404, {"error": "Table 5 benchmark summary not found", "available": False})
            return
        try:
            with open(TABLE5_SUMMARY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.send_json(200, data, headers={"Cache-Control": "public, max-age=60"})
        except Exception as e:
            self.send_json(500, {"error": f"failed to load Table 5 summary: {str(e)}"})

    def handle_dpp_acceptance(self):
        if not DPP_ACCEPTANCE_PATH.is_file():
            self.send_json(404, {"error": "DPP acceptance summary not found", "available": False})
            return
        try:
            with open(DPP_ACCEPTANCE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.send_json(200, data, headers={"Cache-Control": "public, max-age=60"})
        except Exception as e:
            self.send_json(500, {"error": f"failed to load DPP acceptance summary: {str(e)}"})

    def handle_transfer(self):
        if not TRANSFER_PATH.is_file():
            self.send_json(404, {"error": "Zero-shot transfer report not found", "available": False})
            return
        try:
            with open(TRANSFER_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.send_json(200, data, headers={"Cache-Control": "public, max-age=60"})
        except Exception as e:
            self.send_json(500, {"error": f"failed to load zero-shot transfer report: {str(e)}"})

    def handle_benchmarks_summary(self):
        if not BENCHMARKS_V4_SUMMARY.is_file():
            self.send_json(404, {"error": "benchmark summary not found", "available": False})
            return
        try:
            with open(BENCHMARKS_V4_SUMMARY, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "controllers" not in data or "groups" not in data:
                self.send_json(502, {"error": "benchmark summary payload is incomplete or invalid"})
                return
            self.send_json(200, data, headers={"Cache-Control": "public, max-age=60"})
        except (json.JSONDecodeError, ValueError):
            self.send_json(502, {"error": "benchmark summary is malformed JSON"})
        except Exception as e:
            self.send_json(500, {"error": f"failed to read benchmark summary: {str(e)}"})

    def handle_benchmarks_llm_diagnostics(self):
        runs = {}
        for provider in ("gemini_v4", "openrouter_v4"):
            pfile = EXPERIMENTS_DIR / provider / "summary.json"
            if pfile.is_file():
                try:
                    with open(pfile, "r", encoding="utf-8") as f:
                        runs[provider] = json.load(f)
                except Exception:
                    pass
        if not runs:
            self.send_json(404, {"error": "no LLM diagnostic summaries found", "runs": {}})
            return
        self.send_json(200, {
            "status": "ok",
            "provenance": "LLM API Diagnostic Check",
            "disclaimer": "Analytical fluid simulation with authenticated external LLM calls. No in-switch packet forwarding.",
            "runs": runs
        })

    def handle_comparison_configs(self):
        self.send_json(200, {
            "success": True,
            "count": len(COMPARISON_CONFIGS),
            "configs": COMPARISON_CONFIGS
        }, headers={"Cache-Control": "public, max-age=300"})

    def handle_comparison_effects(self):
        if not EFFECTS_JSON_PATH.is_file():
            self.send_json(404, {"error": "audited comparison effects.json not found", "available": False})
            return
        try:
            with open(EFFECTS_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.send_json(200, data, headers={"Cache-Control": "public, max-age=120"})
        except Exception as e:
            self.send_json(500, {"error": f"failed to load comparison effects: {str(e)}"})

    def handle_comparison_runs(self):
        global _CACHED_RUNS_DATA
        if not RUNS_JSON_PATH.is_file():
            self.send_json(404, {"error": "audited comparison runs.json not found", "available": False})
            return
        try:
            if _CACHED_RUNS_DATA is None:
                with open(RUNS_JSON_PATH, "r", encoding="utf-8") as f:
                    _CACHED_RUNS_DATA = json.load(f)
            data = _CACHED_RUNS_DATA
        except Exception as e:
            self.send_json(500, {"error": f"failed to load comparison runs: {str(e)}"})
            return

        query = parse_qs(urlsplit(self.path).query)
        requested_configs = set()
        if "config" in query:
            for item in query["config"]:
                requested_configs.update(c.strip() for c in item.split(",") if c.strip())
        if "configs" in query:
            for item in query["configs"]:
                requested_configs.update(c.strip() for c in item.split(",") if c.strip())

        all_requested = query.get("all", ["false"])[0].lower() in ("true", "1", "yes")
        summary_only = query.get("summary_only", ["false"])[0].lower() in ("true", "1", "yes")

        all_runs = data.get("runs", [])
        if summary_only or (not requested_configs and not all_requested):
            summary_runs = []
            for r in all_runs:
                cfg = r.get("configuration", "")
                windows = r.get("windows", [])
                avg_latency = sum(w.get("latency_ms", 0) for w in windows) / max(len(windows), 1)
                avg_goodput = sum(w.get("throughput_mbps", 0) for w in windows) / max(len(windows), 1)
                avg_loss = sum(w.get("loss_pct", 0) for w in windows) / max(len(windows), 1)
                avg_reward = sum(w.get("reward", 0) for w in windows) / max(len(windows), 1)
                installs = sum(w.get("installs", 0) for w in windows)
                vetoes = sum(w.get("vetoes", 0) for w in windows)
                summary_runs.append({
                    "configuration": cfg,
                    "seed": r.get("seed"),
                    "profile": r.get("profile"),
                    "window_count": len(windows),
                    "mean_latency_ms": round(avg_latency, 3),
                    "mean_goodput_mbps": round(avg_goodput, 3),
                    "mean_loss_pct": round(avg_loss, 3),
                    "mean_reward": round(avg_reward, 4),
                    "total_installs": installs,
                    "total_vetoes": vetoes
                })
            self.send_json(200, {
                "schema": data.get("schema", "selfx.audited-comparison.v1"),
                "total_runs": len(all_runs),
                "configs": data.get("configs", {}),
                "summary": summary_runs
            }, headers={"Cache-Control": "public, max-age=120"})
            return

        filtered = [r for r in all_runs if r.get("configuration") in requested_configs] if requested_configs else all_runs
        self.send_json(200, {
            "schema": data.get("schema", "selfx.audited-comparison.v1"),
            "configs": data.get("configs", {}),
            "count": len(filtered),
            "runs": filtered
        }, headers={"Cache-Control": "public, max-age=120"})

    def handle_topologies_list(self):
        if not TOPOLOGIES_DIR.is_dir():
            self.send_json(404, {"error": "topologies directory not found", "available": False})
            return
        topos = []
        try:
            for manifest_file in sorted(TOPOLOGIES_DIR.glob("*manifest.json")):
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                topos.append({
                    "id": manifest.get("id", manifest_file.stem.replace("_manifest", "")),
                    "name": manifest.get("name", manifest_file.stem),
                    "category": manifest.get("category", "topology"),
                    "switch_count": manifest.get("switch_count", len(manifest.get("switches", []))),
                    "host_count": manifest.get("host_count", len(manifest.get("hosts", []))),
                    "link_count": len(manifest.get("links", []))
                })
            self.send_json(200, {"success": True, "topologies": topos}, headers={"Cache-Control": "public, max-age=120"})
        except Exception as e:
            self.send_json(500, {"error": f"failed to load topologies: {str(e)}"})

    def handle_topology_manifest(self, topo_id):
        topo_id = topo_id.strip()
        if not RESOURCE_NAME_RE.fullmatch(topo_id):
            self.send_json(400, {"error": "invalid topology id format"})
            return
        candidate1 = (TOPOLOGIES_DIR / f"{topo_id}_manifest.json").resolve()
        candidate2 = (TOPOLOGIES_DIR / f"{topo_id}.json").resolve()
        target = candidate1 if candidate1.is_file() else (candidate2 if candidate2.is_file() else None)
        if target is None or target.parent != TOPOLOGIES_DIR:
            self.send_json(404, {"error": f"topology '{topo_id}' not found"})
            return
        try:
            with open(target, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            self.send_json(200, manifest, headers={"Cache-Control": "public, max-age=120"})
        except Exception as e:
            self.send_json(500, {"error": f"failed to load topology '{topo_id}': {str(e)}"})

    def handle_traffic_schedules_list(self):
        if not TRAFFIC_DIR.is_dir():
            self.send_json(404, {"error": "traffic schedules directory not found", "available": False})
            return
        schedules = []
        try:
            for sched_file in sorted(TRAFFIC_DIR.glob("schedule_*.json")):
                with open(sched_file, "r", encoding="utf-8") as f:
                    sched = json.load(f)
                schedules.append({
                    "filename": sched_file.name,
                    "profile": sched.get("profile", sched_file.stem),
                    "seed": sched.get("seed", 42),
                    "duration_sec": sched.get("duration_sec", 600),
                    "num_hosts": sched.get("num_hosts", 8),
                    "total_events": sched.get("total_events", len(sched.get("events", [])))
                })
            self.send_json(200, {"success": True, "schedules": schedules}, headers={"Cache-Control": "public, max-age=120"})
        except Exception as e:
            self.send_json(500, {"error": f"failed to list traffic schedules: {str(e)}"})

    def handle_traffic_schedule(self, profile):
        profile = profile.strip()
        if not RESOURCE_NAME_RE.fullmatch(profile):
            self.send_json(400, {"error": "invalid traffic profile format"})
            return
        target = None
        for cand in TRAFFIC_DIR.glob(f"*{profile}*.json"):
            target = cand.resolve()
            break
        if target is None or target.parent != TRAFFIC_DIR or not target.is_file():
            self.send_json(404, {"error": f"traffic schedule for profile '{profile}' not found"})
            return
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.send_json(200, data, headers={"Cache-Control": "public, max-age=120"})
        except Exception as e:
            self.send_json(500, {"error": f"failed to load traffic schedule '{profile}': {str(e)}"})

    def handle_analytics_dpp(self):
        acceptance = None
        v_tradeoff = None
        if DPP_ACCEPTANCE_PATH.is_file():
            try:
                with open(DPP_ACCEPTANCE_PATH, "r", encoding="utf-8") as f:
                    acceptance = json.load(f)
            except Exception:
                pass
        if V_TRADEOFF_PATH.is_file():
            try:
                with open(V_TRADEOFF_PATH, "r", encoding="utf-8") as f:
                    v_tradeoff = json.load(f)
            except Exception:
                pass
        if not acceptance and not v_tradeoff:
            self.send_json(404, {"error": "DPP analytical reports not found", "available": False})
            return
        self.send_json(200, {
            "success": True,
            "acceptance": acceptance,
            "v_tradeoff": v_tradeoff
        }, headers={"Cache-Control": "public, max-age=120"})

    def handle_analytics_statistics(self):
        paired_ttest = None
        latency_targets = None
        if PAIRED_TTEST_PATH.is_file():
            try:
                with open(PAIRED_TTEST_PATH, "r", encoding="utf-8") as f:
                    paired_ttest = json.load(f)
            except Exception:
                pass
        if LATENCY_TARGETS_PATH.is_file():
            try:
                with open(LATENCY_TARGETS_PATH, "r", encoding="utf-8") as f:
                    latency_targets = json.load(f)
            except Exception:
                pass
        if not paired_ttest and not latency_targets:
            self.send_json(404, {"error": "Statistical reports not found", "available": False})
            return
        self.send_json(200, {
            "success": True,
            "paired_ttest": paired_ttest,
            "latency_targets": latency_targets
        }, headers={"Cache-Control": "public, max-age=120"})

    def handle_analytics_lora(self):
        if not LORA_TRAINING_JSON.is_file():
            self.send_json(404, {"error": "LoRA training summary not found", "available": False})
            return
        try:
            with open(LORA_TRAINING_JSON, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            steps = []
            if LORA_TRAINING_LOG.is_file():
                with open(LORA_TRAINING_LOG, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            steps.append(json.loads(line))
            self.send_json(200, {
                "success": True,
                "config": config_data,
                "steps": steps,
                "step_count": len(steps)
            }, headers={"Cache-Control": "public, max-age=120"})
        except Exception as e:
            self.send_json(500, {"error": f"failed to load LoRA training data: {str(e)}"})

    def handle_memory(self):
        candidates = [
            os.path.join(PROJECT_ROOT, "agent_memory.json"),
            os.path.join(PROJECT_ROOT, "selfx", "agent_memory.json"),
            os.path.join(PROJECT_ROOT, "selfx", "eval", "logs", "A2_memory.json"),
            os.path.join(PROJECT_ROOT, "eval", "logs", "A2_memory.json"),
            os.path.join(PROJECT_ROOT, "sdn-self-improving-agent", "agent_memory.json"),
            os.path.join(PROJECT_ROOT, "sdn-self-improving-agent", "data", "memory.json")
        ]

        found_data = None
        source_path = None
        for path in candidates:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        found_data = json.load(f)
                        source_path = path
                    break
                except Exception:
                    continue

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        if found_data:
            self.wfile.write(json.dumps({
                "success": True,
                "is_live_project": True,
                        "source": "local_memory_file",
                "count": len(found_data),
                "entries": found_data
            }).encode('utf-8'))
        else:
            self.wfile.write(json.dumps({
                "success": False,
                "is_live_project": False,
                "message": "No live agent_memory.json found yet; running with simulated baseline records until python agent executes."
            }).encode('utf-8'))

    def handle_ablation(self):
        log_dirs = [
            os.path.join(PROJECT_ROOT, "selfx", "eval", "logs"),
            os.path.join(PROJECT_ROOT, "eval", "logs"),
            os.path.join(PROJECT_ROOT, "sdn-self-improving-agent", "eval", "logs")
        ]

        results = {}
        for ldir in log_dirs:
            if os.path.exists(ldir):
                for cond in ["A0", "A1", "A2"]:
                    csv_path = os.path.join(ldir, f"{cond}.csv")
                    if os.path.exists(csv_path):
                        rows = []
                        try:
                            with open(csv_path, "r", encoding="utf-8") as f:
                                reader = csv.DictReader(f)
                                for r in reader:
                                    rows.append(r)
                            results[cond] = rows
                        except Exception:
                            pass
                if results:
                    break

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "success": bool(results),
            "conditions": results
        }).encode('utf-8'))

    def _run_path(self, run_id):
        if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
            self.send_json(404, {"error": "result run not found"})
            return None
        root = Path(RESULTS_ROOT).resolve()
        candidate = (root / run_id).resolve()
        if candidate.parent != root or not candidate.is_dir():
            self.send_json(404, {"error": "result run not found"})
            return None
        return candidate

    @staticmethod
    def _public_metadata(metadata):
        public = dict(metadata)
        public["artifacts"] = sorted(public.get("artifacts", {}).keys())
        return public

    def _load_run(self, run_id):
        run_path = self._run_path(run_id)
        if run_path is None:
            return None
        try:
            result = read_run(run_path)
        except (OSError, ValueError, json.JSONDecodeError, ResultValidationError):
            self.send_json(422, {"error": "result run is malformed or invalid"})
            return None
        if result["run"].get("run_id") != run_id:
            self.send_json(422, {"error": "result run identity is invalid"})
            return None
        return result

    def handle_results_index(self):
        results = []
        invalid_count = 0
        root = Path(RESULTS_ROOT).resolve()
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if not child.is_dir() or not RUN_ID_RE.fullmatch(child.name):
                    continue
                try:
                    result = read_run(child)
                except (OSError, ValueError, json.JSONDecodeError, ResultValidationError):
                    invalid_count += 1
                    continue
                metadata = result["run"]
                results.append({
                    "run_id": metadata["run_id"],
                    "created_at_utc": metadata["created_at_utc"],
                    "status": metadata["status"],
                    "provenance": metadata["provenance"],
                    "experiment": metadata["experiment"],
                    "topology": metadata["topology"],
                    "workload": metadata["workload"],
                    "seed": metadata["seed"],
                    "duration_seconds": metadata["duration_seconds"],
                    "metric_count": len(result["metrics"]),
                    "has_summary": "summary" in result,
                    "has_trace": "trace.jsonl" in metadata.get("artifacts", {}),
                })
        self.send_json(200, {
            "schema_version": "selfx.result.v1",
            "count": len(results),
            "invalid_count": invalid_count,
            "results": results,
        })

    def handle_results_compare(self):
        values = parse_qs(urlsplit(self.path).query).get("run_ids", [])
        run_ids = [value for item in values for value in item.split(",") if value]
        if not run_ids or len(run_ids) > 6:
            self.send_json(400, {"error": "run_ids must contain between one and six run IDs"})
            return
        compared = []
        for run_id in run_ids:
            result = self._load_run(run_id)
            if result is None:
                return
            if result["run"]["status"] != "completed" or "summary" not in result:
                self.send_json(409, {"error": "all comparison runs must be completed with summaries"})
                return
            compared.append({
                "run": self._public_metadata(result["run"]),
                "summary": result["summary"],
            })
        self.send_json(200, {"run_ids": run_ids, "results": compared})

    def handle_result_resource(self, path):
        parts = path[len("/api/results/"):].split("/")
        if len(parts) == 1 and parts[0]:
            return self.handle_result_summary(parts[0])
        if len(parts) == 2 and parts[0] and parts[1] in {"summary", "metrics", "trace"}:
            handler = getattr(self, f"handle_result_{parts[1]}")
            return handler(parts[0])
        self.send_json(404, {"error": "result route not found"})

    def handle_result_summary(self, run_id):
        result = self._load_run(run_id)
        if result is None:
            return
        metadata = result["run"]
        if metadata["status"] == "failed":
            self.send_json(409, {"error": "result run failed", "run": self._public_metadata(metadata)})
            return
        if "summary" not in result:
            self.send_json(409, {"error": "result run is incomplete", "run": self._public_metadata(metadata)})
            return
        self.send_json(200, {"run": self._public_metadata(metadata), "summary": result["summary"]})

    def handle_result_metrics(self, run_id):
        result = self._load_run(run_id)
        if result is None:
            return
        self.send_json(200, {"run": self._public_metadata(result["run"]), "metrics": result["metrics"]})

    def handle_result_trace(self, run_id):
        result = self._load_run(run_id)
        if result is None:
            return
        trace = []
        trace_path = result["run"].get("artifacts", {}).get("trace")
        if trace_path:
            path = (Path(RESULTS_ROOT) / run_id / trace_path).resolve()
            if path.parent != (Path(RESULTS_ROOT) / run_id).resolve() or not path.is_file():
                self.send_json(422, {"error": "result trace is unavailable"})
                return
            try:
                with path.open(encoding="utf-8") as handle:
                    for line in handle:
                        if line.strip():
                            trace.append(validate_trace_record(json.loads(line)))
            except (OSError, ValueError, json.JSONDecodeError, ResultValidationError):
                self.send_json(422, {"error": "result trace is malformed or unsafe"})
                return
        self.send_json(200, {"run_id": run_id, "provenance": result["run"]["provenance"], "trace": trace})

    def handle_action_reroute(self):
        self.handle_disabled_control()

    def handle_disabled_control(self, message="network-changing actions are disabled for the public website"):
        self.send_response(409)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "success": False,
            "simulated": False,
            "error": message
        }).encode('utf-8'))

    def handle_action_rate_limit(self):
        self.handle_disabled_control()

def run_server():
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((HOST, PORT), SDNRequestHandler) as httpd:
        print(f"\n=======================================================")
        print(f"  SELF-X SDN Flow-Management Agent Web Dashboard")
        print(f"  Team SDN_07 | EC466 Software Defined Networks")
        print(f"=======================================================")
        print(f"  Local Dashboard URL  : http://localhost:{PORT}")
        print(f"  Listening on         : {HOST}:{PORT}")
        print(f"  Ryu Controller Target: {RYU_BASE_URL}")
        print(f"  Memory API Endpoint  : http://localhost:{PORT}/api/memory")
        print(f"  Ablation API Endpoint: http://localhost:{PORT}/api/ablation")
        print(f"=======================================================\n")
        print(f"Serving files from: {WEB_DIR}")
        print("Press Ctrl+C to stop the server.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == "__main__":
    run_server()
