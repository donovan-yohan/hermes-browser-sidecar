from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TransportProbe:
    name: str
    ok: bool
    endpoint: str
    status_code: int | None
    detail: str
    payload: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "endpoint": self.endpoint,
            "status_code": self.status_code,
            "detail": self.detail,
            "payload": self.payload or {},
        }


class BaseTransport:
    name = "base"

    def probe(self) -> TransportProbe:
        raise NotImplementedError

