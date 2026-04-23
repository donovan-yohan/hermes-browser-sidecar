from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from hermes_browser_sidecar.errors import CODE_SESSION_NOT_FOUND, SidecarException
from hermes_browser_sidecar.protocol.types import (
    PageContext,
    SidecarMessage,
    SidecarProgress,
    SidecarSession,
)
from hermes_browser_sidecar.transports._http import HermesUpstreamError, request_json
from hermes_browser_sidecar.transports.base import BaseTransport, TransportProbe


# ASSUMPTION: Hermes API server speaks the OpenAI-compatible Responses API.
# Send: POST /responses {model, input, previous_response_id?} -> {id, output: [...]}.
# Get:  GET  /responses/{id} -> same shape as above.
# Cancel: DELETE /responses/{id} -> {id, status: "cancelled"}.
# Assistant text plucked defensively from output[0].content[0].text with
# empty-string fallback. See tests/fixtures/api_server_response.json.


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class _ApiSessionRecord:
    previous_response_id: str = ""
    messages: list[SidecarMessage] = field(default_factory=list)
    progress: SidecarProgress = field(default_factory=lambda: SidecarProgress(running=False))
    updated_at: str = field(default_factory=_utc_now_iso)


class HermesAPIServerTransport(BaseTransport):
    name = "api_server"
    supports_sessions = True
    supports_session_list = True
    supports_page_context = True

    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self._sessions: dict[str, _ApiSessionRecord] = {}

    @property
    def health_url(self) -> str:
        parsed = urlparse(self.base_url)
        return urlunparse(parsed._replace(path="/health", params="", query="", fragment=""))

    @property
    def responses_url(self) -> str:
        parsed = urlparse(self.base_url)
        path = parsed.path.rstrip("/") + "/responses"
        return urlunparse(parsed._replace(path=path, params="", query="", fragment=""))

    def _response_url(self, response_id: str) -> str:
        parsed = urlparse(self.base_url)
        path = parsed.path.rstrip("/") + f"/responses/{response_id}"
        return urlunparse(parsed._replace(path=path, params="", query="", fragment=""))

    def _auth_headers(self) -> dict[str, str]:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
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
                    detail="Hermes API server reachable.",
                    payload=payload if isinstance(payload, dict) else {},
                )
        except HTTPError as error:
            return TransportProbe(
                name=self.name,
                ok=False,
                endpoint=self.health_url,
                status_code=error.code,
                detail=f"Hermes API server returned HTTP {error.code}.",
                payload={},
            )
        except (OSError, URLError) as error:
            return TransportProbe(
                name=self.name,
                ok=False,
                endpoint=self.health_url,
                status_code=None,
                detail=f"Hermes API server probe failed: {error}",
                payload={},
            )

    def _build_input(
        self, *, message: str, page_context: PageContext | None
    ) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        if page_context is not None:
            preamble = (
                f"[page_context] title={page_context.title!r} "
                f"url={page_context.url!r} content_kind={page_context.content_kind!r}\n"
            )
            if page_context.selection:
                preamble += f"selection:\n{page_context.selection}\n"
            if page_context.page_text:
                preamble += f"page_text:\n{page_context.page_text}\n"
            items.append({"role": "user", "content": preamble})
        items.append({"role": "user", "content": message})
        return items

    @staticmethod
    def _extract_assistant_text(response: Mapping[str, object]) -> str:
        output = response.get("output")
        if not isinstance(output, list):
            return ""
        for item in output:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for chunk in content:
                if not isinstance(chunk, Mapping):
                    continue
                text = chunk.get("text")
                if isinstance(text, str) and text:
                    return text
        return ""

    def _session_to_public(
        self, session_id: str, record: _ApiSessionRecord
    ) -> SidecarSession:
        return SidecarSession(
            session_id=session_id,
            session_key=record.previous_response_id,
            messages=tuple(record.messages),
            progress=record.progress,
            updated_at=record.updated_at,
        )

    def get_session_state(
        self, *, session_id: str, session_key: str = ""
    ) -> SidecarSession:
        record = self._sessions.get(session_id)
        if record is None:
            return SidecarSession(
                session_id=session_id,
                session_key=session_key,
                messages=(),
                progress=SidecarProgress(running=False),
                updated_at=_utc_now_iso(),
            )
        if record.previous_response_id:
            try:
                response = request_json(
                    url=self._response_url(record.previous_response_id),
                    method="GET",
                    headers=self._auth_headers(),
                    timeout=15.0,
                )
                text = self._extract_assistant_text(response)
                if text and (not record.messages or record.messages[-1].content != text):
                    record.messages.append(
                        SidecarMessage(
                            role="assistant", content=text, timestamp=_utc_now_iso()
                        )
                    )
                    record.updated_at = _utc_now_iso()
            except HermesUpstreamError:
                # Fall back to local state — upstream re-fetch failed but we still
                # have a valid local snapshot.
                pass
        return self._session_to_public(session_id, record)

    def list_sessions(
        self,
        *,
        session_id: str,
        session_key: str = "",
        limit: int = 25,
    ) -> tuple[SidecarSession, ...]:
        items = list(self._sessions.items())
        items.sort(key=lambda kv: kv[1].updated_at, reverse=True)
        return tuple(
            self._session_to_public(sid, record) for sid, record in items[:limit]
        )

    def send_message(
        self,
        *,
        session_id: str,
        session_key: str = "",
        message: str = "",
        page_context: PageContext | None = None,
    ) -> SidecarSession:
        record = self._sessions.setdefault(session_id, _ApiSessionRecord())
        if session_key and not record.previous_response_id:
            record.previous_response_id = session_key

        payload: dict[str, object] = {
            "model": self.model,
            "input": self._build_input(message=message, page_context=page_context),
        }
        if record.previous_response_id:
            payload["previous_response_id"] = record.previous_response_id

        record.progress = SidecarProgress(running=True)
        try:
            response = request_json(
                url=self.responses_url,
                method="POST",
                headers=self._auth_headers(),
                payload=payload,
                timeout=300.0,
            )
        except HermesUpstreamError:
            record.progress = SidecarProgress(running=False)
            raise

        if page_context is not None:
            record.messages.append(
                SidecarMessage(
                    role="user",
                    content="[page context attached]",
                    timestamp=_utc_now_iso(),
                    kind="page_context",
                    metadata={"title": page_context.title, "url": page_context.url},
                )
            )
        record.messages.append(
            SidecarMessage(role="user", content=message, timestamp=_utc_now_iso())
        )
        new_id = response.get("id")
        if isinstance(new_id, str) and new_id:
            record.previous_response_id = new_id
        text = self._extract_assistant_text(response)
        record.messages.append(
            SidecarMessage(role="assistant", content=text, timestamp=_utc_now_iso())
        )
        record.progress = SidecarProgress(running=False)
        record.updated_at = _utc_now_iso()
        return self._session_to_public(session_id, record)

    def reset_session(
        self, *, session_id: str, session_key: str = ""
    ) -> SidecarSession:
        self._sessions.pop(session_id, None)
        fresh = _ApiSessionRecord()
        self._sessions[session_id] = fresh
        return self._session_to_public(session_id, fresh)

    def interrupt_session(
        self, *, session_id: str, session_key: str = ""
    ) -> SidecarSession:
        record = self._sessions.get(session_id)
        if record is None:
            raise SidecarException(
                CODE_SESSION_NOT_FOUND,
                f"No active session for session_id={session_id!r}.",
                http_status=404,
            )
        if record.previous_response_id:
            try:
                request_json(
                    url=self._response_url(record.previous_response_id),
                    method="DELETE",
                    headers=self._auth_headers(),
                    timeout=15.0,
                )
            except HermesUpstreamError:
                # DELETE may 404 if response already terminated — local state is
                # the source of truth for interrupt acknowledgment.
                pass
        record.progress = SidecarProgress(
            running=False, error=None, detail="interrupted"
        )
        record.updated_at = _utc_now_iso()
        return self._session_to_public(session_id, record)
