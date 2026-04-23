from __future__ import annotations

from dataclasses import dataclass

from hermes_browser_sidecar.errors import CODE_NOT_SUPPORTED, SidecarException
from hermes_browser_sidecar.protocol.types import (
    Capabilities,
    PageContext,
    SidecarSession,
)


@dataclass(frozen=True)
class TransportProbe:
    name: str
    ok: bool
    endpoint: str
    status_code: int | None
    detail: str
    payload: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "endpoint": self.endpoint,
            "status_code": self.status_code,
            "detail": self.detail,
            "payload": self.payload or {},
        }


class BaseTransport:
    name: str = "base"
    supports_sessions: bool = False
    supports_session_list: bool = False
    supports_page_context: bool = False
    supports_attachments: bool = False
    supports_tts: bool = False
    supports_stt: bool = False

    def probe(self) -> TransportProbe:
        raise NotImplementedError

    def capabilities(self) -> Capabilities:
        return Capabilities(
            health_check=True,
            capability_discovery=True,
            session_state=self.supports_sessions,
            session_list=self.supports_session_list,
            session_send=self.supports_sessions,
            session_reset=self.supports_sessions,
            session_interrupt=self.supports_sessions,
            page_context=self.supports_page_context,
            attachments=self.supports_attachments,
            tts=self.supports_tts,
            stt=self.supports_stt,
        )

    def get_session_state(
        self, *, session_id: str, session_key: str = ""
    ) -> SidecarSession:
        raise SidecarException(
            CODE_NOT_SUPPORTED,
            f"Transport '{self.name}' does not support session_state.",
            http_status=501,
        )

    def list_sessions(
        self,
        *,
        session_id: str,
        session_key: str = "",
        limit: int = 25,
    ) -> tuple[SidecarSession, ...]:
        raise SidecarException(
            CODE_NOT_SUPPORTED,
            f"Transport '{self.name}' does not support session_list.",
            http_status=501,
        )

    def send_message(
        self,
        *,
        session_id: str,
        session_key: str = "",
        message: str = "",
        page_context: PageContext | None = None,
    ) -> SidecarSession:
        raise SidecarException(
            CODE_NOT_SUPPORTED,
            f"Transport '{self.name}' does not support session_send.",
            http_status=501,
        )

    def reset_session(
        self, *, session_id: str, session_key: str = ""
    ) -> SidecarSession:
        raise SidecarException(
            CODE_NOT_SUPPORTED,
            f"Transport '{self.name}' does not support session_reset.",
            http_status=501,
        )

    def interrupt_session(
        self, *, session_id: str, session_key: str = ""
    ) -> SidecarSession:
        raise SidecarException(
            CODE_NOT_SUPPORTED,
            f"Transport '{self.name}' does not support session_interrupt.",
            http_status=501,
        )
