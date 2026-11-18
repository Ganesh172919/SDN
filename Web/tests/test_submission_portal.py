import json
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).parents[1]))
import server


class SubmissionPortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = Path(cls.enterClassContext(TemporaryDirectory()))
        cls.release = directory / "current"
        cls.release.mkdir()
        cls.enterClassContext(patch.object(server, "CURRENT_SUBMISSION_DIR", cls.release))

        for name in ("SELF_X_Submission.zip", "Overleaf_Source.zip"):
            with ZipFile(cls.release / name, "w") as archive:
                archive.writestr("README.md", "Submission fixture")
        (cls.release / "SELF_X_Revision_Report.pdf").write_bytes(b"%PDF-1.4\n")
        (cls.release / "local-only.txt").write_text("Unpublished fixture.", encoding="utf-8")
        (cls.release / "SHA256SUMS.txt").write_text(
            f"{sha256((cls.release / 'SELF_X_Submission.zip').read_bytes()).hexdigest()}  SELF_X_Submission.zip\n",
            encoding="utf-8",
        )

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
        cls.thread.join(timeout=5)

    def get(self, path):
        try:
            response = urllib.request.urlopen(self.base_url + path, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read()

    def test_submission_info_matches_download_bytes(self):
        status, headers, body = self.get("/api/submission/info")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("Content-Type", ""))
        metadata = json.loads(body)
        self.assertEqual(metadata["team_id"], "SDN_07")
        self.assertEqual(metadata["course"], "EC466 Software Defined Networks")
        self.assertEqual(metadata["submission_zip_status"], "UNDER_100MB")
        self.assertEqual(metadata["google_form_url"], "https://forms.gle/5DbSbyJUqFwpXSYM9")
        items = {item["name"]: item for item in metadata["artifacts"]}
        self.assertNotIn("local-only.txt", items)
        bundle = items["SELF_X_Submission.zip"]
        status, _, content = self.get(bundle["download_url"])
        self.assertEqual(status, 200)
        self.assertEqual(bundle["size_bytes"], len(content))
        self.assertEqual(bundle["sha256"], sha256(content).hexdigest())
        self.assertIsNone(items["SHA256SUMS.txt"]["sha256"])

    def test_source_checkout_reports_missing_bundle(self):
        with TemporaryDirectory() as empty, patch.object(server, "CURRENT_SUBMISSION_DIR", Path(empty)):
            status, _, body = self.get("/api/submission/info")
            self.assertEqual(status, 200)
            metadata = json.loads(body)
            self.assertEqual(metadata["submission_zip_status"], "NOT_BUILT")
            self.assertIsNone(metadata["submission_zip_size_mb"])
            self.assertNotIn("SELF_X_Submission.zip", {entry["name"] for entry in metadata["artifacts"]})
            self.assertEqual(self.get("/downloads/SELF_X_Submission.zip")[0], 404)
            self.assertEqual(self.get("/downloads/SELF_X_IEEE_Paper.pdf")[0], 200)

    def test_manuscript_and_legacy_figures_are_served(self):
        for path, mime in (
            ("/comparison/paper_architecture.pdf", "application/pdf"),
            ("/paper/figures/fig1_architecture.png", "image/png"),
            ("/paper/figures/fig2_traffic.png", "image/png"),
        ):
            status, headers, body = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertIn(mime, headers.get("Content-Type", ""))
            self.assertGreater(len(body), 1000)

    def test_downloads_only_serve_listed_artifacts(self):
        for name in ("Overleaf_Source.zip", "SELF_X_Revision_Report.pdf", "SHA256SUMS.txt"):
            status, _, body = self.get(f"/downloads/{name}")
            self.assertEqual(status, 200, name)
            self.assertEqual(body, (self.release / name).read_bytes())
        self.assertEqual(self.get("/downloads/local-only.txt")[0], 404)

    def test_static_site_serves_only_public_pages_and_assets(self):
        with TemporaryDirectory() as directory, patch.object(server, "WEB_DIR", directory):
            root = Path(directory)
            (root / "index.html").write_text("Home", encoding="utf-8")
            (root / "js").mkdir()
            (root / "js" / "app.js").write_text("'Public asset';", encoding="utf-8")
            (root / "data").mkdir()
            (root / "data" / "fixture.json").write_text("{}", encoding="utf-8")
            self.assertEqual(self.get("/")[0], 200)
            self.assertEqual(self.get("/js/app.js")[0], 200)
            self.assertEqual(self.get("/js/")[0], 404)
            self.assertEqual(self.get("/data/fixture.json")[0], 404)


if __name__ == "__main__":
    unittest.main()
