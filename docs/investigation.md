# Hermes Investigation

## Summary

Hermes Agent currently exposes two relevant surfaces for a browser sidecar:

1. a localhost browser bridge designed specifically for the current sidecar
2. an OpenAI-compatible HTTP API server designed for generic chat frontends

The browser bridge is the only surface that currently covers sidecar-specific session controls and browser-native extras. The API server is cleaner, but it is incomplete for a first extraction if the goal is to preserve the current UX.

## Existing Browser Bridge Surface

The bridge lives in `gateway/browser_bridge.py` and gateway session handling in `gateway/run.py`.

### Routes

- `GET /health`
- `GET /media`
- `POST /inject`
- `POST /session`

### Auth

- bearer token via `Authorization: Bearer <token>`
- legacy support for `X-Hermes-Bridge-Token`
- token usually read from `~/.hermes/browser_bridge_token`

### Notable `/session` actions

- `state`
- `inspect`
- `list`
- `reset`
- `interrupt`
- `send`
- `send_async`
- `tts`
- `transcribe_audio`
- `runtime_config_get`
- `runtime_config_save`
- `runtime_provider_models`
- `recall_search`
- `fetch_transcript`
- `fetch_pdf_text`
- `fetch_pdf_preview_info`

### Practical conclusion

This is the real surface the current Hermes browser extension depends on. It is productive, but it is also deeply coupled to gateway internals, Hermes session bookkeeping, and specific sidecar UX assumptions.

## Existing API Server Surface

The API server lives in `gateway/platforms/api_server.py`.

### Routes

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `GET /v1/responses/{response_id}`
- `DELETE /v1/responses/{response_id}`

### Auth and browser behavior

- bearer token auth via `API_SERVER_KEY`
- browser clients require explicit CORS allowlisting
- conversation state exists for Responses API through stored `response_id` history

### Practical conclusion

This surface is clean and broadly useful, but it is generic. It is appropriate for Open WebUI and similar clients, not as a drop-in replacement for today's sidecar without additional local session logic.

## Current Extension Coupling

The existing Hermes extension depends on the browser bridge rather than the API server.

Evidence from the fork:

- default bridge URL points at `http://127.0.0.1:8765/inject`
- extension health checks use bridge `GET /health`
- side panel uses `POST /session` with custom `action` values
- options UI reads and writes bridge URL and bridge token
- runtime model and config helpers come through the bridge, not the API server

This means the current extension is not transport-agnostic today.

## Option Comparison

## 1. Current Browser Bridge Coupling

Pros:

- closest to current behavior
- already supports sidecar-specific session operations
- already supports transcript, PDF, TTS, STT, and page-context helper flows

Cons:

- private and unstable action surface
- coupled to gateway internals and session store behavior
- extension must understand Hermes-specific conventions

## 2. API-Server-Based Approach

Pros:

- much cleaner public surface
- generic client compatibility
- easier to explain and test

Cons:

- not enough for current sidecar UX without additional local logic
- no native page-context or sidecar-session contract
- missing current interrupt and sidecar inspection semantics

## 3. Hybrid Architecture

Pros:

- preserves current compatibility through the bridge
- creates a stable public boundary for this repository
- leaves room to shift generic chat operations toward the API server later

Cons:

- one extra translation layer
- still needs deliberate design to prevent bridge leakage into the extension contract

## Recommendation

Adopt the hybrid architecture.

Specifically:

- make the extension talk only to a local sidecar service
- define a stable sidecar protocol in this repo
- use the Hermes browser bridge as the first adapter
- add an API-server adapter later when session and page-context responsibilities are clearly owned locally

## Unstable Or Private Seams To Call Out Explicitly

- browser bridge `action` names are effectively private RPC verbs today
- sidecar session semantics depend on Hermes gateway session-store behavior
- `/media` exposes filesystem-backed image paths through bridge-specific conventions
- runtime config save and provider model discovery are gateway-specific convenience flows
- page-context payload shape is shaped by the current extension and gateway message builders rather than a stable external schema

