from __future__ import annotations

import time

from hermes_browser_sidecar.config import SidecarSettings
from hermes_browser_sidecar.errors import (
    CODE_INVALID_REQUEST,
    CODE_UPSTREAM_ERROR,
    CODE_UPSTREAM_UNAVAILABLE,
    SidecarException,
)
from hermes_browser_sidecar.protocol import (
    Capabilities,
    PageContext,
    build_capabilities_payload,
    build_health_payload,
)
from hermes_browser_sidecar.server import run_server
from hermes_browser_sidecar.transports._http import HermesUpstreamError
from hermes_browser_sidecar.transports.api_server import HermesAPIServerTransport
from hermes_browser_sidecar.transports.base import BaseTransport, TransportProbe
from hermes_browser_sidecar.transports.bridge import HermesBridgeTransport


class SidecarService:
    _PROBE_TTL = 5.0

    def __init__(self, settings: SidecarSettings) -> None:
        self.settings = settings
        self._bridge: HermesBridgeTransport | None = None
        self._api_server: HermesAPIServerTransport | None = None
        self._probe_cache: dict[str, tuple[TransportProbe, float]] = {}

    def _build_bridge(self) -> HermesBridgeTransport:
        if self._bridge is None:
            self._bridge = HermesBridgeTransport(
                inject_url=self.settings.hermes_bridge_url,
                token=self.settings.hermes_bridge_token,
                browser_label=self.settings.browser_label,
            )
        return self._bridge

    def _build_api_server(self) -> HermesAPIServerTransport:
        if self._api_server is None:
            self._api_server = HermesAPIServerTransport(
                base_url=self.settings.hermes_api_server_url,
                api_key=self.settings.hermes_api_server_key,
                model=self.settings.api_server_model,
            )
        return self._api_server

    def _cached_probe(self, transport: BaseTransport) -> TransportProbe:
        now = time.monotonic()
        key = id(transport)
        cached = self._probe_cache.get(key)
        if cached is not None:
            probe, ts = cached
            if now - ts < self._PROBE_TTL:
                return probe
        probe = transport.probe()
        self._probe_cache[key] = (probe, now)
        return probe

    def _select_transport(self) -> tuple[str, BaseTransport, BaseTransport | None]:
        mode = self.settings.transport
        if mode == "bridge":
            return ("bridge", self._build_bridge(), None)
        if mode == "api_server":
            return ("api_server", self._build_api_server(), None)
        bridge = self._build_bridge()
        api_server = self._build_api_server()
        probe = self._cached_probe(bridge)
        if probe.ok:
            return ("bridge", bridge, api_server)
        api_probe = self._cached_probe(api_server)
        if api_probe.ok:
            return ("api_server", api_server, bridge)
        return ("bridge", bridge, api_server)

    def _compute_capabilities(
        self, active: BaseTransport, fallback: BaseTransport | None
    ) -> Capabilities:
        if fallback is None:
            return active.capabilities()
        fallback_probe = self._cached_probe(fallback)
        if not fallback_probe.ok:
            return active.capabilities()
        return Capabilities.union(active.capabilities(), fallback.capabilities())

    def _active(self) -> tuple[str, BaseTransport, BaseTransport | None, TransportProbe]:
        name, transport, fallback = self._select_transport()
        return name, transport, fallback, self._cached_probe(transport)

    def build_health_payload(self) -> dict[str, object]:
        name, transport, fallback, probe = self._active()
        capabilities = self._compute_capabilities(transport, fallback)
        notes: list[str] = []
        if not probe.ok:
            notes.append("Active upstream is not reachable; session calls will return 502.")
        notes.append(
            "Local sidecar service has no authentication; bind to 127.0.0.1 only."
        )
        return build_health_payload(
            settings=self.settings,
            active_adapter=name,
            probe=probe,
            capabilities=capabilities,
            notes=notes,
        )

    def build_capabilities_payload(self) -> dict[str, object]:
        _name, transport, fallback = self._select_transport()
        capabilities = self._compute_capabilities(transport, fallback)
        return build_capabilities_payload(capabilities)

    def _wrap_upstream(self, error: HermesUpstreamError) -> SidecarException:
        code = (
            CODE_UPSTREAM_UNAVAILABLE
            if error.status_code is None
            else CODE_UPSTREAM_ERROR
        )
        detail: dict[str, object] = {"status_code": error.status_code}
        if error.payload is not None:
            detail["upstream_payload"] = error.payload
        return SidecarException(code, error.detail, detail=detail, http_status=502)

    def _require_session_id(self, session_id: str) -> None:
        if not session_id:
            raise SidecarException(
                CODE_INVALID_REQUEST,
                "Missing required field: session_id",
                detail={"missing": ["session_id"]},
                http_status=400,
            )

    def get_session_state(
        self, *, session_id: str, session_key: str = ""
    ) -> dict[str, object]:
        self._require_session_id(session_id)
        _, transport, _ = self._select_transport()
        try:
            session = transport.get_session_state(
                session_id=session_id, session_key=session_key
            )
        except HermesUpstreamError as error:
            raise self._wrap_upstream(error) from error
        return {"ok": True, "session": session.to_dict()}

    def list_sessions(
        self,
        *,
        session_id: str,
        session_key: str = "",
        limit: int = 25,
    ) -> dict[str, object]:
        self._require_session_id(session_id)
        _, transport, _ = self._select_transport()
        try:
            sessions = transport.list_sessions(
                session_id=session_id, session_key=session_key, limit=limit
            )
        except HermesUpstreamError as error:
            raise self._wrap_upstream(error) from error
        return {"ok": True, "sessions": [s.to_dict() for s in sessions], "limit": limit}

    def send_message(
        self,
        *,
        session_id: str,
        session_key: str = "",
        message: str = "",
        page_context: PageContext | None = None,
    ) -> dict[str, object]:
        self._require_session_id(session_id)
        if not message and page_context is None:
            raise SidecarException(
                CODE_INVALID_REQUEST,
                "Either message or page_context must be provided",
                detail={"missing": ["message"]},
                http_status=400,
            )
        _, transport, _ = self._select_transport()
        try:
            session = transport.send_message(
                session_id=session_id,
                session_key=session_key,
                message=message,
                page_context=page_context,
            )
        except HermesUpstreamError as error:
            raise self._wrap_upstream(error) from error
        return {"ok": True, "session": session.to_dict()}

    def reset_session(
        self, *, session_id: str, session_key: str = ""
    ) -> dict[str, object]:
        self._require_session_id(session_id)
        _, transport, _ = self._select_transport()
        try:
            session = transport.reset_session(
                session_id=session_id, session_key=session_key
            )
        except HermesUpstreamError as error:
            raise self._wrap_upstream(error) from error
        return {"ok": True, "session": session.to_dict()}

    def interrupt_session(
        self, *, session_id: str, session_key: str = ""
    ) -> dict[str, object]:
        self._require_session_id(session_id)
        _, transport, _ = self._select_transport()
        try:
            session = transport.interrupt_session(
                session_id=session_id, session_key=session_key
            )
        except HermesUpstreamError as error:
            raise self._wrap_upstream(error) from error
        return {"ok": True, "session": session.to_dict()}

    def serve(self) -> None:
        run_server(self)
