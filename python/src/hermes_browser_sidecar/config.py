from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Mapping


DEFAULT_SERVICE_HOST = "127.0.0.1"
DEFAULT_SERVICE_PORT = 8787
DEFAULT_HERMES_BRIDGE_URL = "http://127.0.0.1:8765/inject"
DEFAULT_HERMES_API_SERVER_URL = "http://127.0.0.1:8642/v1"
DEFAULT_TRANSPORT = "hybrid"
DEFAULT_BROWSER_LABEL = "Hermes Browser Sidecar"
ALLOWED_TRANSPORTS = {"bridge", "api_server", "hybrid"}


def _read_env(env: Mapping[str, str], key: str, default: str) -> str:
    value = str(env.get(key, "")).strip()
    return value or default


@dataclass(frozen=True)
class SidecarSettings:
    service_host: str
    service_port: int
    transport: str
    browser_label: str
    hermes_bridge_url: str
    hermes_bridge_token: str
    hermes_api_server_url: str
    hermes_api_server_key: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "SidecarSettings":
        source = env or os.environ
        transport = _read_env(source, "HERMES_SIDECAR_TRANSPORT", DEFAULT_TRANSPORT).lower()
        if transport not in ALLOWED_TRANSPORTS:
            transport = DEFAULT_TRANSPORT

        raw_port = _read_env(source, "HERMES_SIDECAR_PORT", str(DEFAULT_SERVICE_PORT))
        try:
            service_port = int(raw_port)
        except ValueError:
            service_port = DEFAULT_SERVICE_PORT

        return cls(
            service_host=_read_env(source, "HERMES_SIDECAR_HOST", DEFAULT_SERVICE_HOST),
            service_port=service_port,
            transport=transport,
            browser_label=_read_env(
                source,
                "HERMES_SIDECAR_BROWSER_LABEL",
                DEFAULT_BROWSER_LABEL,
            ),
            hermes_bridge_url=_read_env(
                source,
                "HERMES_BROWSER_BRIDGE_URL",
                DEFAULT_HERMES_BRIDGE_URL,
            ),
            hermes_bridge_token=_read_env(source, "HERMES_BROWSER_BRIDGE_TOKEN", ""),
            hermes_api_server_url=_read_env(
                source,
                "HERMES_API_SERVER_URL",
                DEFAULT_HERMES_API_SERVER_URL,
            ),
            hermes_api_server_key=_read_env(source, "HERMES_API_SERVER_KEY", ""),
        )

    @property
    def service_base_url(self) -> str:
        return f"http://{self.service_host}:{self.service_port}"

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["service_base_url"] = self.service_base_url
        return data
