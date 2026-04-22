import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from hermes_browser_sidecar.config import SidecarSettings
from hermes_browser_sidecar.protocol import build_health_payload
from hermes_browser_sidecar.transports.base import TransportProbe
from hermes_browser_sidecar.transports.bridge import HermesBridgeTransport


class ScaffoldContractTests(unittest.TestCase):
    def test_settings_default_to_hybrid_mode(self) -> None:
        settings = SidecarSettings.from_env({})

        self.assertEqual(settings.transport, "hybrid")
        self.assertEqual(settings.service_base_url, "http://127.0.0.1:8787")
        self.assertEqual(settings.hermes_bridge_url, "http://127.0.0.1:8765/inject")
        self.assertEqual(settings.hermes_api_server_url, "http://127.0.0.1:8642/v1")

    def test_bridge_transport_resolves_health_endpoint_from_inject_url(self) -> None:
        transport = HermesBridgeTransport(
            inject_url="http://127.0.0.1:8765/inject",
            token="test-token",
        )

        self.assertEqual(transport.health_url, "http://127.0.0.1:8765/health")

    def test_health_payload_declares_scaffold_capabilities(self) -> None:
        settings = SidecarSettings.from_env({})
        probe = TransportProbe(
            name="bridge",
            ok=True,
            endpoint="http://127.0.0.1:8765/health",
            status_code=200,
            detail="reachable",
            payload={"service": "hermes-browser-bridge"},
        )

        payload = build_health_payload(settings=settings, active_adapter="bridge", probe=probe)

        self.assertEqual(payload["transport"]["mode"], "hybrid")
        self.assertEqual(payload["transport"]["active_adapter"], "bridge")
        self.assertTrue(payload["capabilities"]["health_check"])
        self.assertTrue(payload["capabilities"]["capability_discovery"])
        self.assertFalse(payload["capabilities"]["session_send"])
        self.assertFalse(payload["capabilities"]["session_interrupt"])

    def test_extension_manifest_declares_side_panel_shell(self) -> None:
        manifest_path = REPO_ROOT / "extension" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertIn("sidePanel", manifest["permissions"])
        self.assertEqual(manifest["side_panel"]["default_path"], "sidepanel.html")
        self.assertIn("http://127.0.0.1/*", manifest["host_permissions"])


if __name__ == "__main__":
    unittest.main()
