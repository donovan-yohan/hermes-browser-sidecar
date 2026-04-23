"""Public sidecar protocol — sidecar-owned types and payload builders.

Wire format is snake_case JSON. Upstream-specific naming (Hermes bridge
camelCase, Responses-API shape) lives entirely inside `transports/` and
must never leak into anything exported from this package.
"""

from hermes_browser_sidecar.protocol.payloads import (
    PROTOCOL_VERSION,
    build_capabilities_payload,
    build_health_payload,
)
from hermes_browser_sidecar.protocol.types import (
    Capabilities,
    PageContext,
    SidecarError,
    SidecarMessage,
    SidecarProgress,
    SidecarSession,
)


__all__ = [
    "PROTOCOL_VERSION",
    "Capabilities",
    "PageContext",
    "SidecarError",
    "SidecarMessage",
    "SidecarProgress",
    "SidecarSession",
    "build_capabilities_payload",
    "build_health_payload",
]
