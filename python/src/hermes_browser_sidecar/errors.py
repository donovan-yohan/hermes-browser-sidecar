from __future__ import annotations

from typing import Mapping


CODE_INVALID_REQUEST = "invalid_request"
CODE_NOT_SUPPORTED = "not_supported"
CODE_UPSTREAM_UNAVAILABLE = "upstream_unavailable"
CODE_UPSTREAM_ERROR = "upstream_error"
CODE_SESSION_NOT_FOUND = "session_not_found"
CODE_INTERNAL_ERROR = "internal_error"


class SidecarException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        detail: Mapping[str, object] | None = None,
        http_status: int = 502,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = dict(detail) if detail is not None else None
        self.http_status = http_status

    def to_dict(self) -> dict[str, object]:
        body: dict[str, object] = {"code": self.code, "message": self.message}
        if self.detail is not None:
            body["detail"] = self.detail
        return body
