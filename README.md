# hermes-browser-sidecar

`hermes-browser-sidecar` is a public browser sidecar for Hermes that keeps the extension on a stable local protocol while translating to Hermes's current browser bridge underneath.

The current recommendation is a hybrid architecture:

- the browser extension stays transport-agnostic
- a local sidecar service owns the stable protocol boundary
- the first backend adapter targets Hermes Agent's existing browser bridge
- a future adapter can use the OpenAI-compatible API server where that surface is sufficient

This repository still stays conservative on architecture, but it now ships a materially usable bridge-backed baseline:

- the Python service exposes local `/v1/...` sidecar endpoints
- the MV3 extension can read session state, send messages, start a new chat, interrupt a turn, and optionally bundle page context from the active tab
- Hermes-specific bridge action names and bearer-token details stay inside the service adapter

## Why Hybrid

The existing Hermes browser sidecar is coupled to a custom localhost bridge with sidecar-specific actions like `state`, `list`, `inspect`, `reset`, `interrupt`, `send_async`, `tts`, `transcribe_audio`, and runtime config helpers. That is practical for short-term compatibility, but it is not a clean public boundary.

Hermes Agent also exposes an OpenAI-compatible API server. That surface is much cleaner, but today it does not provide sidecar-specific state, page-context packaging, interrupt semantics, or browser-native extras on its own.

The compromise is to stabilize a local sidecar protocol here, keep the extension dumb, and let backend adapters absorb Hermes-specific integration seams.

## Current State

- [docs/investigation.md](docs/investigation.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/extraction-plan.md](docs/extraction-plan.md)
- `python/` for the local sidecar service and Hermes adapters
- `extension/` for the Chrome/Chromium MV3 side panel client
- [TODO.md](TODO.md) for concrete next steps

## Quick Start

### Python sidecar service

```bash
PYTHONPATH=python/src python3 -m hermes_browser_sidecar print-config
PYTHONPATH=python/src python3 -m hermes_browser_sidecar probe
PYTHONPATH=python/src python3 -m hermes_browser_sidecar serve
```

For a normal editable install on a standard Python toolchain:

```bash
python3 -m pip install -e .
hermes-browser-sidecar print-config
hermes-browser-sidecar probe
hermes-browser-sidecar serve
```

Defaults:

- sidecar service: `http://127.0.0.1:8787`
- Hermes bridge probe target: `http://127.0.0.1:8765/inject`
- Hermes API server probe target: `http://127.0.0.1:8642/v1`
- transport mode: `hybrid`
- browser label: `Hermes Browser Sidecar`

### Pair with Hermes

Start Hermes on the matching bridge-enabled branch and run:

```bash
HERMES_SIDECAR_TRANSPORT=hybrid \
HERMES_BROWSER_BRIDGE_URL=http://127.0.0.1:8765/inject \
HERMES_BROWSER_BRIDGE_TOKEN="$(cat "${HERMES_HOME:-$HOME/.hermes}/browser_bridge_token")" \
PYTHONPATH=python/src python3 -m hermes_browser_sidecar serve
```

### Extension

1. Open `chrome://extensions`
2. Enable `Developer mode`
3. Click `Load unpacked`
4. Select the local `extension/` directory
5. Open the options page and confirm the backend URL is `http://127.0.0.1:8787`
6. Open the side panel
7. Send a message, or leave the composer empty and send with `Use current page` enabled to share page context only

Current extension behavior:

- shows the active page title/URL plus text-size metadata
- reads current Hermes sidecar session state
- sends normal chat turns
- sends chat turns with bundled page context from the active tab
- starts a fresh sidecar chat
- interrupts the current Hermes turn

## Repository Layout

```text
.
├── docs/
├── extension/
├── python/
│   └── src/hermes_browser_sidecar/
├── tests/
├── CODEX_TASK.md
└── TODO.md
```

## Local Protocol

The extension only talks to the local sidecar service. The current public routes are:

- `GET /health`
- `GET /v1/capabilities`
- `GET /v1/session/state`
- `GET /v1/sessions`
- `POST /v1/session/send`
- `POST /v1/session/reset`
- `POST /v1/session/interrupt`

The bridge adapter translates those calls to Hermes browser-bridge routes and action names internally.

## Provenance

This scaffold is based on investigation of the Hermes Agent fork described in [docs/investigation.md](docs/investigation.md). No substantial source files were copied into this repository during this pass.
