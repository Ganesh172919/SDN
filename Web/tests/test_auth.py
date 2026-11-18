import json
import threading
import unittest
import urllib.request
import urllib.error
import socketserver
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.dirname(TEST_DIR)
PROJECT_ROOT = os.path.dirname(WEB_DIR)
for p in (PROJECT_ROOT, WEB_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import server
from server import SDNRequestHandler


class AuthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = Path(cls.enterClassContext(TemporaryDirectory()))
        cls.enterClassContext(patch.object(server, "USER_DATA_DIR", directory))
        cls.enterClassContext(patch.object(server, "USER_DATA_FILE", directory / "users.json"))
        cls.enterClassContext(patch.dict(server.USERS_DB, server.DEFAULT_USERS, clear=True))
        cls.enterClassContext(patch.dict(server.ACTIVE_SESSIONS, clear=True))
        socketserver.TCPServer.allow_reuse_address = True
        cls.server = socketserver.TCPServer(("127.0.0.1", 0), SDNRequestHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _post(self, path, payload, headers=None):
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status, resp.headers, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            return err.code, err.headers, json.loads(err.read().decode("utf-8"))

    def _get(self, path, headers=None):
        req_headers = {}
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(f"{self.base_url}{path}", headers=req_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status, resp.headers, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            return err.code, err.headers, json.loads(err.read().decode("utf-8"))

    def test_auth_status_endpoint(self):
        status, _, body = self._get("/api/auth/status")
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertGreaterEqual(body["registered_users"], 4)
        self.assertIn("admin", body["roles"])
        self.assertIn("operator", body["roles"])
        self.assertIn("researcher", body["roles"])
        self.assertIn("auditor", body["roles"])

    def test_auth_me_unauthenticated(self):
        status, _, body = self._get("/api/auth/me")
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertFalse(body["authenticated"])
        self.assertIsNone(body["user"])
        self.assertIn("demo_accounts", body)

    def test_demo_accounts_login(self):
        for demo in ["admin", "operator", "researcher", "auditor"]:
            token = f"demo_token_{demo}_2026"
            status, _, body = self._get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(status, 200)
            self.assertTrue(body["authenticated"])
            self.assertEqual(body["user"]["username"], demo)
            self.assertEqual(body["user"]["role"], demo)
            self.assertIn("permissions", body["user"])

    def test_user_registration_and_login_flow(self):
        import uuid
        uid = uuid.uuid4().hex[:8]
        new_user = {
            "username": f"user_{uid}",
            "email": f"user_{uid}@selfx-sdn.net",
            "password": "SecurePassword123!",
            "role": "operator"
        }
        # Register
        status, headers, body = self._post("/api/auth/register", new_user)
        self.assertEqual(status, 201)
        self.assertTrue(body["success"])
        self.assertIn("token", body)
        self.assertEqual(body["user"]["username"], f"user_{uid}")
        self.assertEqual(body["user"]["role"], "operator")
        token = body["token"]

        # Verify token via /api/auth/me
        status, _, me_body = self._get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(status, 200)
        self.assertTrue(me_body["authenticated"])
        self.assertEqual(me_body["user"]["username"], f"user_{uid}")
        self.assertIn("control", me_body["user"]["permissions"])

        # Login with same credentials
        login_payload = {"username": f"user_{uid}", "password": "SecurePassword123!"}
        status, _, login_body = self._post("/api/auth/login", login_payload)
        self.assertEqual(status, 200)
        self.assertTrue(login_body["success"])
        self.assertEqual(login_body["user"]["username"], f"user_{uid}")

        # Duplicate registration rejected
        status, _, dup_body = self._post("/api/auth/register", new_user)
        self.assertEqual(status, 409)
        self.assertFalse(dup_body["success"])

        # Invalid login rejected
        bad_login = {"username": f"user_{uid}", "password": "WrongPassword!"}
        status, _, bad_body = self._post("/api/auth/login", bad_login)
        self.assertEqual(status, 401)
        self.assertFalse(bad_body["success"])

        # Logout
        status, _, logout_body = self._post("/api/auth/logout", {}, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(status, 200)
        self.assertTrue(logout_body["success"])

        # Post-logout token invalidated
        status, _, post_me = self._get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(status, 200)
        self.assertFalse(post_me["authenticated"])

    def test_registration_validation(self):
        # Short username
        status, _, body = self._post("/api/auth/register", {"username": "ab", "email": "a@b.com", "password": "123"})
        self.assertEqual(status, 400)

        # Invalid email
        status, _, body = self._post("/api/auth/register", {"username": "validname", "email": "invalidemail", "password": "123456password"})
        self.assertEqual(status, 400)

        # Short password
        status, _, body = self._post("/api/auth/register", {"username": "validname", "email": "valid@email.com", "password": "123"})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
