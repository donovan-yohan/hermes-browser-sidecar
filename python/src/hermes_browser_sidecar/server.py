from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Mapping
from urllib.parse import parse_qs, urlparse

from hermes_browser_sidecar.errors import (
    CODE_INTERNAL_ERROR,
    CODE_INVALID_REQUEST,
    SidecarException,
)
from hermes_browser_sidecar.protocol.types import PageContext


_CHROME_EXTENSION_ORIGIN = re.compile(r"^chrome-extension://[A-Za-z0-9_-]+$")
_CORS_METHODS = "GET, POST, OPTIONS"
_CORS_HEADERS = "Content-Type, Authorization"
_CORS_MAX_AGE = "600"


def run_server(service) -> None:
    handler_class = _build_handler(service)
    server = ThreadingHTTPServer(
        (service.settings.service_host, service.settings.service_port),
        handler_class,
    )
    print(
        f"hermes-browser-sidecar listening on "
        f"http://{service.settings.service_host}:{service.settings.service_port}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _build_handler(service):
    class SidecarHandler(BaseHTTPRequestHandler):
        server_version = "HermesBrowserSidecar/1.0"

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._cors_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def _cors_headers(self) -> None:
            origin = self.headers.get("Origin", "")
            if origin and _CHROME_EXTENSION_ORIGIN.match(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", _CORS_METHODS)
                self.send_header("Access-Control-Allow-Headers", _CORS_HEADERS)
                self.send_header("Access-Control-Max-Age", _CORS_MAX_AGE)

        def _json_response(self, status: int, payload: Mapping[str, object]) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)

        def _error_response(self, exc: SidecarException) -> None:
            self._json_response(exc.http_status, {"ok": False, "error": exc.to_dict()})

        def _read_body(self) -> Mapping[str, object]:
            length_header = self.headers.get("Content-Length", "0")
            try:
                length = int(length_header)
            except ValueError as error:
                raise SidecarException(
                    CODE_INVALID_REQUEST,
                    "Invalid Content-Length header",
                    http_status=400,
                ) from error
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise SidecarException(
                    CODE_INVALID_REQUEST,
                    "Request body must be valid JSON",
                    detail={"parse_error": str(error)},
                    http_status=400,
                ) from error
            if not isinstance(data, Mapping):
                raise SidecarException(
                    CODE_INVALID_REQUEST,
                    "Request body must be a JSON object",
                    http_status=400,
                )
            return data

        def _query(self) -> dict[str, list[str]]:
            return parse_qs(urlparse(self.path).query, keep_blank_values=True)

        def _query_value(self, query: Mapping[str, list[str]], key: str, default: str = "") -> str:
            values = query.get(key)
            if values:
                return values[0]
            return default

        def _dispatch(self, method: str) -> None:
            try:
                path = urlparse(self.path).path.rstrip("/") or "/"
                if method == "GET" and path == "/health":
                    self._json_response(200, service.build_health_payload())
                    return
                if method == "GET" and path == "/v1/capabilities":
                    self._json_response(200, service.build_capabilities_payload())
                    return
                if method == "GET" and path == "/v1/session/state":
                    self._handle_get_session_state()
                    return
                if method == "GET" and path == "/v1/sessions":
                    self._handle_list_sessions()
                    return
                if method == "POST" and path == "/v1/session/send":
                    self._handle_send_message()
                    return
                if method == "POST" and path == "/v1/session/reset":
                    self._handle_reset_session()
                    return
                if method == "POST" and path == "/v1/session/interrupt":
                    self._handle_interrupt_session()
                    return
                self._json_response(404, {"ok": False, "error": {"code": "not_found", "message": "Not found"}})
            except SidecarException as exc:
                self._error_response(exc)
            except Exception as exc:  # pragma: no cover - defensive guard
                self._error_response(
                    SidecarException(
                        CODE_INTERNAL_ERROR,
                        f"Internal error: {exc}",
                        http_status=500,
                    )
                )

        def _handle_get_session_state(self) -> None:
            query = self._query()
            session_id = self._query_value(query, "session_id")
            session_key = self._query_value(query, "session_key")
            payload = service.get_session_state(
                session_id=session_id, session_key=session_key
            )
            self._json_response(200, payload)

        def _handle_list_sessions(self) -> None:
            query = self._query()
            session_id = self._query_value(query, "session_id")
            session_key = self._query_value(query, "session_key")
            limit_raw = self._query_value(query, "limit", "25")
            try:
                limit = int(limit_raw)
            except ValueError as error:
                raise SidecarException(
                    CODE_INVALID_REQUEST,
                    "limit must be an integer",
                    http_status=400,
                ) from error
            payload = service.list_sessions(
                session_id=session_id, session_key=session_key, limit=limit
            )
            self._json_response(200, payload)

        def _read_send_body(self) -> tuple[str, str, str, PageContext | None]:
            data = self._read_body()
            session_id = data.get("session_id", "")
            session_key = data.get("session_key", "")
            message = data.get("message", "")
            page_context_raw = data.get("page_context")
            for name, value in (("session_id", session_id), ("session_key", session_key), ("message", message)):
                if not isinstance(value, str):
                    raise SidecarException(
                        CODE_INVALID_REQUEST,
                        f"Field {name} must be a string",
                        http_status=400,
                    )
            page_context: PageContext | None = None
            if page_context_raw is not None:
                if not isinstance(page_context_raw, Mapping):
                    raise SidecarException(
                        CODE_INVALID_REQUEST,
                        "page_context must be an object",
                        http_status=400,
                    )
                try:
                    page_context = PageContext.from_dict(page_context_raw)
                except ValueError as error:
                    raise SidecarException(
                        CODE_INVALID_REQUEST,
                        str(error),
                        http_status=400,
                    ) from error
            return session_id, session_key, message, page_context

        def _read_session_body(self) -> tuple[str, str]:
            data = self._read_body()
            session_id = data.get("session_id", "")
            session_key = data.get("session_key", "")
            for name, value in (("session_id", session_id), ("session_key", session_key)):
                if not isinstance(value, str):
                    raise SidecarException(
                        CODE_INVALID_REQUEST,
                        f"Field {name} must be a string",
                        http_status=400,
                    )
            return session_id, session_key

        def _handle_send_message(self) -> None:
            session_id, session_key, message, page_context = self._read_send_body()
            payload = service.send_message(
                session_id=session_id,
                session_key=session_key,
                message=message,
                page_context=page_context,
            )
            self._json_response(200, payload)

        def _handle_reset_session(self) -> None:
            session_id, session_key = self._read_session_body()
            payload = service.reset_session(
                session_id=session_id, session_key=session_key
            )
            self._json_response(200, payload)

        def _handle_interrupt_session(self) -> None:
            session_id, session_key = self._read_session_body()
            payload = service.interrupt_session(
                session_id=session_id, session_key=session_key
            )
            self._json_response(200, payload)

    return SidecarHandler
