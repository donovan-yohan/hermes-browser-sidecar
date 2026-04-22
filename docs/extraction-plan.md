# Extraction Plan

## Phase 0: Investigation And Public Scaffold

- publish the architecture recommendation
- define the stable sidecar boundary
- create a minimal backend package
- create a minimal MV3 extension shell
- keep all session operations explicitly out of scope for now

## Phase 1: Bridge-Backed Sidecar Protocol

- implement `GET /v1/session/state`
- implement `GET /v1/sessions`
- implement `POST /v1/session/send`
- implement `POST /v1/session/reset`
- implement `POST /v1/session/interrupt`
- map stable protocol objects onto Hermes bridge actions

## Phase 2: Browser Context Packaging

- tighten page-context normalization and truncation rules
- decide which extraction stays in the extension and which moves server-side
- add attachment and transcript flow tests

## Phase 3: API Server Integration

- introduce an API-server adapter
- keep local session ownership in the sidecar service
- use capability gating to route generic chat through the API server when feasible

## Phase 4: Hardening

- auth story for local sidecar service
- integration tests against live Hermes processes
- packaging and developer setup
- documentation for supported Hermes versions and known compatibility risks
