# Browser Sidecar Ownership and Public Protocol

- Status: proposed
- Date: 2026-04-22
- Repo: `hermes-browser-sidecar`
- Paired sidecar PR: <https://github.com/donovan-yohan/hermes-browser-sidecar/pull/1>
- Paired Hermes PR: <https://github.com/donovan-yohan/hermes-agent/pull/4>

## Summary

This repo should stop behaving like a thin wrapper around Hermes private bridge payloads and start owning a real browser-sidecar product boundary.

After cleanup, this repository should own:

1. the browser extension UX and browser-local signal collection
2. the local standalone sidecar service and its public `http://127.0.0.1/.../v1` protocol
3. transport adapters that translate that public protocol into Hermes-specific upstream calls
4. install/setup UX for running the sidecar in standalone mode
5. optional Hermes plugin extras for tighter in-tree integration when Hermes is present

This repository should **not** pretend it can replace Hermes session ownership today. Hermes still owns the actual agent runtime, execution, and session state. The sidecar depends on a **small Hermes core seam** for ingress into Hermes-managed sessions, but this repo must own everything above that seam that is browser-specific.

The current `hybrid` naming is misleading unless it becomes real capability-based multi-transport routing. Today, `python/src/hermes_browser_sidecar/service.py` falls back to the bridge adapter for `hybrid`, so the mode is effectively bridge-first compatibility rather than genuine routing.

## Why this spec exists

Earlier architecture review conclusion:

- this repo is too thin today
- it mostly wraps Hermes private bridge payloads
- that means the repo does not yet own a stable public contract

Earlier plugin review conclusion:

- this repo can own much more out of tree
- but Hermes general plugins alone are not the right primary seam
- this repo should own the extension, local `/v1` protocol, transport adapters, and install/setup UX
- optional Hermes plugin extras are acceptable, but they are secondary
- the main dependency should be a small Hermes core ingress seam rather than broad coupling to Hermes bridge internals

This spec preserves those conclusions and turns them into an implementation direction for future refactors.

## Current evidence in this repo

### The repo already has the beginnings of the right boundary

- `python/src/hermes_browser_sidecar/server.py` exposes local routes like `/health`, `/v1/capabilities`, `/v1/session/state`, `/v1/sessions`, `/v1/session/send`, `/v1/session/reset`, and `/v1/session/interrupt`
- `extension/background.js` talks to the local sidecar service instead of Hermes directly
- `extension/sidepanel.js` renders UI from the sidecar responses instead of building Hermes HTTP calls itself
- `python/src/hermes_browser_sidecar/transports/bridge.py` hides Hermes bridge auth headers and Hermes action names from the extension

### The repo is still too coupled to Hermes private payloads

- `python/src/hermes_browser_sidecar/transports/bridge.py` still emits Hermes bridge-specific action names like `state`, `list`, `send`, `reset`, and `interrupt`
- `python/src/hermes_browser_sidecar/service.py` largely returns transport payloads with minimal normalization
- `extension/sidepanel.js` still assumes message/session shapes that reflect current Hermes bridge output conventions
- image handling in `extension/sidepanel.js` still expects `media_url` style data from Hermes-side conventions
- the local protocol is currently underspecified in docs and not yet clearly versioned as a repo-owned contract
- `hybrid` is named in `README.md`, `docs/architecture.md`, and `python/src/hermes_browser_sidecar/service.py`, but it is not yet real multi-transport routing

## Decision

This repo should own a **standalone browser sidecar product boundary** with the following layering:

### Layer 1: extension-owned browser UX

Owned here:

- `extension/background.js`
- `extension/sidepanel.js`
- `extension/options.js`
- extension manifest and assets

Responsibilities:

- render UI
- collect browser-local context from tabs, page selection, DOM text, screenshots, or media handles when supported
- persist browser-local settings
- call only the sidecar's local public protocol
- render based on declared capabilities, not transport assumptions

Explicitly not owned by the extension:

- Hermes bridge action names
- Hermes bearer token details
- Hermes route names like `/inject` or `/session`
- local filesystem media path conventions
- Hermes-specific session payload shapes

### Layer 2: sidecar-owned local public protocol

Owned here:

- `python/src/hermes_browser_sidecar/server.py`
- `python/src/hermes_browser_sidecar/protocol.py`
- future protocol docs in `docs/`

Responsibilities:

- define the stable localhost HTTP contract
- validate requests and normalize responses
- expose capability discovery
- expose browser-sidecar concepts like page context, session status, attachments, media references, and local install health
- shield the extension from upstream transport differences

This is the primary public seam for this repo.

### Layer 3: sidecar-owned transport adapters

Owned here:

- `python/src/hermes_browser_sidecar/transports/bridge.py`
- `python/src/hermes_browser_sidecar/transports/api_server.py`
- future adapters under `python/src/hermes_browser_sidecar/transports/`

Responsibilities:

- translate sidecar public requests into Hermes-compatible upstream operations
- probe upstream availability
- map Hermes-specific errors into sidecar protocol errors
- normalize upstream payloads into sidecar-owned response shapes

Transport adapters are internal implementation details. Their wire formats are **not** this repo's public contract.

### Layer 4: optional Hermes plugin extras

Allowed here, but secondary.

Possible ownership:

- pip entry point registration for Hermes discovery
- helper commands to launch the standalone sidecar from Hermes install/setup flows
- optional adapters that use Hermes in-process hooks when Hermes is installed locally

Non-decision:

- do not make Hermes plugin transport registration the primary integration boundary
- do not require Hermes plugin loading for the extension to work
- do not collapse the sidecar service into a mere Hermes plugin shim

The standalone sidecar service remains the product. Plugin extras are convenience packaging.

## Required ownership boundary after cleanup

After refactor, this repo should own these repo-level concerns end to end.

### 1. Browser extension product surface

Own:

- sidepanel interaction model
- options page
- capability-driven feature gating
- collection of browser-local context
- browser permission prompts and UX
- browser install docs

Do not delegate these to Hermes core.

### 2. Public local `/v1` protocol

Own:

- route names
- request/response schemas
- protocol versioning
- error shapes
- capability schema
- normalization rules for messages, media references, progress, and session summaries

Do not expose Hermes bridge payloads as if they were already the public protocol.

### 3. Transport and routing layer

Own:

- adapter selection
- adapter probing
- capability computation
- future multi-transport routing
- mapping between sidecar protocol and Hermes ingress seam

### 4. Install and setup UX

Own:

- how a user starts the service
- standalone install mode
- Hermes-paired install mode
- environment variables and defaults for sidecar operation
- troubleshooting docs for local service, extension connection, and upstream Hermes connectivity

### 5. Optional plugin extras

Own, if added:

- optional packaging metadata in `pyproject.toml`
- optional Hermes plugin entry points
- convenience startup hooks

But document them as optional extras, not as the core API.

## Hermes core seam this repo depends on

This repo depends on a **small Hermes ingress seam**, not on broad Hermes browser-private semantics leaking upward.

### What the Hermes seam should provide

At minimum, Hermes core should provide a stable ingress surface that lets the sidecar:

- create or resolve a Hermes-backed browser session handle
- send a user turn plus optional structured context
- query session state/progress/messages
- interrupt a running turn
- reset or create a fresh session
- optionally expose model/runtime capability information

That seam can be implemented behind a bridge route, an internal API surface, or a plugin hook, but the sidecar should target it as a small semantic interface rather than bind directly to private action strings everywhere.

### What this repo should not claim today

This repo does **not** own:

- the underlying Hermes session lifecycle implementation
- the agent runtime execution engine
- provider/model orchestration
- cross-client session arbitration inside Hermes core

So the sidecar cannot honestly claim to replace Hermes session ownership today. It should instead define a clean browser-facing surface above a narrow Hermes ingress seam.

## Public local `/v1` contract

The public contract should remain small, explicit, and repo-owned.

### Versioning

- Keep a protocol version field, currently modeled in `python/src/hermes_browser_sidecar/protocol.py`
- Treat breaking schema changes as protocol version changes
- Do not use upstream Hermes bridge payload versioning as a substitute for sidecar protocol versioning

### Minimum route set

These existing routes are the correct baseline:

- `GET /health`
- `GET /v1/capabilities`
- `GET /v1/session/state`
- `GET /v1/sessions`
- `POST /v1/session/send`
- `POST /v1/session/reset`
- `POST /v1/session/interrupt`

### Direction for request/response ownership

#### `GET /health`

Purpose:

- local service health
- active transport selection
- upstream reachability summary
- install/debug information

Must remain sidecar-owned and safe for UI troubleshooting.

#### `GET /v1/capabilities`

Purpose:

- declare feature support without the UI inferring from adapter names

Expected shape direction:

- protocol version
- service name
- active adapter
- capabilities map
- optional transport summaries
- optional install mode summary

Capabilities should describe user-visible behavior, for example:

- `session_state`
- `session_list`
- `session_send`
- `session_reset`
- `session_interrupt`
- `page_context`
- `attachments`
- `tts`
- `stt`
- `screenshots`
- `image_rendering`
- `multi_transport_routing`

Do not force the UI to branch on raw transport names like `bridge` vs `api_server` for feature support.

#### `GET /v1/session/state`

Purpose:

- fetch the normalized current session view for the side panel

Should return a sidecar-owned session state object, not a raw Hermes bridge payload. Normalize:

- `session_key`
- `session_id`
- `title` if available
- `messages[]`
- `progress`
- `capabilities` or per-session affordances if needed
- `upstream_status` if useful for debugging

#### `GET /v1/sessions`

Purpose:

- list recent sessions in a sidecar-owned summary format

Do not simply proxy Hermes list payloads.

#### `POST /v1/session/send`

Purpose:

- send a user message and optional structured browser context

Request direction:

```json
{
  "client_session_id": "browser-generated-id",
  "session_key": "optional-stable-sidecar-session-key",
  "message": "optional-text",
  "page_context": {
    "title": "...",
    "url": "...",
    "selection": "...",
    "pageText": "...",
    "contentKind": "webpage",
    "metadata": {}
  }
}
```

Rules:

- allow message-only
- allow page-context-only
- validate size and field types at the sidecar boundary
- map to Hermes ingress input internally

#### `POST /v1/session/reset`

Purpose:

- clear or create a fresh browser-sidecar session on the current Hermes-backed channel

Should return normalized session state.

#### `POST /v1/session/interrupt`

Purpose:

- interrupt the active turn if supported

Should return normalized session state or normalized progress.

### Error model

The sidecar should own its own error envelope. Practical direction:

```json
{
  "ok": false,
  "error": {
    "code": "upstream_unavailable",
    "message": "Hermes browser ingress is not reachable.",
    "retryable": true,
    "details": {}
  }
}
```

Avoid raw passthrough of Hermes error strings as the only surface.

## Capability-driven UI and normalization boundaries

### UI must be capability-driven

`extension/sidepanel.js` should render features based on `GET /v1/capabilities`, not based on assumptions about the current adapter.

Examples:

- show interrupt button only when `session_interrupt` is available
- show page-context controls only when `page_context` is available
- hide TTS/STT controls until capabilities announce them
- hide session list affordances when `session_list` is false
- eventually support richer rendering only when `attachments` or `image_rendering` is true

### Normalization belongs in the sidecar, not the extension

The extension should not need to know:

- whether upstream called the message kind `page_context` or something else
- whether image URLs are filesystem paths, local service URLs, or Hermes-generated references
- whether progress came from bridge polling, server-sent events, or API responses
- whether a session key maps directly to a Hermes session id

The sidecar should normalize:

- message role/kind/content fields
- progress state and status text
- attachment/media reference format
- session summary shape
- request validation and truncation limits

### Browser-local normalization stays in the extension

The extension still owns collection-time normalization for browser-only raw inputs, such as:

- DOM text extraction
- selection extraction
- tab metadata fallback
- browser permission failures

But once the data crosses the local `/v1` boundary, the sidecar owns semantic normalization.

## Transport and capability layering direction

### Immediate direction

Keep the current local protocol and adapter structure, but make the layering honest:

- `bridge` = compatibility adapter to the current Hermes browser bridge
- `api_server` = future adapter for Hermes generic API server flows where possible
- `hybrid` = reserved for actual multi-transport routing only

### Rule for `hybrid`

Do not describe `hybrid` as implemented until `python/src/hermes_browser_sidecar/service.py` actually routes per capability or per operation.

A real `hybrid` mode would do things like:

- session management via Hermes bridge ingress
- generic chat turn submission via API server when parity exists
- capability probe decides which operations are supported by which adapter
- local sidecar chooses the adapter per operation and still returns one normalized response format

Until then, document the current mode as bridge-first compatibility or rename it.

### Transport matrix direction

This repo should eventually document a matrix roughly like:

| Operation | Public sidecar route | Bridge adapter | API server adapter | Hybrid routing |
|---|---|---:|---:|---:|
| health | `/health` | yes | yes | yes |
| capabilities | `/v1/capabilities` | yes | yes | yes |
| session state | `/v1/session/state` | yes | partial/no today | bridge |
| list sessions | `/v1/sessions` | yes | no today | bridge |
| send text turn | `/v1/session/send` | yes | partial future | route by capability |
| send page context | `/v1/session/send` | yes | no today | bridge until parity |
| reset | `/v1/session/reset` | yes | no today | bridge |
| interrupt | `/v1/session/interrupt` | yes | no today | bridge |
| attachments/TTS/STT | future `/v1/...` | future | future | route by capability |

## Fake-modularity warnings

### Warning 1: a local proxy is not a product boundary

If `server.py` only renames Hermes routes and `service.py` only forwards transport payloads, the repo is still fake-modular. Moving code out of tree is not enough if the public contract is still just Hermes private payloads in disguise.

### Warning 2: protocol ownership requires schema ownership

If implementers keep returning raw Hermes bridge message/session objects, this repo does not actually own the protocol. It only owns a relay.

### Warning 3: plugin packaging is not architectural separation

Adding a Hermes plugin entry point in `pyproject.toml` does not fix the ownership problem by itself. If the extension still effectively depends on Hermes private bridge semantics, the plugin is only a thinner shim.

### Warning 4: naming `hybrid` is not the same as having routing

If the service always falls back to bridge for all session operations, calling the mode `hybrid` creates false expectations in docs and code review.

## Optional Hermes plugin packaging

Optional plugin extras are acceptable here because they can improve install ergonomics and in-tree discovery, but they must be documented as extras.

### Acceptable forms

- a `pyproject.toml` optional dependency group for Hermes integration helpers
- an optional pip entry point that Hermes can discover
- helper commands that launch `hermes-browser-sidecar serve` with Hermes-aware defaults
- adapters that can import Hermes integration hooks only when available

### Required constraints

- standalone service mode must keep working without plugin registration
- extension must keep talking only to local sidecar `/v1`
- plugin extras must not become the only way to access the sidecar protocol
- plugin extras must not require the extension to understand Hermes internals

### Suggested packaging direction

When this is implemented, prefer naming that makes the layering obvious, for example:

- base package: standalone sidecar service and extension support
- optional extra: `[hermes-plugin]` or similar for Hermes discovery hooks

But keep that packaging clearly secondary in docs.

## Docs that this repo should add after cleanup

Add and maintain repo-owned docs for the boundary this repo claims.

### 1. Ownership doc

Suggested path:

- `docs/ownership.md`

Should explain:

- what this repo owns
- what Hermes core owns
- why the extension only talks to local `/v1`
- what remains dependent on Hermes core today

### 2. Transport matrix

Suggested path:

- `docs/transport-matrix.md`

Should explain:

- `bridge`, `api_server`, and future real `hybrid`
- which operations are supported where
- fallback behavior
- capability computation rules

### 3. Protocol spec

Suggested path:

- `docs/protocol.md`

Should contain:

- routes
- schemas
- examples
- error model
- versioning policy

### 4. Install modes doc

Suggested path:

- `docs/install-modes.md`

Should explain:

- standalone sidecar mode
- Hermes-paired mode
- optional Hermes plugin mode
- extension setup
- environment variables and troubleshooting

### 5. Non-goals doc or section

Suggested path:

- `docs/non-goals.md`
  or section in `docs/ownership.md`

Should say explicitly:

- this repo does not replace Hermes runtime/session core today
- this repo does not standardize all Hermes internals
- this repo does not require API-server parity before shipping bridge-backed value

## Phased refactor plan

These phases are intentionally bite-sized and scoped to concrete file paths.

### Phase 0: document the truthful architecture

Goal:

- make the current bridge-first baseline honest
- define the target ownership boundary before deeper code changes

Tasks:

1. add this spec
   - `docs/superpowers/specs/2026-04-22-browser-sidecar-ownership-and-protocol.md`
2. update repo docs to remove ambiguity around current `hybrid` claims
   - `README.md`
   - `docs/architecture.md`
3. add explicit ownership and non-goals docs
   - `docs/ownership.md`
   - `docs/non-goals.md`
4. add protocol and transport docs
   - `docs/protocol.md`
   - `docs/transport-matrix.md`
   - `docs/install-modes.md`

Verification commands:

```bash
cd /private/tmp/codex-hermes-sidecar-arch-plugin
python3 - <<'PY'
from pathlib import Path
for path in [
    'docs/superpowers/specs/2026-04-22-browser-sidecar-ownership-and-protocol.md',
]:
    p = Path(path)
    print(path, 'exists=', p.exists(), 'size=', p.stat().st_size if p.exists() else 0)
PY
```

### Phase 1: make the protocol explicitly sidecar-owned

Goal:

- move from passthrough-ish payloads to normalized sidecar schemas

Primary file paths:

- `python/src/hermes_browser_sidecar/protocol.py`
- `python/src/hermes_browser_sidecar/service.py`
- `python/src/hermes_browser_sidecar/server.py`

Tasks:

1. centralize schema builders in `protocol.py`
2. define normalized message/session/progress builders
3. define structured error builders
4. have `service.py` return sidecar schemas rather than raw transport dicts
5. keep `server.py` focused on HTTP parsing and status code mapping

Verification commands:

```bash
cd /private/tmp/codex-hermes-sidecar-arch-plugin
python3 -m compileall python/src
PYTHONPATH=python/src python3 -m hermes_browser_sidecar print-config
PYTHONPATH=python/src python3 -m hermes_browser_sidecar probe
```

### Phase 2: isolate Hermes-private translation inside adapters

Goal:

- keep Hermes bridge action names and auth entirely inside adapter code

Primary file paths:

- `python/src/hermes_browser_sidecar/transports/base.py`
- `python/src/hermes_browser_sidecar/transports/bridge.py`
- `python/src/hermes_browser_sidecar/transports/api_server.py`
- `python/src/hermes_browser_sidecar/service.py`

Tasks:

1. define a semantic adapter interface in `transports/base.py`
2. make `bridge.py` map semantic adapter calls to current Hermes bridge actions internally
3. keep adapter outputs normalized before they reach the extension-facing layer
4. implement explicit capability reporting per adapter
5. ensure `api_server.py` returns truthful unsupported-capability states instead of pretending parity

Verification commands:

```bash
cd /private/tmp/codex-hermes-sidecar-arch-plugin
python3 -m compileall python/src
PYTHONPATH=python/src python3 -m hermes_browser_sidecar probe
```

### Phase 3: capability-driven extension cleanup

Goal:

- make the UI depend on sidecar capabilities and normalized response shapes only

Primary file paths:

- `extension/background.js`
- `extension/sidepanel.js`
- `extension/options.js`

Tasks:

1. fetch and cache `/v1/capabilities` on panel load
2. gate UI controls by capabilities instead of hardcoded assumptions
3. stop assuming Hermes-shaped `messages` or `images` payloads
4. route all media rendering through sidecar-owned normalized fields
5. treat adapter names as diagnostics, not behavior switches

Verification steps:

- load unpacked extension from `extension/`
- confirm the side panel still loads against the local sidecar service
- confirm missing capabilities hide or disable unsupported controls
- confirm page-context-only send still works when `page_context` is enabled

Practical command support:

```bash
cd /private/tmp/codex-hermes-sidecar-arch-plugin
python3 -m http.server >/dev/null 2>&1 || true
```

Manual browser verification is still required for MV3 UX.

### Phase 4: make `hybrid` real or rename it

Goal:

- eliminate misleading transport naming

Primary file paths:

- `python/src/hermes_browser_sidecar/service.py`
- `python/src/hermes_browser_sidecar/config.py`
- `README.md`
- `docs/architecture.md`
- `docs/transport-matrix.md`

Tasks:

Option A, preferred if routing work is ready:

1. implement per-operation routing in `service.py`
2. compute capabilities from combined adapter support
3. expose `multi_transport_routing: true` only when real routing exists

Option B, if routing is not ready:

1. rename current `hybrid` to `bridge_first` or equivalent
2. update docs and defaults to match reality

Verification commands:

```bash
cd /private/tmp/codex-hermes-sidecar-arch-plugin
PYTHONPATH=python/src python3 -m hermes_browser_sidecar print-config
PYTHONPATH=python/src python3 -m hermes_browser_sidecar probe
```

### Phase 5: optional Hermes plugin extras

Goal:

- improve Hermes-side ergonomics without changing the primary boundary

Primary file paths:

- `pyproject.toml`
- `python/src/hermes_browser_sidecar/cli.py`
- optional new files under `python/src/hermes_browser_sidecar/`

Tasks:

1. add optional packaging metadata for Hermes plugin discovery if needed
2. keep base install usable without Hermes plugin registration
3. add docs for optional Hermes-paired setup
4. if Hermes plugin hooks are added, keep them as a launcher/integration convenience layer above the same local `/v1` service

Verification commands:

```bash
cd /private/tmp/codex-hermes-sidecar-arch-plugin
python3 -m pip install -e .
hermes-browser-sidecar print-config
hermes-browser-sidecar probe
```

## Implementation notes tied to current files

### `python/src/hermes_browser_sidecar/server.py`

Keep this file thin.

Good responsibilities:

- parse HTTP
- validate primitive request shape
- map service exceptions to HTTP status codes
- write JSON responses and CORS headers

Do not let this file become the place where Hermes bridge payload semantics leak into the public API.

### `python/src/hermes_browser_sidecar/service.py`

This should become the main orchestration layer for:

- adapter selection
- capability aggregation
- normalized response building
- future hybrid routing

Today it is too close to passthrough behavior. Refactor toward sidecar-owned DTO builders.

### `python/src/hermes_browser_sidecar/protocol.py`

This should become the canonical home for:

- protocol version
- capability schema
- health payload schema
- normalized session/message/progress schema builders
- error envelope builders

### `python/src/hermes_browser_sidecar/transports/bridge.py`

This file is the right place to keep Hermes-private details like:

- `/inject`
- `/session`
- bearer token headers
- action names such as `state`, `list`, `send`, `reset`, and `interrupt`

But those details must stop escaping upward as the public contract.

### `python/src/hermes_browser_sidecar/transports/api_server.py`

Keep this adapter truthful and partial until parity is real. It is better to return honest capability limitations than to claim support it does not have.

### `extension/background.js`

This file should remain a browser-local service client and page-context collector. It should not become a second transport adapter.

### `extension/sidepanel.js`

This file should render normalized sidecar state. It should not know whether the upstream session came from Hermes bridge, API server, or future routing.

## Non-goals

This spec does not require this repo to:

- reimplement Hermes agent runtime logic
- fully replace Hermes session ownership
- achieve full API-server parity before shipping a bridge-backed sidecar
- standardize every future browser feature up front
- keep misleading names if they no longer match reality

## Acceptance criteria for the intended end state

The refactor direction is successful when all of the following are true:

1. the extension only talks to local sidecar `/v1` routes
2. the extension does not know Hermes bridge action names, bearer token conventions, or local media path rules
3. `bridge` and `api_server` are internal adapters, not public protocol variants
4. `hybrid` is either real per-operation routing or renamed
5. sidecar responses are normalized and versioned here
6. optional Hermes plugin packaging exists only as a secondary integration convenience
7. docs clearly state what this repo owns, what Hermes owns, and the dependency on a small Hermes ingress seam

## Practical next implementation move

If an implementer picks up this repo after the paired PR reviews, the first meaningful step should be:

1. make the docs truthful
2. define normalized sidecar response builders in `python/src/hermes_browser_sidecar/protocol.py`
3. make `python/src/hermes_browser_sidecar/service.py` return those normalized shapes
4. only then expand transport parity or plugin extras

That sequence fixes the ownership boundary first, which is the core problem identified in review.