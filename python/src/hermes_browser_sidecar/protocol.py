from __future__ import annotations

from hermes_browser_sidecar.config import SidecarSettings
from hermes_browser_sidecar.transports.base import TransportProbe


PROTOCOL_VERSION = "0.1"


def build_capabilities() -> dict[str, bool]:
    return {
        "health_check": True,
        "capability_discovery": True,
        "session_state": False,
        "session_send": False,
        "session_reset": False,
        "session_interrupt": False,
        "page_context": False,
        "attachments": False,
        "tts": False,
        "stt": False,
    }


def build_health_payload(
    *,
    settings: SidecarSettings,
    active_adapter: str,
    probe: TransportProbe,
) -> dict[str, object]:
    return {
        "ok": True,
        "service": "hermes-browser-sidecar",
        "protocol_version": PROTOCOL_VERSION,
        "transport": {
            "mode": settings.transport,
            "active_adapter": active_adapter,
        },
        "sidecar": {
            "base_url": settings.service_base_url,
        },
        "upstream": probe.to_dict(),
        "capabilities": build_capabilities(),
        "notes": [
            "Scaffold only. Session transport is not implemented yet.",
            "Bridge-first compatibility is the current active recommendation.",
        ],
    }

