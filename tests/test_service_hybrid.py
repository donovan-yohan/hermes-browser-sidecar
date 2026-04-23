import unittest

from tests._fakes import FakeTransport  # noqa: F401  (path setup)

from hermes_browser_sidecar.config import SidecarSettings
from hermes_browser_sidecar.service import SidecarService


def _settings(transport: str = "hybrid") -> SidecarSettings:
    return SidecarSettings.from_env({"HERMES_SIDECAR_TRANSPORT": transport})


class SelectionTests(unittest.TestCase):
    def test_bridge_only_skips_api_server(self) -> None:
        service = SidecarService(_settings("bridge"))
        bridge = FakeTransport(probe_ok=True)
        api = FakeTransport(probe_ok=True)
        service._bridge = bridge  # type: ignore[assignment]
        service._api_server = api  # type: ignore[assignment]
        name, active, fallback = service._select_transport()
        self.assertEqual(name, "bridge")
        self.assertIs(active, bridge)
        self.assertIsNone(fallback)

    def test_api_server_only_skips_bridge(self) -> None:
        service = SidecarService(_settings("api_server"))
        bridge = FakeTransport(probe_ok=False)
        api = FakeTransport(probe_ok=True)
        service._bridge = bridge  # type: ignore[assignment]
        service._api_server = api  # type: ignore[assignment]
        name, active, fallback = service._select_transport()
        self.assertEqual(name, "api_server")
        self.assertIs(active, api)
        self.assertIsNone(fallback)

    def test_hybrid_prefers_bridge_when_probe_ok(self) -> None:
        service = SidecarService(_settings("hybrid"))
        bridge = FakeTransport(probe_ok=True)
        api = FakeTransport(probe_ok=True)
        service._bridge = bridge  # type: ignore[assignment]
        service._api_server = api  # type: ignore[assignment]
        name, active, fallback = service._select_transport()
        self.assertEqual(name, "bridge")
        self.assertIs(active, bridge)
        self.assertIs(fallback, api)

    def test_hybrid_falls_back_to_api_server_when_bridge_down(self) -> None:
        service = SidecarService(_settings("hybrid"))
        bridge = FakeTransport(probe_ok=False)
        api = FakeTransport(probe_ok=True)
        service._bridge = bridge  # type: ignore[assignment]
        service._api_server = api  # type: ignore[assignment]
        name, active, fallback = service._select_transport()
        self.assertEqual(name, "api_server")
        self.assertIs(active, api)
        self.assertIs(fallback, bridge)


class CapabilitiesTests(unittest.TestCase):
    def test_capabilities_payload_uses_protocol_version(self) -> None:
        service = SidecarService(_settings("hybrid"))
        service._bridge = FakeTransport(probe_ok=True)  # type: ignore[assignment]
        service._api_server = FakeTransport(probe_ok=True)  # type: ignore[assignment]
        payload = service.build_capabilities_payload()
        self.assertEqual(payload["service"], "hermes-browser-sidecar")
        self.assertEqual(payload["protocol_version"], "1.0")
        capabilities = payload["capabilities"]
        self.assertTrue(capabilities["session_send"])
        self.assertTrue(capabilities["page_context"])

    def test_health_payload_includes_no_auth_note(self) -> None:
        service = SidecarService(_settings("bridge"))
        service._bridge = FakeTransport(probe_ok=True)  # type: ignore[assignment]
        payload = service.build_health_payload()
        self.assertEqual(payload["protocol_version"], "1.0")
        self.assertEqual(payload["transport"]["mode"], "bridge")
        self.assertEqual(payload["transport"]["active_adapter"], "bridge")
        self.assertTrue(any("no authentication" in n for n in payload["notes"]))


class RoutingTests(unittest.TestCase):
    def test_send_message_requires_session_id(self) -> None:
        from hermes_browser_sidecar.errors import SidecarException
        service = SidecarService(_settings("bridge"))
        service._bridge = FakeTransport(probe_ok=True)  # type: ignore[assignment]
        with self.assertRaises(SidecarException) as ctx:
            service.send_message(session_id="", message="hi")
        self.assertEqual(ctx.exception.http_status, 400)

    def test_send_message_returns_session_dict(self) -> None:
        service = SidecarService(_settings("bridge"))
        fake = FakeTransport(probe_ok=True)
        service._bridge = fake  # type: ignore[assignment]
        result = service.send_message(session_id="panel-1", message="hi")
        self.assertTrue(result["ok"])
        self.assertEqual(result["session"]["session_id"], "panel-1")
        self.assertIn(("send_message", {"session_id": "panel-1", "session_key": "", "message": "hi", "page_context": None}), fake.calls)


if __name__ == "__main__":
    unittest.main()
