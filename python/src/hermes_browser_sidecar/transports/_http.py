from __future__ import annotations

import json
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HermesUpstreamError(Exception):
    def __init__(
        self,
        *,
        status_code: int | None,
        detail: str,
        payload: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.payload = dict(payload) if payload is not None else None


def request_json(
    *,
    url: str,
    method: str,
    headers: Mapping[str, str] | None = None,
    payload: Mapping[str, object] | None = None,
    timeout: float = 30.0,
) -> dict[str, object]:
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    body: bytes | None = None
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")

    request = Request(url, headers=request_headers, data=body, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8") or "{}"
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise HermesUpstreamError(
                    status_code=response.status,
                    detail=f"Unexpected upstream payload from {url} (not an object).",
                )
            if data.get("ok") is False:
                error_text = str(data.get("error") or "Upstream reported failure.")
                raise HermesUpstreamError(
                    status_code=response.status,
                    detail=error_text,
                    payload=data,
                )
            return data
    except HTTPError as error:
        detail = f"Upstream returned HTTP {error.code}."
        parsed_payload: dict[str, object] | None = None
        try:
            text = error.read().decode("utf-8") or "{}"
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                parsed_payload = parsed
                if parsed.get("error"):
                    detail = str(parsed["error"])
        except Exception:
            pass
        raise HermesUpstreamError(
            status_code=error.code,
            detail=detail,
            payload=parsed_payload,
        ) from error
    except (OSError, URLError) as error:
        raise HermesUpstreamError(
            status_code=None,
            detail=f"Upstream request failed: {error}",
        ) from error
