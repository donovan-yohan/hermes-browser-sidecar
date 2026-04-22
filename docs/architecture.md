# Architecture Recommendation

## Chosen Direction

Target a hybrid architecture:

- the extension talks only to a local `hermes-browser-sidecar` service
- that service exposes a stable sidecar protocol owned by this repository
- the first concrete adapter uses Hermes Agent's existing browser bridge for practical compatibility
- a later adapter can use Hermes Agent's OpenAI-compatible API server where the browser bridge is not required

This keeps the user-facing client simple while preventing Hermes gateway internals from becoming the public browser contract.

## Why Not Bind Directly To The Current Browser Bridge

The current Hermes browser bridge is productive, but it is tightly coupled to gateway session internals and sidecar-specific action strings. The current extension depends on custom routes and actions such as:

- `POST /inject`
- `POST /session`
- `action=state|inspect|list|reset|interrupt|send|send_async`
- `action=tts|transcribe_audio|runtime_config_get|runtime_config_save|runtime_provider_models|recall_search`

That surface is not transport-neutral. It also bakes current page-context packaging and sidecar session rules directly into Hermes gateway code.

## Why Not Bind Directly To The OpenAI-Compatible API Server

The Hermes API server is a cleaner long-term integration seam, but it currently provides generic agent chat surfaces rather than browser-sidecar surfaces. It supports:

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `GET /v1/models`
- `GET /health`

That is useful for generic chat UIs, but not enough by itself for the current sidecar UX. Missing pieces include:

- explicit browser-sidecar session discovery and reset
- interrupt semantics tied to the side panel
- page-context bundling rules
- media and transcript helper flows
- runtime config helpers currently used by the Hermes extension

## Stable Boundary For This Repo

The public boundary for this repo should be a small local HTTP protocol that the extension can trust regardless of the upstream Hermes transport:

- `GET /health`
- `GET /v1/capabilities`
- future `GET /v1/session/state`
- future `POST /v1/session/send`
- future `POST /v1/session/reset`
- future `POST /v1/session/interrupt`

The extension should render based on declared capabilities instead of assuming bridge-only features exist.

## Ownership Split

### Extension

- render side-panel UI
- collect browser-local signals
- send sidecar requests to the local sidecar service
- avoid embedding Hermes-specific action names or bridge auth conventions

### Local Sidecar Service

- expose a stable protocol for the extension
- normalize config and capability reporting
- translate sidecar requests into upstream Hermes transport calls
- keep Hermes-specific tokens and transport details out of the extension where practical

### Hermes Adapters

- `bridge` adapter: bridge-first compatibility with today's Hermes sidecar behavior
- `api_server` adapter: future generic Hermes integration path
- `hybrid` mode: capability-driven routing, bridge for sidecar-only operations, API server where generic chat suffices

## Current Implementation Scope

This scaffold only implements:

- configuration loading
- upstream probe logic
- a tiny sidecar service with `health` and `capabilities`
- a minimal MV3 extension that exercises those endpoints

It does not implement full session transport yet.

