from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from hermes_browser_sidecar.transports.base import BaseTransport, TransportProbe


class HermesBridgeTransport(BaseTransport):
    name = "bridge"

    def __init__(self, *, inject_url: str, token: str) -> None:
        self.inject_url = inject_url
        self.token = token

    @property
    def health_url(self) -> str:
        parsed = urlparse(self.inject_url)
        return urlunparse(parsed._replace(path="/health", params="", query="", fragment=""))

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

