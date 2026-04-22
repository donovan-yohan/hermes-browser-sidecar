from __future__ import annotations

from hermes_browser_sidecar.config import SidecarSettings
from hermes_browser_sidecar.protocol import build_capabilities, build_health_payload
from hermes_browser_sidecar.server import run_server
from hermes_browser_sidecar.transports.api_server import HermesAPIServerTransport
from hermes_browser_sidecar.transports.base import BaseTransport
from hermes_browser_sidecar.transports.bridge import HermesBridgeTransport


class SidecarService:
    def __init__(self, settings: SidecarSettings) -> None:
        self.settings = settings

    def _select_transport(self) -> tuple[str, BaseTransport]:
        if self.settings.transport == "api_server":
            return (
                "api_server",
                HermesAPIServerTransport(
                    base_url=self.settings.hermes_api_server_url,
                    api_key=self.settings.hermes_api_server_key,
                ),
            )

        return (
            "bridge",
            HermesBridgeTransport(
                inject_url=self.settings.hermes_bridge_url,
                token=self.settings.hermes_bridge_token,
            ),
        )

    def build_health_payload(self) -> dict[str, object]:
        active_adapter, transport = self._select_transport()
        probe = transport.probe()
        return build_health_payload(
            settings=self.settings,
            active_adapter=active_adapter,
            probe=probe,
        )

    def build_capabilities_payload(self) -> dict[str, object]:
        return {
            "ok": True,
            "service": "hermes-browser-sidecar",
            "capabilities": build_capabilities(),
        }

    def serve(self) -> None:
        run_server(self)

