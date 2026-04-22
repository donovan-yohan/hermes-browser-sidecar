from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from hermes_browser_sidecar.transports.base import BaseTransport, TransportProbe


class HermesAPIServerTransport(BaseTransport):
    name = "api_server"

    def __init__(self, *, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key

    @property
    def health_url(self) -> str:
        parsed = urlparse(self.base_url)
        return urlunparse(parsed._replace(path="/health", params="", query="", fragment=""))

    def probe(self) -> TransportProbe:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = Request(self.health_url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8") or "{}")
                return TransportProbe(
                    name=self.name,
                    ok=200 <= response.status < 300,
                    endpoint=self.health_url,
                    status_code=response.status,
                    detail="Hermes API server reachable.",
                    payload=payload,
                )
        except HTTPError as error:
            return TransportProbe(
                name=self.name,
                ok=False,
                endpoint=self.health_url,
                status_code=error.code,
                detail=f"Hermes API server returned HTTP {error.code}.",
                payload={},
            )
        except (OSError, URLError) as error:
            return TransportProbe(
                name=self.name,
                ok=False,
                endpoint=self.health_url,
                status_code=None,
                detail=f"Hermes API server probe failed: {error}",
                payload={},
            )

