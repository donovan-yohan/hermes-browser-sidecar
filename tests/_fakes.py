from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))


from hermes_browser_sidecar.protocol.types import (  # noqa: E402  (path setup above)
    Capabilities,
    PageContext,
    SidecarMessage,
    SidecarProgress,
    SidecarSession,
)
from hermes_browser_sidecar.transports.base import BaseTransport, TransportProbe  # noqa: E402


HandlerFn = Callable[[str, str, dict, bytes], tuple[int, dict]]


class FakeUpstreamServer:
    """Tiny stdlib HTTP server that records and replies based on a handler.

    Use as a context manager:
        with FakeUpstreamServer(handler) as srv:
            srv.url -> "http://127.0.0.1:<port>"
    """

    def __init__(self, handler: HandlerFn) -> None:
        self._handler = handler
        self.requests: list[dict[str, Any]] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def __enter__(self) -> "FakeUpstreamServer":
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

            def _serve(self, method: str) -> None:
                length = int(self.headers.get("Content-Length", "0") or 0)
                body = self.rfile.read(length) if length > 0 else b""
                headers = {k: v for k, v in self.headers.items()}
                outer.requests.append(
                    {
                        "method": method,
                        "path": self.path,
                        "headers": headers,
                        "body": body,
                    }
                )
                status, payload = outer._handler(method, self.path, headers, body)
                raw = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:  # noqa: N802
                self._serve("GET")

            def do_POST(self) -> None:  # noqa: N802
                self._serve("POST")

            def do_DELETE(self) -> None:  # noqa: N802
                self._serve("DELETE")

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()
        return self

    def __exit__(self, *_args) -> None:
        assert self._server is not None
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


class FakeTransport(BaseTransport):
    name = "fake"
    supports_sessions = True
    supports_session_list = True
    supports_page_context = True

    def __init__(
        self,
        *,
        probe_ok: bool = True,
        sessions: tuple[SidecarSession, ...] | None = None,
    ) -> None:
        self.probe_ok = probe_ok
        self.calls: list[tuple[str, dict]] = []
        self._fixture_session = SidecarSession(
            session_id="fake",
            session_key="fk-key",
            messages=(SidecarMessage(role="assistant", content="ok", timestamp="t"),),
            progress=SidecarProgress(running=False),
            updated_at="t",
        )
        self._sessions = sessions or (self._fixture_session,)

    def probe(self) -> TransportProbe:
        return TransportProbe(
            name=self.name,
            ok=self.probe_ok,
            endpoint="fake://probe",
            status_code=200 if self.probe_ok else None,
            detail="fake",
            payload={},
        )

    def get_session_state(self, *, session_id, session_key=""):
        self.calls.append(("get_session_state", {"session_id": session_id, "session_key": session_key}))
        return SidecarSession(
            session_id=session_id,
            session_key=session_key or "fk-key",
            messages=self._fixture_session.messages,
            progress=self._fixture_session.progress,
            updated_at=self._fixture_session.updated_at,
        )

    def list_sessions(self, *, session_id, session_key="", limit=25):
        self.calls.append(("list_sessions", {"session_id": session_id, "session_key": session_key, "limit": limit}))
        return self._sessions[:limit]

    def send_message(self, *, session_id, session_key="", message="", page_context=None):
        self.calls.append(
            (
                "send_message",
                {
                    "session_id": session_id,
                    "session_key": session_key,
                    "message": message,
                    "page_context": page_context.to_dict() if page_context else None,
                },
            )
        )
        return self.get_session_state(session_id=session_id, session_key=session_key)

    def reset_session(self, *, session_id, session_key=""):
        self.calls.append(("reset_session", {"session_id": session_id, "session_key": session_key}))
        return self.get_session_state(session_id=session_id, session_key=session_key)

    def interrupt_session(self, *, session_id, session_key=""):
        self.calls.append(("interrupt_session", {"session_id": session_id, "session_key": session_key}))
        return self.get_session_state(session_id=session_id, session_key=session_key)


class FakeService:
    """Imitates SidecarService surface for server-route tests."""

    def __init__(self, *, settings, transport: FakeTransport, raise_on: str | None = None) -> None:
        self.settings = settings
        self._transport = transport
        self._raise_on = raise_on
        self._capabilities = transport.capabilities()

    def _maybe_raise(self, op: str) -> None:
        if self._raise_on == op:
            from hermes_browser_sidecar.errors import (
                CODE_NOT_SUPPORTED,
                SidecarException,
            )
            raise SidecarException(CODE_NOT_SUPPORTED, f"forced {op}", http_status=501)

    def build_health_payload(self) -> dict:
        from hermes_browser_sidecar.protocol import build_health_payload
        return build_health_payload(
            settings=self.settings,
            active_adapter=self._transport.name,
            probe=self._transport.probe(),
            capabilities=self._capabilities,
            notes=["fake"],
        )

    def build_capabilities_payload(self) -> dict:
        from hermes_browser_sidecar.protocol import build_capabilities_payload
        return build_capabilities_payload(self._capabilities)

    def get_session_state(self, *, session_id, session_key=""):
        from hermes_browser_sidecar.errors import CODE_INVALID_REQUEST, SidecarException
        if not session_id:
            raise SidecarException(CODE_INVALID_REQUEST, "Missing session_id", http_status=400)
        self._maybe_raise("get_session_state")
        return {"ok": True, "session": self._transport.get_session_state(session_id=session_id, session_key=session_key).to_dict()}

    def list_sessions(self, *, session_id, session_key="", limit=25):
        from hermes_browser_sidecar.errors import CODE_INVALID_REQUEST, SidecarException
        if not session_id:
            raise SidecarException(CODE_INVALID_REQUEST, "Missing session_id", http_status=400)
        self._maybe_raise("list_sessions")
        sessions = self._transport.list_sessions(session_id=session_id, session_key=session_key, limit=limit)
        return {"ok": True, "sessions": [s.to_dict() for s in sessions], "limit": limit}

    def send_message(self, *, session_id, session_key="", message="", page_context=None):
        from hermes_browser_sidecar.errors import CODE_INVALID_REQUEST, SidecarException
        if not session_id:
            raise SidecarException(CODE_INVALID_REQUEST, "Missing session_id", http_status=400)
        if not message and page_context is None:
            raise SidecarException(CODE_INVALID_REQUEST, "Missing message", http_status=400)
        self._maybe_raise("send_message")
        return {"ok": True, "session": self._transport.send_message(session_id=session_id, session_key=session_key, message=message, page_context=page_context).to_dict()}

    def reset_session(self, *, session_id, session_key=""):
        from hermes_browser_sidecar.errors import CODE_INVALID_REQUEST, SidecarException
        if not session_id:
            raise SidecarException(CODE_INVALID_REQUEST, "Missing session_id", http_status=400)
        self._maybe_raise("reset_session")
        return {"ok": True, "session": self._transport.reset_session(session_id=session_id, session_key=session_key).to_dict()}

    def interrupt_session(self, *, session_id, session_key=""):
        from hermes_browser_sidecar.errors import CODE_INVALID_REQUEST, SidecarException
        if not session_id:
            raise SidecarException(CODE_INVALID_REQUEST, "Missing session_id", http_status=400)
        self._maybe_raise("interrupt_session")
        return {"ok": True, "session": self._transport.interrupt_session(session_id=session_id, session_key=session_key).to_dict()}


__all__ = [
    "Capabilities",
    "FakeService",
    "FakeTransport",
    "FakeUpstreamServer",
    "PageContext",
    "REPO_ROOT",
    "SidecarMessage",
    "SidecarProgress",
    "SidecarSession",
]
