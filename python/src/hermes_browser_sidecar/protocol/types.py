from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Mapping


def _require_str(data: Mapping[str, object], key: str) -> str:
    if key not in data:
        raise ValueError(f"Missing required field: {key}")
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"Field {key} must be a string")
    return value


def _require_bool(data: Mapping[str, object], key: str) -> bool:
    if key not in data:
        raise ValueError(f"Missing required field: {key}")
    value = data[key]
    if not isinstance(value, bool):
        raise ValueError(f"Field {key} must be a boolean")
    return value


@dataclass(frozen=True)
class SidecarProgress:
    running: bool
    error: str | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {"running": self.running, "error": self.error, "detail": self.detail}

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "SidecarProgress":
        running = _require_bool(data, "running")
        raw_error = data.get("error")
        if raw_error is not None and not isinstance(raw_error, str):
            raise ValueError("Field error must be a string or null")
        raw_detail = data.get("detail", "")
        if not isinstance(raw_detail, str):
            raise ValueError("Field detail must be a string")
        return cls(running=running, error=raw_error, detail=raw_detail)


@dataclass(frozen=True)
class PageContext:
    title: str
    url: str
    selection: str
    page_text: str
    content_kind: str
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "url": self.url,
            "selection": self.selection,
            "page_text": self.page_text,
            "content_kind": self.content_kind,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "PageContext":
        metadata = data.get("metadata", {}) or {}
        if not isinstance(metadata, Mapping):
            raise ValueError("Field metadata must be an object")
        return cls(
            title=_require_str(data, "title"),
            url=_require_str(data, "url"),
            selection=_require_str(data, "selection"),
            page_text=_require_str(data, "page_text"),
            content_kind=_require_str(data, "content_kind"),
            metadata=dict(metadata),
        )


@dataclass(frozen=True)
class SidecarMessage:
    role: str
    content: str
    timestamp: str
    kind: str = "text"
    metadata: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        body: dict[str, object] = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "kind": self.kind,
        }
        if self.metadata is not None:
            body["metadata"] = dict(self.metadata)
        return body

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "SidecarMessage":
        metadata_raw = data.get("metadata")
        if metadata_raw is not None and not isinstance(metadata_raw, Mapping):
            raise ValueError("Field metadata must be an object or null")
        kind = data.get("kind", "text")
        if not isinstance(kind, str):
            raise ValueError("Field kind must be a string")
        return cls(
            role=_require_str(data, "role"),
            content=_require_str(data, "content"),
            timestamp=_require_str(data, "timestamp"),
            kind=kind,
            metadata=dict(metadata_raw) if metadata_raw is not None else None,
        )


@dataclass(frozen=True)
class SidecarSession:
    session_id: str
    session_key: str
    messages: tuple[SidecarMessage, ...]
    progress: SidecarProgress
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "session_key": self.session_key,
            "messages": [m.to_dict() for m in self.messages],
            "progress": self.progress.to_dict(),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "SidecarSession":
        raw_messages = data.get("messages", [])
        if not isinstance(raw_messages, list):
            raise ValueError("Field messages must be a list")
        progress_raw = data.get("progress")
        if not isinstance(progress_raw, Mapping):
            raise ValueError("Field progress must be an object")
        return cls(
            session_id=_require_str(data, "session_id"),
            session_key=_require_str(data, "session_key"),
            messages=tuple(SidecarMessage.from_dict(m) for m in raw_messages),
            progress=SidecarProgress.from_dict(progress_raw),
            updated_at=_require_str(data, "updated_at"),
        )


@dataclass(frozen=True)
class SidecarError:
    code: str
    message: str
    detail: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        body: dict[str, object] = {"code": self.code, "message": self.message}
        if self.detail is not None:
            body["detail"] = dict(self.detail)
        return body


@dataclass(frozen=True)
class Capabilities:
    health_check: bool = True
    capability_discovery: bool = True
    session_state: bool = False
    session_list: bool = False
    session_send: bool = False
    session_reset: bool = False
    session_interrupt: bool = False
    page_context: bool = False
    attachments: bool = False
    tts: bool = False
    stt: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def union(cls, *others: "Capabilities") -> "Capabilities":
        merged = {f.name: False for f in fields(cls)}
        for cap in others:
            for f in fields(cls):
                if getattr(cap, f.name):
                    merged[f.name] = True
        return cls(**merged)
