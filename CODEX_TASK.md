# Codex task: hermes-browser-sidecar investigation + scaffold

Context:
- Target repo: /Users/donovanyohan/Documents/Programs/personal/hermes-browser-sidecar
- Source fork to inspect: /tmp/hermes-agent-main
- Relevant source paths:
  - /tmp/hermes-agent-main/browser-extension/
  - /tmp/hermes-agent-main/gateway/browser_bridge.py
  - /tmp/hermes-agent-main/gateway/platforms/api_server.py
  - /tmp/hermes-agent-main/browser-extension/README.md
  - /tmp/hermes-agent-main/README.md
  - /tmp/hermes-agent-main/website/docs/user-guide/messaging/open-webui.md

Goal:
Create an initial public scaffold for a portable project called `hermes-browser-sidecar` that combines:
1. a browser extension (Chrome/Chromium MV3 side panel client), and
2. a Python backend module/service for the local bridge / Hermes integration.

Primary research question:
- Given Hermes Agent’s existing architecture, should this project target:
  - the existing browser bridge pattern,
  - the OpenAI-compatible API server,
  - or a hybrid path where the extension is transport-agnostic but the first backend uses today’s bridge?

What to do:
1. Inspect the source fork and summarize the actual existing API / transport surfaces relevant to a browser sidecar.
2. Produce a recommendation doc that compares:
   - current browser bridge coupling,
   - API-server-based approach,
   - hybrid architecture.
3. Scaffold this repo for the recommended path, but keep the implementation conservative.
4. Do NOT try to fully port the whole sidecar yet. This run is for investigation, structure, and starter code only.

Expected outputs:
- `README.md`
- `docs/architecture.md`
- `docs/investigation.md`
- `docs/extraction-plan.md`
- a sane starter directory layout, probably something like:
  - `extension/`
  - `python/` or `packages/python/hermes_browser_sidecar/`
- minimal Python packaging scaffold
- minimal browser extension scaffold or copied baseline manifest/assets only if clearly appropriate
- `TODO.md` with next concrete steps

Constraints:
- Prefer clarity over pretending the extraction is already solved.
- Call out unstable/private Hermes integration seams explicitly.
- If you copy source material, keep it minimal and note provenance.
- Do not push anything.
- You may make local commits if useful, but it is not required.

Decision bias:
- We currently suspect the right long-term architecture is a hybrid leaning toward:
  - extension as dumb client,
  - stable sidecar protocol/backend boundary,
  - eventual use of Hermes API server where feasible,
  - but practical compatibility with today’s browser bridge and gateway internals.

When done:
- leave the repo in a readable scaffolded state
- print a short summary of what you created and the chosen architecture recommendation
