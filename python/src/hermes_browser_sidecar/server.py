from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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

        def do_GET(self) -> None:  # noqa: N802
            if self.path.rstrip("/") == "/health":
                self._json_response(200, service.build_health_payload())
                return

            if self.path.rstrip("/") == "/v1/capabilities":
                self._json_response(200, service.build_capabilities_payload())
                return

            self._json_response(404, {"ok": False, "error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path.startswith("/v1/session"):
                self._json_response(
                    501,
                    {
                        "ok": False,
                        "error": "Session endpoints are intentionally not implemented in this scaffold.",
                    },
                )
                return

            self._json_response(404, {"ok": False, "error": "Not found"})

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def _json_response(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return SidecarHandler

