# hermes-browser-sidecar

`hermes-browser-sidecar` is a public extraction scaffold for a portable Hermes browser sidecar.

The current recommendation is a hybrid architecture:

- the browser extension stays transport-agnostic
- a local sidecar service owns the stable protocol boundary
- the first backend adapter targets Hermes Agent's existing browser bridge
- a future adapter can use the OpenAI-compatible API server where that surface is sufficient

This repository is intentionally conservative. It does not attempt to port the full Hermes sidecar yet. The current scaffold focuses on investigation, architecture, starter packaging, and a minimal no-build MV3 extension shell.

## Why Hybrid

The existing Hermes browser sidecar is coupled to a custom localhost bridge with sidecar-specific actions like `state`, `list`, `inspect`, `reset`, `interrupt`, `send_async`, `tts`, `transcribe_audio`, and runtime config helpers. That is practical for short-term compatibility, but it is not a clean public boundary.

Hermes Agent also exposes an OpenAI-compatible API server. That surface is much cleaner, but today it does not provide sidecar-specific state, page-context packaging, interrupt semantics, or browser-native extras on its own.

The compromise is to stabilize a local sidecar protocol here, keep the extension dumb, and let backend adapters absorb Hermes-specific integration seams.

## Current Scaffold

- [docs/investigation.md](docs/investigation.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/extraction-plan.md](docs/extraction-plan.md)
- `python/` for the starter backend package
- `extension/` for the starter Chrome/Chromium MV3 side panel client
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

### Extension scaffold

1. Open `chrome://extensions`
2. Enable `Developer mode`
3. Click `Load unpacked`
4. Select the local `extension/` directory
5. Open the side panel or the options page

The extension currently verifies sidecar health and reads declared capabilities. It does not yet attempt a full Hermes chat transport.

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

## Provenance

This scaffold is based on investigation of the Hermes Agent fork described in [docs/investigation.md](docs/investigation.md). No substantial source files were copied into this repository during this pass.
