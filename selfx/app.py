"""Loopback-only dashboard. Serves an explicit allowlist, never the project tree."""
from __future__ import annotations
import argparse
import csv
import json
import mimetypes
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
RUNS = {"venv_v4":"Loss-aware A4 full experiment in .venv","gemini_v4":"Bounded Gemini project run","openrouter_v4":"Bounded OpenRouter project run","venv_v3":"Previous v3 experiment","adaptive":"Latest adaptive experiment","fast_gemini_demo":"Previous fast Gemini check","venv_full": "Previous portable experiment", "gemini_venv": "Previous Gemini .venv pilot", "offline": "Original portable experiment", "gemini_paced": "Gemini three-seed pilot", "openrouter": "OpenRouter free diagnostic", "gemini": "Gemini unpaced diagnostic", "dashboard": "Latest dashboard run"}
JOB = {"status": "idle", "message": "Ready"}
LOCK = threading.Lock()


def experiment_dirs():
    return {name: ROOT / "output" / "experiments" / name for name in RUNS}


def run_offline(cycles, seed):
    try:
        command = [sys.executable, "-m", "eval.run_simulation", "--cycles", str(cycles), "--seeds", str(seed), "--out-dir", str(ROOT / "output" / "experiments" / "dashboard")]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=90)
        JOB.update(status="completed" if result.returncode == 0 else "failed", message="Experiment ready in Latest dashboard run" if result.returncode == 0 else "Run failed; check the local Python environment")
    except Exception:
        JOB.update(status="failed", message="Run failed; check the local Python environment")
    finally:
        LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def send(self, data, mime="application/json", status=200):
        payload = json.dumps(data).encode() if mime == "application/json" else data
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        route = urlparse(self.path)
        query = parse_qs(route.query)
        if route.path == "/api/health":
            return self.send({"status": "ok", "provenance": "simulation", "job": JOB,
                              "runtime": {"python": sys.executable,"virtual_environment":sys.prefix!=sys.base_prefix}})
        if route.path == "/api/benchmarks":
            path=ROOT/"output"/"benchmarks"/"v4"/"summary.json"
            if not path.exists():
                return self.send({"error":"Run .\\run.ps1 benchmark first"},status=404)
            return self.send(json.loads(path.read_text(encoding="utf-8")))
        if route.path=='/api/latency':
            datasets={}
            for provider in ('gemini','openrouter'):
                path=ROOT/f'output/benchmarks/v4/latency_{provider}_pooled/summary.json'
                if path.exists():datasets[provider]=json.loads(path.read_text(encoding='utf-8'))
            return self.send({'providers':datasets})
        if route.path=='/api/rule-demo':
            provider=query.get('provider',['gemini'])[0]
            if provider not in ('gemini','openrouter','offline'):return self.send({'error':'Unknown provider'},status=400)
            folder=ROOT/f'output/benchmarks/v4/latency_{provider}_pooled' if provider!='offline' else ROOT/'output/benchmarks/v4/rule_demo_offline'
            if not (folder/'trace.jsonl').exists():return self.send({'error':'Run the provider demo first'},status=404)
            records=[json.loads(line) for line in (folder/'trace.jsonl').read_text(encoding='utf-8').splitlines()]
            return self.send({'provider':provider,'records':[r for r in records if r['metrics']['mode']=='bounded'],
                'final_expiry':json.loads((folder/'rule_expiry.json').read_text(encoding='utf-8'))})
        if route.path == "/api/experiments":
            results = []
            for name, directory in experiment_dirs().items():
                if (directory / "summary.json").is_file():
                    results.append({"id": name, "label": RUNS[name], "summary": json.loads((directory / "summary.json").read_text(encoding="utf-8"))})
            return self.send({"experiments": results, "job": JOB})
        if route.path == "/api/trace":
            name = query.get("run", ["offline"])[0]
            if name not in RUNS:
                return self.send({"error": "unknown experiment"}, status=404)
            path = experiment_dirs()[name] / "trace.jsonl"
            if not path.exists():
                return self.send({"error": "experiment not run yet"}, status=404)
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()[:5000]]
            condition = query.get("condition", [None])[0]
            seed = query.get("seed", [None])[0]
            if condition is not None:
                records = [r for r in records if r["metrics"]["condition"] == condition]
            if seed is not None:
                records = [r for r in records if str(r["metrics"]["seed"]) == seed]
            return self.send({"records": records})
        if route.path == "/api/providers":
            path = ROOT / "output" / "provider_check.json"
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                return self.send({"checked_at_utc": data["checked_at_utc"], "checks": data["checks"],
                                  "free_model_count": len(data["catalogs"]["openrouter"]["models"])})
            return self.send({"checks": []})
        static = {"/": ROOT / "web" / "index.html", "/app.js": ROOT / "web" / "app.js", "/style.css": ROOT / "web" / "style.css",
                  "/benchmarks.js": ROOT / "web" / "benchmarks.js", "/benchmarks.css": ROOT / "web" / "benchmarks.css", "/rule-demo.js":ROOT/"web/rule-demo.js",
                  "/architecture": ROOT / "docs" / "ARCHITECTURE.md", "/readme": ROOT / "README.md"}
        for filename in ("SELF_X_Report.docx", "SELF_X_Report.pdf", "SELF_X_Presentation.pptx", "SELF_X_Presentation.pdf", "SELF_X_Benchmark_Atlas.pdf"):
            static["/download/" + filename] = ROOT / "output" / "submission" / filename
        figures={"traffic_scenarios","scenario_latency_matrix","paired_memory_effect","guard_ablation","distribution_ecdf","metric_tradeoffs","actions_and_vetoes","queue_shift_heatmap","offline_control_overhead","api_latency_compare","api_call_origins","api_timeline","free_model_availability","memory_sensitivity","memory_learning","rule_lifecycle","loss_breakdown"}
        for name in figures:
            static["/benchmark-figure/"+name+".png"]=ROOT/"output/benchmarks/v4/figures"/(name+".png")
        path = static.get(route.path)
        if path and path.is_file():
            return self.send(path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        return self.send({"error": "not found"}, status=404)

    def do_POST(self):
        if self.path != "/api/run":
            return self.send({"error": "not found"}, status=404)
        # Browser requests must come from this exact loopback origin.
        if self.headers.get("Origin") != f"http://{self.headers.get('Host')}" or self.headers.get("X-Selfx-Request") != "dashboard":
            return self.send({"error": "invalid origin"}, status=403)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 1024:
                raise ValueError()
            body = json.loads(self.rfile.read(length))
            cycles, seed = body.get("cycles", 24), body.get("seed", 1729)
            if type(cycles) is not int or not 1 <= cycles <= 120 or type(seed) is not int or not 0 <= seed <= 2**31-1:
                raise ValueError()
        except (ValueError, TypeError):
            return self.send({"error": "cycles must be 1..120 and seed a nonnegative integer"}, status=400)
        if not LOCK.acquire(blocking=False):
            return self.send({"error": "an experiment is already running"}, status=409)
        JOB.update(status="running", message="Running the same traffic through five controllers including adaptive memory")
        threading.Thread(target=run_offline, args=(cycles, seed), daemon=True).start()
        return self.send(JOB, status=202)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    print(f"SELF-X dashboard: http://127.0.0.1:{args.port}", flush=True)
    try:
        ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    except OSError:
        raise SystemExit("Cannot open local port; try --port 8766")


if __name__ == "__main__":
    main()
