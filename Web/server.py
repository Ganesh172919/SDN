#!/usr/bin/env python3
"""
server.py - Full-Stack REST Bridge & Web Server for SELF-X SDN Flow Manager
Connects the web dashboard directly to your live Mininet OpenFlow testbed,
Ryu REST Controller (ofctl_rest), LangGraph agent memory, and evaluation logs.

Features:
- Proxies all GET/POST Ryu ofctl_rest API calls (switches, flows, ports, flow-mod, meters) with CORS headers.
- Dynamically reads real episodic memory bank records from `agent_memory.json` or `eval/logs/A2_memory.json`.
- Dynamically reads and parses real evaluation ablation logs (A0.csv, A1.csv, A2.csv).
- Fallback simulation telemetry when Ryu/Mininet is offline, enabling zero-friction development.
"""

import os
import sys
import json
import csv
import http.server
import socketserver
import urllib.request
import urllib.error

PORT = int(os.environ.get("SDN_WEB_PORT", 5000))
RYU_BASE_URL = os.environ.get("RYU_REST_BASE", "http://127.0.0.1:8080")
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(WEB_DIR)

class SDNRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        # Enable CORS and caching headers for seamless frontend access
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        # API: Real-time System Status & Ryu Controller Health
        if self.path == '/api/status':
            self.handle_status()
            return

        # API: Live Episodic Memory Bank
        if self.path == '/api/memory':
            self.handle_memory()
            return

        # API: Real Ablation Benchmark Logs (A0 vs A1 vs A2 CSVs)
        if self.path == '/api/ablation':
            self.handle_ablation()
            return

        # API: Proxy Ryu ofctl_rest GET endpoints
        if self.path.startswith('/api/ryu/'):
            self.handle_ryu_proxy(method='GET')
            return

        # Default static web files
        return super().do_GET()

    def do_POST(self):
        # API: Proxy Ryu ofctl_rest POST endpoints (flowentry/add, meterentry/add)
        if self.path.startswith('/api/ryu/'):
            self.handle_ryu_proxy(method='POST')
            return

        # API: Direct Flow Reroute Helper
        if self.path == '/api/action/reroute':
            self.handle_action_reroute()
            return

        # API: Direct Rate Limit Helper
        if self.path == '/api/action/rate_limit':
            self.handle_action_rate_limit()
            return

        self.send_response(404)
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
            "ryu_base_url": RYU_BASE_URL,
            "connected_switches": switches,
            "project": "SELF-X SDN Agent",
            "course": "EC466 Software Defined Networks",
            "team": "SDN_07"
        }
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

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
                "source": source_path,
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

    def handle_ryu_proxy(self, method='GET'):
        subpath = self.path[len('/api/ryu/'):]
        target_url = f"{RYU_BASE_URL}/{subpath}"

        try:
            req_data = None
            headers = {'User-Agent': 'SDN-Dashboard'}

            if method == 'POST':
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    req_data = self.rfile.read(content_length)
                headers['Content-Type'] = self.headers.get('Content-Type', 'application/json')

            req = urllib.request.Request(target_url, data=req_data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                content = resp.read()
                self.send_response(resp.status)
                self.send_header('Content-Type', resp.headers.get('Content-Type', 'application/json'))
                self.end_headers()
                self.wfile.write(content)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": f"Failed to connect to Ryu at {target_url}: {e}",
                "hint": "Start Ryu controller: ryu-manager ryu.app.ofctl_rest ryu.app.simple_switch_13"
            }).encode('utf-8'))

    def handle_action_reroute(self):
        # Sends OpenFlow 1.3 Flow-Mod rule to switch s2 (dpid=2) to steer elephant traffic to Port 4
        flow_rule = {
            "dpid": 2,
            "cookie": 0,
            "table_id": 0,
            "priority": 200,
            "match": {
                "in_port": 2,
                "eth_type": 2048,
                "ipv4_dst": "10.0.0.8"
            },
            "actions": [
                {"type": "OUTPUT", "port": 4}
            ]
        }
        target_url = f"{RYU_BASE_URL}/stats/flowentry/add"
        try:
            req = urllib.request.Request(
                target_url,
                data=json.dumps(flow_rule).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": "Flow reroute installed on live Ryu controller (Port 4)."}).encode('utf-8'))
        except Exception as e:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "simulated": True,
                "message": f"Ryu controller offline ({e}). Applied reroute in simulated engine."
            }).encode('utf-8'))

    def handle_action_rate_limit(self):
        # Sends OpenFlow 1.3 Meter entry to switch s2 to cap bandwidth to 6144 kbps
        meter_rule = {
            "dpid": 2,
            "meter_id": 1,
            "flags": ["KBPS"],
            "bands": [
                {"type": "DROP", "rate": 6144, "burst_size": 0}
            ]
        }
        target_url = f"{RYU_BASE_URL}/stats/meterentry/add"
        try:
            req = urllib.request.Request(
                target_url,
                data=json.dumps(meter_rule).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": "OpenFlow meter rule installed on live Ryu controller (6 Mbps ceiling)."}).encode('utf-8'))
        except Exception as e:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "simulated": True,
                "message": f"Ryu controller offline ({e}). Applied rate-limit in simulated engine."
            }).encode('utf-8'))

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
