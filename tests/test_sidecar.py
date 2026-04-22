import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from hermes_browser_sidecar.config import SidecarSettings
from hermes_browser_sidecar.server import _build_handler
from hermes_browser_sidecar.service import SidecarService
from hermes_browser_sidecar.transports.bridge import HermesBridgeTransport


class _FakeBridgeTransport:
    supports_sessions = True

    def __init__(self) -> None:
        self.calls = []

    def probe(self):
        raise AssertionError("probe should not be called in this test")

    def get_session_state(self, **kwargs):
        self.calls.append(("state", kwargs))
        return {"session_key": "session-1", "messages": [], "progress": {"running": False}}

    def list_sessions(self, **kwargs):
        self.calls.append(("list", kwargs))
        return {"ok": True, "active_session_key": "session-1", "sessions": []}

    def send_message(self, **kwargs):
        self.calls.append(("send", kwargs))
        return {"session_key": "session-1", "messages": [], "progress": {"running": True}}

    def reset_session(self, **kwargs):
        self.calls.append(("reset", kwargs))
        return {"session_key": "session-2", "messages": [], "progress": {"running": False}}

    def interrupt_session(self, **kwargs):
        self.calls.append(("interrupt", kwargs))
        return {"session_key": "session-1", "messages": [], "progress": {"running": True}}


class _HarnessService:
    def __init__(self) -> None:
        self.settings = type("Settings", (), {"service_host": "127.0.0.1", "service_port": 0})()

    def build_health_payload(self):
        return {"ok": True, "service": "hermes-browser-sidecar"}

    def build_capabilities_payload(self):
        return {"ok": True, "capabilities": {"session_send": True}}

    def get_session_state(self, *, client_session_id: str, session_key: str = ""):
        return {"ok": True, "session": {"session_id": client_session_id, "session_key": session_key or "state-1"}}

    def list_sessions(self, *, client_session_id: str, session_key: str = "", limit: int = 25):
        return {"ok": True, "sessions": [{"session_key": session_key or "state-1"}], "limit": limit}

    def send_message(self, *, client_session_id: str, session_key: str = "", message: str = "", page_context=None):
        return {
            "ok": True,
            "session": {
                "session_id": client_session_id,
                "session_key": session_key or "send-1",
                "echo": message,
                "page_context": page_context or {},
            },
        }

    def reset_session(self, *, client_session_id: str, session_key: str = ""):
        return {"ok": True, "session": {"session_id": client_session_id, "session_key": "reset-1"}}

    def interrupt_session(self, *, client_session_id: str, session_key: str = ""):
        return {"ok": True, "session": {"session_id": client_session_id, "session_key": session_key or "send-1"}}


class SidecarContractTests(unittest.TestCase):
    def test_settings_default_to_hybrid_mode(self) -> None:
        settings = SidecarSettings.from_env({})

        self.assertEqual(settings.transport, "hybrid")
        self.assertEqual(settings.browser_label, "Hermes Browser Sidecar")
        self.assertEqual(settings.service_base_url, "http://127.0.0.1:8787")
        self.assertEqual(settings.hermes_bridge_url, "http://127.0.0.1:8765/inject")
        self.assertEqual(settings.hermes_api_server_url, "http://127.0.0.1:8642/v1")

    def test_bridge_transport_resolves_bridge_endpoints(self) -> None:
        transport = HermesBridgeTransport(
            inject_url="http://127.0.0.1:8765/inject",
            token="test-token",
        )

        self.assertEqual(transport.health_url, "http://127.0.0.1:8765/health")
        self.assertEqual(transport.session_url, "http://127.0.0.1:8765/session")

    def test_bridge_transport_maps_send_to_browser_bridge_payload(self) -> None:
        class RecordingBridgeTransport(HermesBridgeTransport):
            def __init__(self):
                super().__init__(inject_url="http://127.0.0.1:8765/inject", token="test-token")
                self.recorded = None

            def _request_json(self, *, url, method, payload=None, timeout=30.0):
                self.recorded = {
                    "url": url,
                    "method": method,
                    "payload": payload,
                    "timeout": timeout,
                }
                return {"ok": True, "session_key": "session-1"}

        transport = RecordingBridgeTransport()
        transport.send_message(
            browser_label="Hermes Browser Sidecar",
            client_session_id="panel-123",
            session_key="session-1",
            message="Summarize this page",
            page_context={"title": "Example"},
        )

        self.assertEqual(transport.recorded["url"], "http://127.0.0.1:8765/session")
        self.assertEqual(transport.recorded["method"], "POST")
        self.assertEqual(
            transport.recorded["payload"],
            {
                "action": "send",
                "browserLabel": "Hermes Browser Sidecar",
                "clientSessionId": "panel-123",
                "sessionKey": "session-1",
                "message": "Summarize this page",
                "pageContext": {"title": "Example"},
            },
        )

    def test_service_uses_bridge_adapter_for_session_calls(self) -> None:
        service = SidecarService(SidecarSettings.from_env({}))
        fake_transport = _FakeBridgeTransport()
        service._select_transport = lambda: ("bridge", fake_transport)  # type: ignore[method-assign]

        result = service.send_message(
            client_session_id="panel-123",
            session_key="session-1",
            message="hello",
            page_context={"title": "Example"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["adapter"], "bridge")
        self.assertEqual(fake_transport.calls[0][0], "send")
        self.assertEqual(fake_transport.calls[0][1]["browser_label"], "Hermes Browser Sidecar")

    def test_extension_manifest_declares_chat_permissions(self) -> None:
        manifest_path = REPO_ROOT / "extension" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertIn("sidePanel", manifest["permissions"])
        self.assertIn("scripting", manifest["permissions"])
        self.assertIn("tabs", manifest["permissions"])
        self.assertIn("<all_urls>", manifest["host_permissions"])
        self.assertEqual(manifest["side_panel"]["default_path"], "sidepanel.html")


class SidecarServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _HarnessService()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _build_handler(self.service))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_get_session_state_endpoint(self) -> None:
        with urlopen(
            f"{self.base_url}/v1/session/state?client_session_id=panel-123&session_key=session-1"
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["session"]["session_id"], "panel-123")
        self.assertEqual(payload["session"]["session_key"], "session-1")

    def test_post_send_endpoint_accepts_page_context(self) -> None:
        request = Request(
            f"{self.base_url}/v1/session/send",
            method="POST",
            data=json.dumps(
                {
                    "client_session_id": "panel-123",
                    "session_key": "session-1",
                    "message": "hello",
                    "page_context": {"title": "Example"},
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["session"]["echo"], "hello")
        self.assertEqual(payload["session"]["page_context"]["title"], "Example")

    def test_post_send_requires_client_session_id(self) -> None:
        request = Request(
            f"{self.base_url}/v1/session/send",
            method="POST",
            data=json.dumps({"message": "hello"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        with self.assertRaises(Exception) as context:
            urlopen(request)

        self.assertIn("HTTP Error 400", str(context.exception))


if __name__ == "__main__":
    unittest.main()
