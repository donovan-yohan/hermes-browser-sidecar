# TODO

## Phase 2 — Browser context & attachments
- Attachments / image / transcript flow over the public protocol (capabilities
  currently false on both adapters).
- Confirm bridge response shape against `gateway/browser_bridge.py` and remove
  the captured-from-observation comment in `transports/bridge.py`.
- Confirm Responses API output shape (`output[*].content[*].text`) against the
  Hermes API server source and tighten `_extract_assistant_text`.

## Phase 3 — API server parity
- Implement transcript fetch / PDF preview helpers on `api_server.py`.
- Add a streaming variant of `send_message` for the Responses API.
- Persist the API-server `_sessions` map across restarts (file or sqlite).

## Phase 4 — Hardening
- Local sidecar auth: shared-secret header negotiated via the extension at
  install time.
- Integration test harness against a live Hermes process.
- Packaging: ship as a single binary or pip-installable launcher.
- Docs for supported Hermes versions and compatibility risks.
