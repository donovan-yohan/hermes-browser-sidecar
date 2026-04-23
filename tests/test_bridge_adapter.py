import json
import unittest
from pathlib import Path

from tests._fakes import FakeUpstreamServer, PageContext, REPO_ROOT  # noqa: F401  (path setup)

from hermes_browser_sidecar.transports._http import HermesUpstreamError
from hermes_browser_sidecar.transports.bridge import HermesBridgeTransport


FIXTURE = json.loads((REPO_ROOT / "tests" / "fixtures" / "bridge_session_state.json").read_text())


def _bridge_handler(method: str, path: str, _headers: dict, body: bytes):
    if path == "/health":
        return 200, {"ok": True, "service": "hermes-browser-bridge"}
    if path == "/v1/local-client/request":
        payload = json.loads(body.decode("utf-8")) if body else {}
        action = payload.get("action")
        if action == "list":
            return 200, {"ok": True, "sessions": [FIXTURE]}
        if action in {"state", "send", "reset", "interrupt"}:
            return 200, {"ok": True, **FIXTURE}
        return 400, {"ok": False, "error": f"unknown action {action}"}
    return 404, {"ok": False, "error": "not found"}


class BridgePayloadShapeTests(unittest.TestCase):
    def test_send_message_emits_local_client_request_with_page_context(self) -> None:
        with FakeUpstreamServer(_bridge_handler) as srv:
            transport = HermesBridgeTransport(
                inject_url=srv.url + "/inject",
                token="tok-123",
                browser_label="Test Browser",
            )
            page_ctx = PageContext(
                title="A Page",
                url="https://example.com/",
                selection="sel",
                page_text="body",
                content_kind="webpage",
                metadata={"source": "test"},
            )
            session = transport.send_message(
                session_id="panel-1",
                session_key="resume",
                message="hello",
                page_context=page_ctx,
            )
            self.assertEqual(session.session_id, "panel-1")
            self.assertEqual(session.session_key, "session-1")
            self.assertGreaterEqual(len(session.messages), 1)

        send_request = next(r for r in srv.requests if r["method"] == "POST")
        body = json.loads(send_request["body"].decode("utf-8"))
        self.assertEqual(body["action"], "send")
        self.assertEqual(body["client"]["label"], "Test Browser")
        self.assertEqual(body["client"]["client_session_id"], "panel-1")
        self.assertEqual(body["message"], "hello")
        self.assertIn("context", body)
        self.assertEqual(body["context"]["page_context"]["page_text"], "body")
        self.assertEqual(body["context"]["page_context"]["content_kind"], "webpage")
        self.assertEqual(send_request["headers"].get("Authorization"), "Bearer tok-123")

    def test_list_emits_action_list(self) -> None:
        with FakeUpstreamServer(_bridge_handler) as srv:
            transport = HermesBridgeTransport(
                inject_url=srv.url + "/inject", token="", browser_label="Test"
            )
            sessions = transport.list_sessions(session_id="panel-1", limit=5)
            self.assertEqual(len(sessions), 1)

        body = json.loads(srv.requests[0]["body"].decode("utf-8"))
        self.assertEqual(body["action"], "list")
        self.assertEqual(body["client"]["label"], "Test")
        self.assertEqual(body["client"]["client_session_id"], "panel-1")


class BridgeNormalizationTests(unittest.TestCase):
    def test_normalize_session_returns_snake_case_only(self) -> None:
        transport = HermesBridgeTransport(
            inject_url="http://127.0.0.1:8765/inject", token="", browser_label="x"
        )
        session = transport._normalize_session(session_id="panel-1", raw=FIXTURE)
        as_dict = session.to_dict()
        flat = json.dumps(as_dict)
        for forbidden in ("browserLabel", "clientSessionId", "sessionKey", "pageContext"):
            self.assertNotIn(forbidden, flat)
        self.assertEqual(as_dict["session_id"], "panel-1")
        self.assertEqual(as_dict["session_key"], "session-1")
        self.assertEqual(len(as_dict["messages"]), 2)
        self.assertEqual(as_dict["progress"]["running"], False)


class BridgeErrorTests(unittest.TestCase):
    def test_http_401_raises_upstream_error(self) -> None:
        def handler(_method, path, _headers, _body):
            if path == "/v1/local-client/request":
                return 401, {"ok": False, "error": "unauthorized"}
            return 404, {"ok": False, "error": "not found"}

        with FakeUpstreamServer(handler) as srv:
            transport = HermesBridgeTransport(
                inject_url=srv.url + "/inject", token="bad", browser_label="x"
            )
            with self.assertRaises(HermesUpstreamError) as ctx:
                transport.get_session_state(session_id="panel-1")
            self.assertEqual(ctx.exception.status_code, 401)


class BridgeProbeTests(unittest.TestCase):
    def test_probe_ok(self) -> None:
        with FakeUpstreamServer(_bridge_handler) as srv:
            transport = HermesBridgeTransport(
                inject_url=srv.url + "/inject", token="", browser_label="x"
            )
            probe = transport.probe()
            self.assertTrue(probe.ok)
            self.assertEqual(probe.status_code, 200)

    def test_probe_unreachable_when_port_closed(self) -> None:
        transport = HermesBridgeTransport(
            inject_url="http://127.0.0.1:1/inject", token="", browser_label="x"
        )
        probe = transport.probe()
        self.assertFalse(probe.ok)


if __name__ == "__main__":
    unittest.main()
