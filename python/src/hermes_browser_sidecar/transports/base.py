from __future__ import annotations

from dataclasses import dataclass


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
    name = "base"
    supports_sessions = False

    def probe(self) -> TransportProbe:
        raise NotImplementedError

    def get_session_state(
        self,
        *,
        browser_label: str,
        client_session_id: str,
        session_key: str = "",
    ) -> dict[str, object]:
        raise NotImplementedError

    def list_sessions(
        self,
        *,
        browser_label: str,
        client_session_id: str,
        session_key: str = "",
        limit: int = 25,
    ) -> dict[str, object]:
        raise NotImplementedError

    def send_message(
        self,
        *,
        browser_label: str,
        client_session_id: str,
        session_key: str = "",
        message: str = "",
        page_context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        raise NotImplementedError

    def reset_session(
        self,
        *,
        browser_label: str,
        client_session_id: str,
        session_key: str = "",
    ) -> dict[str, object]:
        raise NotImplementedError

    def interrupt_session(
        self,
        *,
        browser_label: str,
        client_session_id: str,
        session_key: str = "",
    ) -> dict[str, object]:
        raise NotImplementedError
