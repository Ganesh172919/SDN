import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen, Request
import pytest
from app import Handler


@pytest.fixture
def server_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def test_dashboard_never_serves_credentials_or_project_files(server_url):
    assert json.load(urlopen(server_url + "/api/health"))["status"] == "ok"
    for path in ("/.env", "/.git/config", "/../.env", "/config.py", "/output/provider_check.json"):
        with pytest.raises(HTTPError) as error:
            urlopen(server_url + path)
        assert error.value.code == 404


def test_cross_origin_and_invalid_replay_are_rejected(server_url):
    req = Request(server_url + "/api/run", data=b'{}', method="POST", headers={"Origin": "https://example.com"})
    with pytest.raises(HTTPError) as error:
        urlopen(req)
    assert error.value.code == 403
    req = Request(server_url + "/api/run", data=b'{"cycles":99999}', method="POST", headers={"Origin": server_url, "X-Selfx-Request": "dashboard"})
    with pytest.raises(HTTPError) as error:
        urlopen(req)
    assert error.value.code == 400
