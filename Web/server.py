#!/usr/bin/env python3
"""
server.py - Full-Stack REST Bridge & Web Server for SELF-X SDN Flow Manager
Connects the web dashboard directly to your live Mininet OpenFlow testbed,
Ryu REST Controller (ofctl_rest), LangGraph agent memory, and evaluation logs.

Read-only endpoint contract used by the dashboard:
- GET /login -> server-rendered login page with a CSRF token.
- POST /api/auth/login -> form login; returns {success, redirect} or an error.
- GET /api/auth/session -> authenticated user or HTTP 401.
- POST /api/auth/logout -> invalidates the session; requires X-CSRF-Token.
- GET /api/status -> {status, ryu_controller, ryu_base_url, connected_switches, project, course, team}
- GET /api/memory -> {success, is_live_project, source, count, entries} when memory exists,
    otherwise {success: false, is_live_project: false, message}.
- GET /api/ablation -> {success, conditions}, where conditions contains any available
    A0/A1/A2 CSV rows.
- GET /api/ryu/<path> -> a proxied Ryu response, or HTTP 502 when unavailable.

The dashboard's direct action helpers are intentionally disabled in this phase. They
return HTTP 409 and do not issue OpenFlow writes. Simulation actions are browser-local.
"""

import os
import sys
import json
import csv
import base64
import hashlib
import http.server
import hmac
import secrets
import socketserver
import time
from dataclasses import dataclass
from getpass import getpass
import urllib.request
import urllib.error
from urllib.parse import parse_qs, urlsplit

PORT = int(os.environ.get("SDN_WEB_PORT", 5000))
RYU_BASE_URL = os.environ.get("RYU_REST_BASE", "http://127.0.0.1:8080")
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(WEB_DIR)
AUTH_USERNAME = os.environ.get("SELFX_AUTH_USERNAME", "")
AUTH_PASSWORD_HASH = os.environ.get("SELFX_AUTH_PASSWORD_HASH", "")
AUTH_SESSION_TTL = int(os.environ.get("SELFX_AUTH_SESSION_TTL", "1800"))
AUTH_SECURE_COOKIE = os.environ.get("SELFX_AUTH_SECURE_COOKIE", "0") == "1"
SESSION_COOKIE = "sfx_session"
CSRF_COOKIE = "sfx_csrf"
PBKDF2_ITERATIONS = 310_000


@dataclass
class Session:
    username: str
    csrf_token: str
    created_at: float
    last_seen: float


SESSIONS = {}


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


DUMMY_PASSWORD_HASH = hash_password("invalid-credential")


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("ascii"), int(iterations)
        ).hex()
        return hmac.compare_digest(digest, expected)
    except (TypeError, ValueError):
        return False


def credentials_valid(username, password):
    stored_hash = AUTH_PASSWORD_HASH or DUMMY_PASSWORD_HASH
    username_matches = hmac.compare_digest(username, AUTH_USERNAME or "disabled")
    password_matches = verify_password(password, stored_hash)
    return bool(AUTH_USERNAME and AUTH_PASSWORD_HASH) and username_matches and password_matches


def cookie_value(cookie_header, name):
    if not cookie_header:
        return ""
    for item in cookie_header.split(";"):
        key, separator, value = item.strip().partition("=")
        if separator and key == name:
            return value
    return ""


def cookie_header(name, value, max_age=None, http_only=False):
    parts = [f"{name}={value}", "Path=/", "SameSite=Lax"]
    if max_age is not None:
        parts.append(f"Max-Age={max_age}")
    if http_only:
        parts.append("HttpOnly")
    if AUTH_SECURE_COOKIE:
        parts.append("Secure")
    return "; ".join(parts)

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
            self.handle_login_page()
            return
        if path == '/api/auth/session':
            self.handle_session()
            return
        if path == '/api/auth/csrf':
            self.handle_csrf()
            return
        if path.startswith('/api/') and not self.require_auth(api=True):
            return
        if path in ('/', '/index.html') and not self.require_auth(api=False):
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

        # API: Proxy Ryu ofctl_rest GET endpoints
        if path.startswith('/api/ryu/'):
            self.handle_ryu_proxy(method='GET')
            return

        # Default static web files
        return super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == '/api/auth/login':
            self.handle_login()
            return
        if path == '/api/auth/logout':
            if self.require_auth(api=True) and self.require_csrf():
                self.handle_logout()
            return
        if path.startswith('/api/') and not self.require_auth(api=True):
            return

        # Ryu writes remain disabled during Phase 2.
        if path.startswith('/api/ryu/'):
            self.handle_disabled_control()
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

    def require_auth(self, api):
        session_id = cookie_value(self.headers.get('Cookie'), SESSION_COOKIE)
        session = SESSIONS.get(session_id)
        if not session or time.time() - session.last_seen > AUTH_SESSION_TTL:
            if session_id:
                SESSIONS.pop(session_id, None)
            if api:
                self.send_json(401, {"error": "authentication required"})
            else:
                self.send_response(303)
                self.send_header('Location', '/login')
                self.end_headers()
            return False
        session.last_seen = time.time()
        self.session = session
        return True

    def require_csrf(self):
        submitted = self.headers.get('X-CSRF-Token', '')
        if not submitted:
            submitted = self.form_value('csrf_token')
        valid = bool(getattr(self, 'session', None)) and hmac.compare_digest(
            submitted, self.session.csrf_token
        )
        if not valid:
            self.send_json(403, {"error": "CSRF validation failed"})
        return valid

    def read_form(self):
        length = min(int(self.headers.get('Content-Length', 0)), 64 * 1024)
        body = self.rfile.read(length).decode('utf-8', errors='replace') if length else ''
        return {key: values[0] for key, values in parse_qs(body).items()}

    def form_value(self, name):
        if not hasattr(self, '_form_data'):
            self._form_data = self.read_form()
        return self._form_data.get(name, '')

    def handle_login_page(self):
        token = cookie_value(self.headers.get('Cookie'), CSRF_COOKIE) or secrets.token_urlsafe(32)
        try:
            with open(os.path.join(WEB_DIR, 'login.html'), 'r', encoding='utf-8') as file:
                page = file.read().replace('{{CSRF_TOKEN}}', token)
        except OSError:
            self.send_error(500, 'login page unavailable')
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Set-Cookie', cookie_header(CSRF_COOKIE, token))
        self.end_headers()
        self.wfile.write(page.encode('utf-8'))

    def handle_login(self):
        form = self.read_form()
        csrf = form.get('csrf_token', '')
        csrf_cookie = cookie_value(self.headers.get('Cookie'), CSRF_COOKIE)
        username = form.get('username', '')
        password = form.get('password', '')
        if not csrf or not csrf_cookie or not hmac.compare_digest(csrf, csrf_cookie):
            self.send_json(403, {"error": "CSRF validation failed"})
            return
        if not credentials_valid(username, password):
            self.send_json(401, {"error": "invalid credentials"})
            return

        now = time.time()
        session_id = secrets.token_urlsafe(32)
        session = Session(username, secrets.token_urlsafe(32), now, now)
        SESSIONS[session_id] = session
        self.send_json(200, {"success": True, "redirect": "/"}, {
            'Set-Cookie': [
                cookie_header(SESSION_COOKIE, session_id, http_only=True),
                cookie_header(CSRF_COOKIE, session.csrf_token),
            ]
        })

    def handle_logout(self):
        session_id = cookie_value(self.headers.get('Cookie'), SESSION_COOKIE)
        SESSIONS.pop(session_id, None)
        self.send_json(200, {"success": True}, {
            'Set-Cookie': cookie_header(SESSION_COOKIE, '', max_age=0, http_only=True)
        })

    def handle_session(self):
        if not self.require_auth(api=True):
            return
        self.send_json(200, {"authenticated": True, "username": self.session.username})

    def handle_csrf(self):
        token = cookie_value(self.headers.get('Cookie'), CSRF_COOKIE) or secrets.token_urlsafe(32)
        self.send_json(200, {"csrf_token": token}, {
            'Set-Cookie': cookie_header(CSRF_COOKIE, token)
        })

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
        self.handle_disabled_control()

    def handle_disabled_control(self):
        self.send_response(409)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "success": False,
            "simulated": False,
            "error": "live network actions are disabled during Web Phase 1"
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
    if "--hash-password" in sys.argv:
        print(hash_password(getpass("Password to hash: ")))
    else:
        run_server()
