from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from hermes_browser_sidecar.transports.base import BaseTransport, TransportProbe


class HermesBridgeTransport(BaseTransport):
    name = "bridge"
    supports_sessions = True

    def __init__(self, *, inject_url: str, token: str) -> None:
        self.inject_url = inject_url
        self.token = token

    @property
    def health_url(self) -> str:
        parsed = urlparse(self.inject_url)
        return urlunparse(parsed._replace(path="/health", params="", query="", fragment=""))

    @property
    def session_url(self) -> str:
        parsed = urlparse(self.inject_url)
        return urlunparse(parsed._replace(path="/session", params="", query="", fragment=""))

    def _request_json(
        self,
        *,
        url: str,
        method: str,
        payload: dict[str, object] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, object]:
        headers = {
            "Accept": "application/json",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        request = Request(url, headers=headers, data=body, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8") or "{}")
                if not isinstance(data, dict):
                    raise RuntimeError(f"Unexpected Hermes bridge payload from {url}.")
                if data.get("ok") is False:
                    raise RuntimeError(str(data.get("error") or "Hermes browser bridge request failed."))
                return data
        except HTTPError as error:
            detail = f"Hermes browser bridge returned HTTP {error.code}."
            try:
                payload_text = error.read().decode("utf-8") or "{}"
                parsed = json.loads(payload_text)
                if isinstance(parsed, dict) and parsed.get("error"):
                    detail = str(parsed["error"])
            except Exception:
                pass
            raise RuntimeError(detail) from error
        except (OSError, URLError) as error:
            raise RuntimeError(f"Hermes browser bridge request failed: {error}") from error

    def probe(self) -> TransportProbe:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(self.health_url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8") or "{}")
                return TransportProbe(
                    name=self.name,
                    ok=200 <= response.status < 300,
                    endpoint=self.health_url,
                    status_code=response.status,
                    detail="Hermes browser bridge reachable.",
                    payload=payload,
                )
        except HTTPError as error:
            return TransportProbe(
                name=self.name,
                ok=False,
                endpoint=self.health_url,
                status_code=error.code,
                detail=f"Hermes browser bridge returned HTTP {error.code}.",
                payload={},
            )
        except (OSError, URLError) as error:
            return TransportProbe(
                name=self.name,
                ok=False,
                endpoint=self.health_url,
                status_code=None,
                detail=f"Hermes browser bridge probe failed: {error}",
                payload={},
            )

    def _session_payload(
        self,
        *,
        action: str,
        browser_label: str,
        client_session_id: str,
        session_key: str = "",
        limit: int | None = None,
        message: str = "",
        page_context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "action": action,
            "browserLabel": browser_label,
            "clientSessionId": client_session_id,
        }
        if session_key:
            payload["sessionKey"] = session_key
        if limit is not None:
            payload["limit"] = limit
        if message:
            payload["message"] = message
        if page_context:
            payload["pageContext"] = page_context
        return payload

    def get_session_state(
        self,
        *,
        browser_label: str,
        client_session_id: str,
        session_key: str = "",
    ) -> dict[str, object]:
        return self._request_json(
            url=self.session_url,
            method="POST",
            payload=self._session_payload(
                action="state",
                browser_label=browser_label,
                client_session_id=client_session_id,
                session_key=session_key,
            ),
        )

    def list_sessions(
        self,
        *,
        browser_label: str,
        client_session_id: str,
        session_key: str = "",
        limit: int = 25,
    ) -> dict[str, object]:
        return self._request_json(
            url=self.session_url,
            method="POST",
            payload=self._session_payload(
                action="list",
                browser_label=browser_label,
                client_session_id=client_session_id,
                session_key=session_key,
                limit=limit,
            ),
        )

    def send_message(
        self,
        *,
        browser_label: str,
        client_session_id: str,
        session_key: str = "",
        message: str = "",
        page_context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return self._request_json(
            url=self.session_url,
            method="POST",
            payload=self._session_payload(
                action="send",
                browser_label=browser_label,
                client_session_id=client_session_id,
                session_key=session_key,
                message=message,
                page_context=page_context,
            ),
            timeout=300.0,
        )

    def reset_session(
        self,
        *,
        browser_label: str,
        client_session_id: str,
        session_key: str = "",
    ) -> dict[str, object]:
        return self._request_json(
            url=self.session_url,
            method="POST",
            payload=self._session_payload(
                action="reset",
                browser_label=browser_label,
                client_session_id=client_session_id,
                session_key=session_key,
            ),
        )

    def interrupt_session(
        self,
        *,
        browser_label: str,
        client_session_id: str,
        session_key: str = "",
    ) -> dict[str, object]:
        return self._request_json(
            url=self.session_url,
            method="POST",
            payload=self._session_payload(
                action="interrupt",
                browser_label=browser_label,
                client_session_id=client_session_id,
                session_key=session_key,
            ),
        )
