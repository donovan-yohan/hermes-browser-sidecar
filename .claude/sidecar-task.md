# Browser Sidecar Ownership and Protocol — Implementation

## Goal
Transform this repo from a thin scaffold into a real browser-sidecar product boundary that owns its public protocol and consumes a small Hermes core seam.

## Current state
This repo is a scaffold (`7ee2292`). It has:
- `python/src/hermes_browser_sidecar/server.py` — basic FastAPI server with stub routes
- `python/src/hermes_browser_sidecar/service.py` — thin service layer
- `python/src/hermes_browser_sidecar/protocol.py` — minimal protocol types
- `python/src/hermes_browser_sidecar/transports/` — base.py only
- `extension/background.js`, `sidepanel.js` — basic extension shell

## What to build

### 1. Public local `/v1` protocol (repo-owned contract)
Stabilize these routes in `server.py` with explicit request/response schemas in `protocol.py`:
- `GET /health` — service health, transport selection, upstream reachability
- `GET /v1/capabilities` — feature support declaration (session_state, session_send, page_context, attachments, tts, stt, screenshots, etc.)
- `GET /v1/session/state` — current session snapshot
- `GET /v1/sessions` — session list
- `POST /v1/session/send` — submit a turn
- `POST /v1/session/reset` — reset session
- `POST /v1/session/interrupt` — interrupt active turn

The protocol must be SIDE-OWNED. Do not expose Hermes bridge action names or payload shapes as the public contract.

### 2. Transport adapters (internal implementation detail)
Create `transports/bridge.py` and `transports/api_server.py` that:
- translate sidecar public protocol into Hermes-compatible upstream calls
- probe upstream availability
- map Hermes-specific errors into sidecar protocol errors
- normalize upstream payloads into sidecar-owned response shapes

The bridge adapter should target the Hermes localhost seam (to be implemented at `http://127.0.0.1:8765` or similar). Do NOT hardcode Hermes private action strings in the public protocol.

### 3. Browser extension (consumer of public protocol only)
Update `extension/background.js` and `extension/sidepanel.js` to:
- call ONLY the sidecar's local public protocol (`http://127.0.0.1:8787/v1/...`)
- render based on declared capabilities, not transport assumptions
- collect browser-local context (page text, selection, URL, title)
- NEVER call Hermes bridge routes or know Hermes bearer tokens directly

### 4. Service layer
Update `service.py` to:
- own adapter selection and probing
- compute capabilities from available transports
- handle the public protocol business logic
- shield the extension from upstream transport differences

## Architecture constraints

- The extension should not know Hermes bridge action names, bearer tokens, or private payload shapes.
- The public protocol should be versioned and documented.
- Transport adapters are INTERNAL. Their wire formats are NOT this repo's public contract.
- Do NOT pretend this repo replaces Hermes session ownership. Hermes still owns the actual runtime.
- The sidecar should target the Hermes local-client seam as its only ingress contract.

## Reference material

Read these before starting:
- `docs/superpowers/specs/2026-04-22-browser-sidecar-ownership-and-protocol.md` (full spec, 870 lines)
- `docs/architecture.md`
- `AGENTS.md`

There is a prior PR branch at `origin/feat/sidecar-reference-wireup-20260422` with a more complete implementation. You may inspect it for salvageable code (especially `transports/bridge.py`, `server.py`, `service.py`, `extension/`). But do NOT copy its architecture wholesale — it was "too thin" and mostly wrapped Hermes private payloads instead of owning a real public protocol.

## Verification

After implementation:
1. `pytest tests/` should pass.
2. The sidecar service should start and respond to `/health` and `/v1/capabilities`.
3. The extension should communicate only with the sidecar service.
4. Code should clearly separate public protocol from transport internals.

## Acceptance criteria
- This repo owns a stable public localhost `/v1` contract
- The extension calls only the sidecar service, never Hermes directly
- Transport adapters normalize Hermes upstream into sidecar-owned shapes
- Browser-specific product logic lives here, not in Hermes core
- The repo can function as a standalone sidecar product
