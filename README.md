# hermes-browser-sidecar

`hermes-browser-sidecar` owns a stable local HTTP protocol for the Hermes
browser side panel, plus pluggable transport adapters that translate that
protocol into upstream Hermes calls.

The browser extension only ever talks to the sidecar (`http://127.0.0.1:8787`
by default). It never speaks to Hermes directly, never knows Hermes bridge
action names, and never sees Hermes bearer tokens.

## Architecture

- **Public protocol** (`python/src/hermes_browser_sidecar/protocol/`) —
  snake_case JSON dataclasses. Single source of truth for what extensions see.
  See [docs/protocol.md](docs/protocol.md).
- **Transport adapters** (`python/src/hermes_browser_sidecar/transports/`) —
  internal. Translate public requests into upstream calls and normalize
  upstream responses back into public types.
  - `bridge.py` targets the Hermes browser bridge `/session` action endpoint.
  - `api_server.py` targets the Hermes OpenAI-compatible Responses API.
- **Service** (`service.py`) — owns adapter selection, capability union,
  request routing.
- **Server** (`server.py`) — pure HTTP: routing, CORS, error mapping.

## Quick Start

### Python sidecar service

```bash
PYTHONPATH=python/src python3 -m hermes_browser_sidecar print-config
PYTHONPATH=python/src python3 -m hermes_browser_sidecar probe
PYTHONPATH=python/src python3 -m hermes_browser_sidecar serve
```

Editable install:
```bash
python3 -m pip install -e .
hermes-browser-sidecar serve
```

### Smoke

```bash
curl -sS http://127.0.0.1:8787/health | python3 -m json.tool
curl -sS http://127.0.0.1:8787/v1/capabilities | python3 -m json.tool
curl -sS 'http://127.0.0.1:8787/v1/session/state?session_id=panel-1' \
  | python3 -m json.tool
```

### Tests

```bash
python3 -m pytest tests/
```

### Extension

1. `chrome://extensions` → enable **Developer mode**
2. **Load unpacked** → select `extension/`
3. Click the extension action to open the side panel.
4. Visit a regular page (the extension uses `chrome.scripting` to read page
   text/selection; it cannot inject into `chrome://` pages).

The extension auto-fetches `/v1/capabilities` and renders only enabled
features; if the active adapter probe fails, send/reset/interrupt return 502
and the side panel shows the upstream error.

## Configuration

| Env var                          | Default                          | Description |
|----------------------------------|----------------------------------|-------------|
| `HERMES_SIDECAR_HOST`            | `127.0.0.1`                      | Sidecar listen host. |
| `HERMES_SIDECAR_PORT`            | `8787`                           | Sidecar listen port. |
| `HERMES_SIDECAR_TRANSPORT`       | `hybrid`                         | `bridge`, `api_server`, or `hybrid`. |
| `HERMES_SIDECAR_BROWSER_LABEL`   | `Hermes Browser Sidecar`         | Identifier sent to the bridge for client routing. |
| `HERMES_BROWSER_BRIDGE_URL`      | `http://127.0.0.1:8765/inject`   | Hermes browser bridge base. |
| `HERMES_BROWSER_BRIDGE_TOKEN`    | (empty)                          | Bridge bearer token. |
| `HERMES_API_SERVER_URL`          | `http://127.0.0.1:8642/v1`       | Hermes API server base. |
| `HERMES_API_SERVER_KEY`          | (empty)                          | API server bearer token. |
| `HERMES_API_SERVER_MODEL`        | `hermes`                         | Model name passed to `/v1/responses`. |

## Hybrid mode

In hybrid mode the service probes the bridge first; if reachable, it routes
session calls there and treats the API server as a fallback. If the bridge is
down, it falls back to the API server adapter. Capabilities reported on
`/v1/capabilities` are the union of all reachable adapters, so the extension
can render features as soon as any adapter supports them.

## Security note

The sidecar has **no authentication** on its local HTTP surface. It is meant
to bind to `127.0.0.1` only. Auth is a Phase 4 item — see [TODO.md](TODO.md).

## Repository layout

```text
.
├── docs/                # protocol + architecture docs
├── extension/           # MV3 side panel client
├── python/src/hermes_browser_sidecar/
│   ├── protocol/        # public sidecar types
│   ├── transports/      # internal adapters (bridge, api_server)
│   ├── server.py        # HTTP + CORS + error mapping
│   └── service.py       # hybrid selection + typed handlers
├── tests/               # pytest suites + fakes + fixtures
└── TODO.md
```
