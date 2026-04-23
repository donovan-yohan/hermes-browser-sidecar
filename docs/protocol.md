# Sidecar Public Protocol (`/v1`)

`PROTOCOL_VERSION = "1.0"`. All wire payloads use snake_case JSON. Upstream
Hermes naming (camelCase, action-tagged RPCs, Responses-API shape) lives
entirely inside `transports/` and never appears in any response below.

The sidecar listens on `http://127.0.0.1:8787` by default. CORS is restricted
to `chrome-extension://*` origins; other origins receive no
`Access-Control-Allow-Origin` header.

## Routes

| Method  | Path                    | Description                                |
|---------|-------------------------|--------------------------------------------|
| OPTIONS | any                     | CORS preflight (204)                       |
| GET     | `/health`               | Service health, transport mode, upstream probe, capabilities, notes |
| GET     | `/v1/capabilities`      | Capability declaration                     |
| GET     | `/v1/session/state`     | Current session snapshot                   |
| GET     | `/v1/sessions`          | Local session list                         |
| POST    | `/v1/session/send`      | Submit a turn                              |
| POST    | `/v1/session/reset`     | Drop session, return fresh state           |
| POST    | `/v1/session/interrupt` | Cancel active turn                         |

## Common types

```jsonc
SidecarSession {
  "session_id": "panel-1",        // client-issued UUID, panel-scoped
  "session_key": "<opaque>",      // server-issued resume token; "" if none
  "messages": [SidecarMessage],
  "progress": SidecarProgress,
  "updated_at": "2026-04-22T18:00:00Z"
}

SidecarMessage {
  "role": "user" | "assistant" | "system",
  "content": "...",
  "timestamp": "2026-04-22T18:00:00Z",
  "kind": "text" | "page_context" | "image" | "tool_call",
  "metadata": { ... }              // optional
}

SidecarProgress {
  "running": false,
  "error": null,                   // string when failed, null otherwise
  "detail": ""
}

PageContext {
  "title": "...",
  "url": "...",
  "selection": "...",
  "page_text": "...",
  "content_kind": "webpage" | "pdf",
  "metadata": { ... }
}

SidecarError {
  "code": "invalid_request" | "not_supported" | "upstream_unavailable" |
          "upstream_error" | "session_not_found" | "internal_error",
  "message": "...",
  "detail": { ... }                // optional
}
```

## GET /health → 200

```json
{
  "ok": true,
  "service": "hermes-browser-sidecar",
  "protocol_version": "1.0",
  "transport": {"mode": "hybrid", "active_adapter": "bridge"},
  "sidecar": {"base_url": "http://127.0.0.1:8787"},
  "upstream": {
    "name": "bridge", "ok": true, "endpoint": "http://127.0.0.1:8765/health",
    "status_code": 200, "detail": "...", "payload": { ... }
  },
  "capabilities": { ...Capabilities },
  "notes": ["Local sidecar service has no authentication; bind to 127.0.0.1 only."]
}
```

## GET /v1/capabilities → 200

```json
{
  "ok": true,
  "service": "hermes-browser-sidecar",
  "protocol_version": "1.0",
  "capabilities": {
    "health_check": true,
    "capability_discovery": true,
    "session_state": true,
    "session_list": true,
    "session_send": true,
    "session_reset": true,
    "session_interrupt": true,
    "page_context": true,
    "attachments": false,
    "tts": false,
    "stt": false
  }
}
```

In hybrid mode the capability set is the union of the active adapter and the
fallback adapter — the extension can rely on a flag being true if any
reachable adapter supports it, and the service routes the request accordingly.

## GET /v1/session/state?session_id=…&session_key=… → 200

```json
{"ok": true, "session": SidecarSession}
```

`session_id` is required (400 if missing). `session_key` is optional and is
the server-issued resume token from a prior response.

## GET /v1/sessions?session_id=…&session_key=…&limit=25 → 200

```json
{"ok": true, "sessions": [SidecarSession, ...], "limit": 25}
```

## POST /v1/session/send → 200

Request:
```json
{
  "session_id": "panel-1",
  "session_key": "...",
  "message": "Tell me about this page.",
  "page_context": PageContext   // optional
}
```

Response: `{"ok": true, "session": SidecarSession}` reflecting the new
assistant message and updated progress.

## POST /v1/session/reset → 200, /v1/session/interrupt → 200

Request:
```json
{"session_id": "panel-1", "session_key": "..."}
```

Response: `{"ok": true, "session": SidecarSession}`.

## Errors

```json
{"ok": false, "error": SidecarError}
```

| Status | code                    | When                                                         |
|--------|-------------------------|--------------------------------------------------------------|
| 400    | `invalid_request`       | missing/invalid field, non-JSON body                         |
| 404    | `session_not_found`     | interrupt against a session never opened                     |
| 404    | `not_found`             | unknown route                                                |
| 500    | `internal_error`        | unexpected server-side fault                                 |
| 501    | `not_supported`         | active transport doesn't support this operation              |
| 502    | `upstream_unavailable`  | upstream Hermes endpoint unreachable                         |
| 502    | `upstream_error`        | upstream returned a non-success HTTP status                  |

## Versioning

- Path-based versioning: routes live under `/v1/`. Future breaking changes
  ship as `/v2/`.
- `protocol_version` field on `/health` and `/v1/capabilities` reports the
  minor version; clients should rely on capability flags rather than the
  version string for feature detection.
- New optional fields may be added to existing types; clients must ignore
  unknown fields.

## Known limitations (v1.0)

- No authentication on the local sidecar; bind to `127.0.0.1` only.
- API-server adapter session state is in-memory and lost on restart.
- API-server `interrupt` issues `DELETE /v1/responses/{id}` — may only
  cancel storage rather than in-flight generation depending on the upstream
  Responses API behaviour.
- `attachments`, `tts`, `stt` capabilities are reserved but not implemented
  by either adapter.
