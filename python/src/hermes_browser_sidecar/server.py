from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


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
        server_version = "HermesBrowserSidecar/0.1"

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._write_cors_headers()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            route = parsed.path.rstrip("/")
            query = parse_qs(parsed.query or "")

            if route == "/health":
                self._json_response(200, service.build_health_payload())
                return

            if route == "/v1/capabilities":
                self._json_response(200, service.build_capabilities_payload())
                return

            if route == "/v1/session/state":
                try:
                    self._json_response(
                        200,
                        service.get_session_state(
                            client_session_id=self._read_client_session_id(query),
                            session_key=self._first_query(query, "session_key"),
                        ),
                    )
                except ValueError as error:
                    self._json_response(400, {"ok": False, "error": str(error)})
                except NotImplementedError as error:
                    self._json_response(501, {"ok": False, "error": str(error)})
                except RuntimeError as error:
                    self._json_response(502, {"ok": False, "error": str(error)})
                return

            if route == "/v1/sessions":
                try:
                    raw_limit = self._first_query(query, "limit")
                    limit = int(raw_limit) if raw_limit else 25
                    self._json_response(
                        200,
                        service.list_sessions(
                            client_session_id=self._read_client_session_id(query),
                            session_key=self._first_query(query, "session_key"),
                            limit=limit,
                        ),
                    )
                except ValueError as error:
                    self._json_response(400, {"ok": False, "error": str(error)})
                except NotImplementedError as error:
                    self._json_response(501, {"ok": False, "error": str(error)})
                except RuntimeError as error:
                    self._json_response(502, {"ok": False, "error": str(error)})
                return

            self._json_response(404, {"ok": False, "error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            route = self.path.rstrip("/")
            if route not in {
                "/v1/session/send",
                "/v1/session/reset",
                "/v1/session/interrupt",
            }:
                self._json_response(404, {"ok": False, "error": "Not found"})
                return

            try:
                payload = self._read_json_body()
                client_session_id = self._read_body_client_session_id(payload)
                session_key = str(payload.get("session_key") or "").strip()

                if route == "/v1/session/send":
                    self._json_response(
                        200,
                        service.send_message(
                            client_session_id=client_session_id,
                            session_key=session_key,
                            message=str(payload.get("message") or "").strip(),
                            page_context=self._read_page_context(payload),
                        ),
                    )
                    return

                if route == "/v1/session/reset":
                    self._json_response(
                        200,
                        service.reset_session(
                            client_session_id=client_session_id,
                            session_key=session_key,
                        ),
                    )
                    return

                self._json_response(
                    200,
                    service.interrupt_session(
                        client_session_id=client_session_id,
                        session_key=session_key,
                    ),
                )
            except ValueError as error:
                self._json_response(400, {"ok": False, "error": str(error)})
            except NotImplementedError as error:
                self._json_response(501, {"ok": False, "error": str(error)})
            except RuntimeError as error:
                self._json_response(502, {"ok": False, "error": str(error)})

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def _first_query(self, query: dict[str, list[str]], key: str) -> str:
            return str((query.get(key) or [""])[0] or "").strip()

        def _read_client_session_id(self, query: dict[str, list[str]]) -> str:
            client_session_id = self._first_query(query, "client_session_id")
            if client_session_id:
                return client_session_id
            raise ValueError("Missing client_session_id.")

        def _read_body_client_session_id(self, payload: dict[str, object]) -> str:
            client_session_id = str(payload.get("client_session_id") or "").strip()
            if client_session_id:
                return client_session_id
            raise ValueError("Missing client_session_id.")

        def _read_json_body(self) -> dict[str, object]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise ValueError("Invalid Content-Length header.") from error
            if length <= 0:
                raise ValueError("Missing request body.")
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception as error:
                raise ValueError("Invalid JSON payload.") from error
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            return payload

        def _read_page_context(self, payload: dict[str, object]) -> dict[str, object] | None:
            page_context = payload.get("page_context")
            if page_context is None:
                return None
            if not isinstance(page_context, dict):
                raise ValueError("page_context must be an object when provided.")
            return page_context

        def _write_cors_headers(self) -> None:
            origin = self.headers.get("Origin", "")
            if origin.startswith("chrome-extension://"):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

        def _json_response(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self._write_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return SidecarHandler
