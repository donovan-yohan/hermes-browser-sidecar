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

        if self.settings.transport == "bridge":
            return (
                "bridge",
                HermesBridgeTransport(
                    inject_url=self.settings.hermes_bridge_url,
                    token=self.settings.hermes_bridge_token,
                ),
            )

        return (
            "bridge",
            HermesBridgeTransport(
                inject_url=self.settings.hermes_bridge_url,
                token=self.settings.hermes_bridge_token,
            ),
        )

    def _session_capabilities(self, transport: BaseTransport) -> dict[str, bool]:
        return build_capabilities(sessions_enabled=bool(getattr(transport, "supports_sessions", False)))

    def build_health_payload(self) -> dict[str, object]:
        active_adapter, transport = self._select_transport()
        probe = transport.probe()
        return build_health_payload(
            settings=self.settings,
            active_adapter=active_adapter,
            probe=probe,
            capabilities=self._session_capabilities(transport),
        )

    def build_capabilities_payload(self) -> dict[str, object]:
        active_adapter, transport = self._select_transport()
        return {
            "ok": True,
            "service": "hermes-browser-sidecar",
            "protocol_version": "0.2",
            "active_adapter": active_adapter,
            "capabilities": self._session_capabilities(transport),
        }

    def _bridge_session_transport(self) -> tuple[str, BaseTransport]:
        active_adapter, transport = self._select_transport()
        if not getattr(transport, "supports_sessions", False):
            raise NotImplementedError(
                f"Transport mode '{active_adapter}' does not expose sidecar session flows yet."
            )
        return active_adapter, transport

    def get_session_state(
        self,
        *,
        client_session_id: str,
        session_key: str = "",
    ) -> dict[str, object]:
        active_adapter, transport = self._bridge_session_transport()
        session = transport.get_session_state(
            browser_label=self.settings.browser_label,
            client_session_id=client_session_id,
            session_key=session_key,
        )
        return {"ok": True, "adapter": active_adapter, "session": session}

    def list_sessions(
        self,
        *,
        client_session_id: str,
        session_key: str = "",
        limit: int = 25,
    ) -> dict[str, object]:
        active_adapter, transport = self._bridge_session_transport()
        listing = transport.list_sessions(
            browser_label=self.settings.browser_label,
            client_session_id=client_session_id,
            session_key=session_key,
            limit=limit,
        )
        return {"ok": True, "adapter": active_adapter, **listing}

    def send_message(
        self,
        *,
        client_session_id: str,
        session_key: str = "",
        message: str = "",
        page_context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        active_adapter, transport = self._bridge_session_transport()
        session = transport.send_message(
            browser_label=self.settings.browser_label,
            client_session_id=client_session_id,
            session_key=session_key,
            message=message,
            page_context=page_context,
        )
        return {"ok": True, "adapter": active_adapter, "session": session}

    def reset_session(
        self,
        *,
        client_session_id: str,
        session_key: str = "",
    ) -> dict[str, object]:
        active_adapter, transport = self._bridge_session_transport()
        session = transport.reset_session(
            browser_label=self.settings.browser_label,
            client_session_id=client_session_id,
            session_key=session_key,
        )
        return {"ok": True, "adapter": active_adapter, "session": session}

    def interrupt_session(
        self,
        *,
        client_session_id: str,
        session_key: str = "",
    ) -> dict[str, object]:
        active_adapter, transport = self._bridge_session_transport()
        session = transport.interrupt_session(
            browser_label=self.settings.browser_label,
            client_session_id=client_session_id,
            session_key=session_key,
        )
        return {"ok": True, "adapter": active_adapter, "session": session}

    def serve(self) -> None:
        run_server(self)
