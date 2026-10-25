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

PORT = int(os.environ.get("SDN_WEB_PORT", 5000))
RYU_BASE_URL = os.environ.get("RYU_REST_BASE", "http://127.0.0.1:8080")
RESULTS_ROOT = Path(os.environ.get("SELFX_RESULTS_ROOT", Path(PROJECT_ROOT) / "results")).resolve()
BENCHMARKS_V4_SUMMARY = (Path(PROJECT_ROOT) / "selfx" / "output" / "benchmarks" / "v4" / "summary.json").resolve()
EXPERIMENTS_DIR = (Path(PROJECT_ROOT) / "selfx" / "output" / "experiments").resolve()
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class SDNRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'same-origin')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        path = urlsplit(self.path).path
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

        # API: Live Episodic Memory Bank
        if path == '/api/memory':
            self.handle_memory()
            return

        # API: Real Ablation Benchmark Logs (A0 vs A1 vs A2 CSVs)
        if path == '/api/ablation':
            self.handle_ablation()
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
                    ryu_online = True
                    content = resp.read().decode('utf-8')
                    switches = json.loads(content)
        except Exception:
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
            "benchmarks_available": BENCHMARKS_V4_SUMMARY.is_file()
        }
        self.send_json(200, data)

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
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), SDNRequestHandler) as httpd:
        print(f"\n=======================================================")
        print(f"  SELF-X SDN Flow-Management Agent Web Dashboard")
        print(f"  Team SDN_07 | EC466 Software Defined Networks")
        print(f"=======================================================")
        print(f"  Local Dashboard URL  : http://localhost:{PORT}")
        print(f"  Network Dashboard URL: http://127.0.0.1:{PORT}")
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
            httpd.shutdown()

if __name__ == "__main__":
    run_server()
