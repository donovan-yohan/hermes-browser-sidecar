from __future__ import annotations

from hermes_browser_sidecar.config import SidecarSettings
from hermes_browser_sidecar.transports.base import TransportProbe


PROTOCOL_VERSION = "0.2"


def build_capabilities(*, sessions_enabled: bool) -> dict[str, bool]:
    return {
        "health_check": True,
        "capability_discovery": True,
        "session_state": sessions_enabled,
        "session_list": sessions_enabled,
        "session_send": sessions_enabled,
        "session_reset": sessions_enabled,
        "session_interrupt": sessions_enabled,
        "page_context": sessions_enabled,
        "attachments": False,
        "tts": False,
        "stt": False,
    }


def build_health_payload(
    *,
    settings: SidecarSettings,
    active_adapter: str,
    probe: TransportProbe,
    capabilities: dict[str, bool],
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
        "capabilities": capabilities,
        "notes": [
            "The extension talks to this local sidecar service, not Hermes directly.",
            "Bridge-backed session flows are available when the active adapter supports them.",
        ],
    }
