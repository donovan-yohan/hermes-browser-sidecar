from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from hermes_browser_sidecar.protocol.types import (
    PageContext,
    SidecarMessage,
    SidecarProgress,
    SidecarSession,
)
from hermes_browser_sidecar.transports._http import HermesUpstreamError, request_json
from hermes_browser_sidecar.transports.base import BaseTransport, TransportProbe


# CAPTURED FROM HERMES BRIDGE — VERIFY AGAINST gateway/browser_bridge.py.
# Bridge POST /session response shape (best-effort observation):
#   {"ok": True, "session_key": "<opaque>",
#    "messages": [{"role": "...", "content": "...", "timestamp": "...", "kind": "..."}],
#    "progress": {"running": bool, "error": str|null, "detail": str},
#    "sessions": [...]   # only for action=list
#   }
# All bridge field names are camelCase on the request side, snake_case on the
# response side (per existing fixture). Adapter normalizes both directions.


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class HermesBridgeTransport(BaseTransport):
    name = "bridge"
    supports_sessions = True
    supports_session_list = True
    supports_page_context = True

    def __init__(self, *, inject_url: str, token: str, browser_label: str) -> None:
        self.inject_url = inject_url
        self.token = token
        self.browser_label = browser_label

    @property
    def health_url(self) -> str:
        parsed = urlparse(self.inject_url)
        return urlunparse(parsed._replace(path="/health", params="", query="", fragment=""))

    @property
    def session_url(self) -> str:
        parsed = urlparse(self.inject_url)
        return urlunparse(parsed._replace(path="/session", params="", query="", fragment=""))

    def _auth_headers(self) -> dict[str, str]:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    def probe(self) -> TransportProbe:
        request = Request(self.health_url, headers=self._auth_headers(), method="GET")
        try:
            with urlopen(request, timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8") or "{}")
                return TransportProbe(
                    name=self.name,
                    ok=200 <= response.status < 300,
                    endpoint=self.health_url,
                    status_code=response.status,
                    detail="Hermes browser bridge reachable.",
                    payload=payload if isinstance(payload, dict) else {},
                )
        except HTTPError as error:
            return TransportProbe(
                name=self.name,
                ok=False,
                endpoint=self.health_url,
                status_code=error.code,
                detail=f"Hermes browser bridge returned HTTP {error.code}.",
                payload={},
            )
        except (OSError, URLError) as error:
            return TransportProbe(
                name=self.name,
                ok=False,
                endpoint=self.health_url,
                status_code=None,
                detail=f"Hermes browser bridge probe failed: {error}",
                payload={},
            )

    def _bridge_payload(
        self,
        *,
        action: str,
        session_id: str,
        session_key: str = "",
        limit: int | None = None,
        message: str = "",
        page_context: PageContext | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "action": action,
            "browserLabel": self.browser_label,
            "clientSessionId": session_id,
        }
        if session_key:
            payload["sessionKey"] = session_key
        if limit is not None:
            payload["limit"] = limit
        if message:
            payload["message"] = message
        if page_context is not None:
            payload["pageContext"] = {
                "title": page_context.title,
                "url": page_context.url,
                "selection": page_context.selection,
                "pageText": page_context.page_text,
                "contentKind": page_context.content_kind,
                "metadata": dict(page_context.metadata),
            }
        return payload

    def _post_session(
        self, payload: Mapping[str, object], *, timeout: float = 30.0
    ) -> dict[str, object]:
        return request_json(
            url=self.session_url,
            method="POST",
            headers=self._auth_headers(),
            payload=payload,
            timeout=timeout,
        )

    @staticmethod
    def _normalize_progress(raw: object) -> SidecarProgress:
        if not isinstance(raw, Mapping):
            return SidecarProgress(running=False)
        running = bool(raw.get("running", False))
        error = raw.get("error")
        if error is not None and not isinstance(error, str):
            error = str(error)
        detail = raw.get("detail", "")
        if not isinstance(detail, str):
            detail = str(detail)
        return SidecarProgress(running=running, error=error, detail=detail)

    @staticmethod
    def _normalize_message(raw: object) -> SidecarMessage:
        if not isinstance(raw, Mapping):
            return SidecarMessage(role="assistant", content="", timestamp=_utc_now_iso())
        role = str(raw.get("role", "assistant"))
        content = raw.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        timestamp = raw.get("timestamp")
        if not isinstance(timestamp, str) or not timestamp:
            timestamp = _utc_now_iso()
        kind = raw.get("kind", "text")
        if not isinstance(kind, str):
            kind = "text"
        metadata_raw = raw.get("metadata")
        metadata = dict(metadata_raw) if isinstance(metadata_raw, Mapping) else None
        return SidecarMessage(
            role=role, content=content, timestamp=timestamp, kind=kind, metadata=metadata
        )

    def _normalize_session(
        self, *, session_id: str, raw: Mapping[str, object]
    ) -> SidecarSession:
        session_key = raw.get("session_key") or raw.get("sessionKey") or ""
        if not isinstance(session_key, str):
            session_key = str(session_key)
        raw_messages = raw.get("messages") or []
        if not isinstance(raw_messages, list):
            raw_messages = []
        progress = self._normalize_progress(raw.get("progress"))
        updated_at = raw.get("updated_at") or raw.get("updatedAt") or _utc_now_iso()
        if not isinstance(updated_at, str):
            updated_at = _utc_now_iso()
        return SidecarSession(
            session_id=session_id,
            session_key=session_key,
            messages=tuple(self._normalize_message(m) for m in raw_messages),
            progress=progress,
            updated_at=updated_at,
        )

    def _extract_session_dict(self, response: Mapping[str, object]) -> Mapping[str, object]:
        session = response.get("session")
        if isinstance(session, Mapping):
            return session
        return response

    def get_session_state(
        self, *, session_id: str, session_key: str = ""
    ) -> SidecarSession:
        response = self._post_session(
            self._bridge_payload(
                action="state", session_id=session_id, session_key=session_key
            )
        )
        return self._normalize_session(
            session_id=session_id, raw=self._extract_session_dict(response)
        )

    def list_sessions(
        self,
        *,
        session_id: str,
        session_key: str = "",
        limit: int = 25,
    ) -> tuple[SidecarSession, ...]:
        response = self._post_session(
            self._bridge_payload(
                action="list",
                session_id=session_id,
                session_key=session_key,
                limit=limit,
            )
        )
        raw_sessions = response.get("sessions")
        if not isinstance(raw_sessions, list):
            raw_sessions = []
        out: list[SidecarSession] = []
        for entry in raw_sessions:
            if not isinstance(entry, Mapping):
                continue
            entry_id = entry.get("session_id") or entry.get("clientSessionId") or session_id
            if not isinstance(entry_id, str):
                entry_id = session_id
            out.append(self._normalize_session(session_id=entry_id, raw=entry))
        return tuple(out)

    def send_message(
        self,
        *,
        session_id: str,
        session_key: str = "",
        message: str = "",
        page_context: PageContext | None = None,
    ) -> SidecarSession:
        response = self._post_session(
            self._bridge_payload(
                action="send",
                session_id=session_id,
                session_key=session_key,
                message=message,
                page_context=page_context,
            ),
            timeout=300.0,
        )
        return self._normalize_session(
            session_id=session_id, raw=self._extract_session_dict(response)
        )

    def reset_session(
        self, *, session_id: str, session_key: str = ""
    ) -> SidecarSession:
        response = self._post_session(
            self._bridge_payload(
                action="reset", session_id=session_id, session_key=session_key
            )
        )
        return self._normalize_session(
            session_id=session_id, raw=self._extract_session_dict(response)
        )

    def interrupt_session(
        self, *, session_id: str, session_key: str = ""
    ) -> SidecarSession:
        response = self._post_session(
            self._bridge_payload(
                action="interrupt", session_id=session_id, session_key=session_key
            )
        )
        return self._normalize_session(
            session_id=session_id, raw=self._extract_session_dict(response)
        )
