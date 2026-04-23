import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError

from tests._fakes import FakeService, FakeTransport  # noqa: F401  (path setup)

from hermes_browser_sidecar.config import SidecarSettings
from hermes_browser_sidecar.server import _build_handler


def _start(service):
    handler_class = _build_handler(service)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_class)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    return httpd, thread, f"http://{host}:{port}"


def _request(method: str, url: str, *, body: dict | None = None, headers: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req_headers = {"Content-Type": "application/json"} if body is not None else {}
    if headers:
        req_headers.update(headers)
    request = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(request, timeout=5.0) as resp:
            payload = resp.read().decode("utf-8")
            return resp.status, dict(resp.headers), json.loads(payload) if payload else {}
    except HTTPError as error:
        payload = error.read().decode("utf-8")
        return error.code, dict(error.headers), json.loads(payload) if payload else {}


class ServerHappyPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = FakeTransport(probe_ok=True)
        self.service = FakeService(
            settings=SidecarSettings.from_env({}),
            transport=self.transport,
        )
        self.httpd, self.thread, self.url = _start(self.service)

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2.0)

    def test_health(self) -> None:
        status, _, body = _request("GET", self.url + "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["protocol_version"], "1.0")

    def test_capabilities(self) -> None:
        status, _, body = _request("GET", self.url + "/v1/capabilities")
        self.assertEqual(status, 200)
        self.assertTrue(body["capabilities"]["session_send"])

    def test_session_state(self) -> None:
        status, _, body = _request(
            "GET", self.url + "/v1/session/state?session_id=panel-1"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["session"]["session_id"], "panel-1")

    def test_session_state_missing_id(self) -> None:
        status, _, body = _request("GET", self.url + "/v1/session/state")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_request")

    def test_send_message(self) -> None:
        status, _, body = _request(
            "POST",
            self.url + "/v1/session/send",
            body={"session_id": "panel-1", "message": "hi"},
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_send_missing_message(self) -> None:
        status, _, body = _request(
            "POST",
            self.url + "/v1/session/send",
            body={"session_id": "panel-1"},
        )
        self.assertEqual(status, 400)

    def test_invalid_json_body(self) -> None:
        request = urllib.request.Request(
            self.url + "/v1/session/send",
            data=b"not json",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5.0) as resp:
                status, body = resp.status, json.loads(resp.read().decode("utf-8"))
        except HTTPError as error:
            status, body = error.code, json.loads(error.read().decode("utf-8"))
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_request")

    def test_unknown_route_404(self) -> None:
        status, _, _ = _request("GET", self.url + "/v1/nonsense")
        self.assertEqual(status, 404)

    def test_reset_and_interrupt(self) -> None:
        for path in ("/v1/session/reset", "/v1/session/interrupt"):
            status, _, body = _request(
                "POST",
                self.url + path,
                body={"session_id": "panel-1"},
            )
            self.assertEqual(status, 200, f"{path} returned {status}: {body}")
            self.assertTrue(body["ok"])


class ServerCorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FakeService(
            settings=SidecarSettings.from_env({}),
            transport=FakeTransport(probe_ok=True),
        )
        self.httpd, self.thread, self.url = _start(self.service)

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2.0)

    def test_options_preflight_chrome_extension(self) -> None:
        request = urllib.request.Request(
            self.url + "/v1/session/send",
            method="OPTIONS",
            headers={
                "Origin": "chrome-extension://abcdef",
                "Access-Control-Request-Method": "POST",
            },
        )
        with urllib.request.urlopen(request, timeout=5.0) as resp:
            self.assertEqual(resp.status, 204)
            self.assertEqual(
                resp.headers.get("Access-Control-Allow-Origin"),
                "chrome-extension://abcdef",
            )
            self.assertIn("POST", resp.headers.get("Access-Control-Allow-Methods", ""))

    def test_non_extension_origin_gets_no_cors_echo(self) -> None:
        request = urllib.request.Request(
            self.url + "/health",
            method="GET",
            headers={"Origin": "https://evil.example"},
        )
        with urllib.request.urlopen(request, timeout=5.0) as resp:
            self.assertIsNone(resp.headers.get("Access-Control-Allow-Origin"))


class ServerNotSupportedMappingTests(unittest.TestCase):
    def test_service_not_supported_returns_501(self) -> None:
        service = FakeService(
            settings=SidecarSettings.from_env({}),
            transport=FakeTransport(probe_ok=True),
            raise_on="send_message",
        )
        httpd, thread, url = _start(service)
        try:
            status, _, body = _request(
                "POST",
                url + "/v1/session/send",
                body={"session_id": "panel-1", "message": "hi"},
            )
            self.assertEqual(status, 501)
            self.assertEqual(body["error"]["code"], "not_supported")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2.0)


if __name__ == "__main__":
    unittest.main()
