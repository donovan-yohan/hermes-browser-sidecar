from __future__ import annotations

from hermes_browser_sidecar.config import SidecarSettings
from hermes_browser_sidecar.protocol.types import Capabilities
from hermes_browser_sidecar.transports.base import TransportProbe


PROTOCOL_VERSION = "1.0"
SERVICE_NAME = "hermes-browser-sidecar"


def build_capabilities_payload(capabilities: Capabilities) -> dict[str, object]:
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "protocol_version": PROTOCOL_VERSION,
        "capabilities": capabilities.to_dict(),
    }


def build_health_payload(
    *,
    settings: SidecarSettings,
    active_adapter: str,
    probe: TransportProbe,
    capabilities: Capabilities,
    notes: list[str] | None = None,
) -> dict[str, object]:
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "protocol_version": PROTOCOL_VERSION,
        "transport": {
            "mode": settings.transport,
            "active_adapter": active_adapter,
        },
        "sidecar": {"base_url": settings.service_base_url},
        "upstream": probe.to_dict(),
        "capabilities": capabilities.to_dict(),
        "notes": list(notes) if notes else [],
    }
