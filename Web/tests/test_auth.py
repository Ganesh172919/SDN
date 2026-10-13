import http.cookiejar
import os
import re
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

os.environ["SELFX_AUTH_USERNAME"] = "test-user"
os.environ["SELFX_AUTH_SESSION_TTL"] = "2"
os.environ["SELFX_AUTH_SECURE_COOKIE"] = "0"

import sys

sys.path.insert(0, str(Path(__file__).parents[1]))
import server


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, msg, headers, newurl):
        return None


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.AUTH_USERNAME = "test-user"
        server.AUTH_PASSWORD_HASH = server.hash_password("correct-password")
        server.AUTH_SESSION_TTL = 2
        server.SESSIONS.clear()
        cls.httpd = server.socketserver.ThreadingTCPServer(
            ("127.0.0.1", 0), server.SDNRequestHandler
        )
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.SESSIONS.clear()

    def setUp(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar), NoRedirect()
        )

    def request(self, path, method="GET", data=None, headers=None):
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=headers or {},
            method=method,
        )
        try:
            response = self.opener.open(request, timeout=3)
            return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()

    def login_page(self):
        status, _, body = self.request("/login")
        self.assertEqual(status, 200)
        token = re.search(rb'name="csrf_token" value="([^"]+)"', body).group(1).decode()
        return token

    def login(self, password="correct-password"):
        token = self.login_page()
        data = urllib.parse.urlencode({
            "username": "test-user",
            "password": password,
            "csrf_token": token,
        }).encode()
        return self.request(
            "/api/auth/login",
            method="POST",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def cookie(self, name):
        return next((item.value for item in self.jar if item.name == name), "")

    def test_successful_login_creates_http_only_session(self):
        status, headers, body = self.login()
        self.assertEqual(status, 200, body)
        self.assertIn("sfx_session=", headers.get_all("Set-Cookie")[0])
        self.assertIn("SameSite=Lax", headers.get_all("Set-Cookie")[0])
        self.assertIn("HttpOnly", headers.get_all("Set-Cookie")[0])
        session_cookie = next(item for item in self.jar if item.name == "sfx_session")
        self.assertTrue(any(key.lower() == "httponly" for key in session_cookie._rest))
        status, _, body = self.request("/api/auth/session")
        self.assertEqual(status, 200, body)
        self.assertIn(b"test-user", body)

    def test_invalid_credentials_are_rejected(self):
        status, _, body = self.login(password="wrong-password")
        self.assertEqual(status, 401)
        self.assertIn(b"invalid credentials", body)
        self.assertEqual(self.cookie("sfx_session"), "")

    def test_unauthenticated_dashboard_and_api_are_protected(self):
        status, headers, _ = self.request("/")
        self.assertEqual(status, 303)
        self.assertEqual(headers.get("Location"), "/login")
        status, _, body = self.request("/api/status")
        self.assertEqual(status, 401)
        self.assertIn(b"authentication required", body)

    def test_session_expiration(self):
        self.assertEqual(self.login()[0], 200)
        session_id = self.cookie("sfx_session")
        server.SESSIONS[session_id].last_seen -= server.AUTH_SESSION_TTL + 1
        status, _, _ = self.request("/api/auth/session")
        self.assertEqual(status, 401)
        self.assertNotIn(session_id, server.SESSIONS)

    def test_logout_invalidates_session(self):
        self.assertEqual(self.login()[0], 200)
        csrf = self.cookie("sfx_csrf")
        status, _, _ = self.request(
            "/api/auth/logout",
            method="POST",
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(status, 200)
        status, _, _ = self.request("/api/auth/session")
        self.assertEqual(status, 401)

    def test_csrf_protects_login_and_logout(self):
        self.login_page()
        data = urllib.parse.urlencode({
            "username": "test-user",
            "password": "correct-password",
        }).encode()
        status, _, _ = self.request(
            "/api/auth/login",
            method="POST",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(status, 403)

        self.assertEqual(self.login()[0], 200)
        status, _, _ = self.request(
            "/api/auth/logout",
            method="POST",
            headers={"X-CSRF-Token": "wrong-token"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.request("/api/auth/session")[0], 200)

    def test_authenticated_network_control_writes_remain_disabled(self):
        self.assertEqual(self.login()[0], 200)
        status, _, body = self.request(
            "/api/ryu/stats/flowentry/add",
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 409)
        self.assertIn(b"disabled", body)


if __name__ == "__main__":
    unittest.main()
