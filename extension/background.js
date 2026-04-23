const DEFAULT_BACKEND_URL = "http://127.0.0.1:8787";
const SELECTION_LIMIT = 8000;
const PAGE_TEXT_LIMIT = 24000;
const TITLE_LIMIT = 512;
const URL_LIMIT = 2048;

function clampText(text, limit) {
  const value = String(text || "");
  if (value.length <= limit) return value;
  return value.slice(0, limit);
}

async function getSettings() {
  const stored = await chrome.storage.sync.get({
    backendUrl: DEFAULT_BACKEND_URL,
    includePageByDefault: true
  });
  return {
    backendUrl: String(stored.backendUrl || "").trim() || DEFAULT_BACKEND_URL,
    includePageByDefault: stored.includePageByDefault !== false
  };
}

async function saveSettings(patch) {
  const current = await getSettings();
  const next = {
    backendUrl: String(patch?.backendUrl || current.backendUrl).trim() || DEFAULT_BACKEND_URL,
    includePageByDefault:
      typeof patch?.includePageByDefault === "boolean"
        ? patch.includePageByDefault
        : current.includePageByDefault
  };
  await chrome.storage.sync.set(next);
  return next;
}

async function ensureSessionId() {
  const stored = await chrome.storage.local.get({ sessionId: "" });
  if (stored.sessionId) return stored.sessionId;
  const generated = crypto.randomUUID();
  await chrome.storage.local.set({ sessionId: generated });
  return generated;
}

async function getSessionKey() {
  const stored = await chrome.storage.local.get({ sessionKey: "" });
  return stored.sessionKey || "";
}

async function setSessionKey(value) {
  await chrome.storage.local.set({ sessionKey: String(value || "") });
}

function resolveUrl(baseUrl, pathname, query) {
  const url = new URL(baseUrl);
  url.pathname = pathname;
  url.search = "";
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }
  url.hash = "";
  return url.toString();
}

async function requestJson(method, pathname, { query, body } = {}) {
  const settings = await getSettings();
  const url = resolveUrl(settings.backendUrl, pathname, query);
  const init = { method };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const response = await fetch(url, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload?.error?.message || payload?.error || `Request failed: ${response.status}`;
    const error = new Error(String(message));
    error.code = payload?.error?.code;
    error.status = response.status;
    throw error;
  }
  return payload;
}

function extractPageContextInPage() {
  const selectionText = window.getSelection ? window.getSelection().toString() : "";
  const rawText = (document.body && (document.body.innerText || document.body.textContent)) || "";
  const normalized = rawText.replace(/\n{3,}/g, "\n\n");
  const contentType = String(document.contentType || "").toLowerCase();
  const isPdf = contentType.includes("pdf") || (location.href || "").toLowerCase().endsWith(".pdf");
  return {
    title: document.title || "",
    url: location.href || "",
    selection: selectionText,
    page_text: normalized,
    content_kind: isPdf ? "pdf" : "webpage",
    metadata: { source: "document-body" }
  };
}

async function captureActivePageContext() {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab?.id) return null;
  try {
    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPageContextInPage
    });
    const raw = result?.result;
    if (!raw) return null;
    return {
      title: clampText(raw.title, TITLE_LIMIT),
      url: clampText(raw.url, URL_LIMIT),
      selection: clampText(raw.selection, SELECTION_LIMIT),
      page_text: clampText(raw.page_text, PAGE_TEXT_LIMIT),
      content_kind: String(raw.content_kind || "webpage"),
      metadata: raw.metadata || {}
    };
  } catch (error) {
    return {
      title: clampText(tab.title || "", TITLE_LIMIT),
      url: clampText(tab.url || "", URL_LIMIT),
      selection: "",
      page_text: "",
      content_kind: "webpage",
      metadata: { source: "tab-fallback", reason: String(error?.message || error) }
    };
  }
}

async function maybeStoreSessionKey(payload) {
  const key = payload?.session?.session_key;
  if (typeof key === "string" && key) {
    await setSessionKey(key);
  }
}

async function fetchHealth() {
  return requestJson("GET", "/health");
}

async function fetchCapabilities() {
  return requestJson("GET", "/v1/capabilities");
}

async function fetchSessionState() {
  const [sessionId, sessionKey] = await Promise.all([ensureSessionId(), getSessionKey()]);
  const payload = await requestJson("GET", "/v1/session/state", {
    query: { session_id: sessionId, session_key: sessionKey }
  });
  await maybeStoreSessionKey(payload);
  return payload;
}

async function fetchSessionList() {
  const [sessionId, sessionKey] = await Promise.all([ensureSessionId(), getSessionKey()]);
  return requestJson("GET", "/v1/sessions", {
    query: { session_id: sessionId, session_key: sessionKey }
  });
}

async function sendUserTurn({ message, includePage }) {
  const [sessionId, sessionKey] = await Promise.all([ensureSessionId(), getSessionKey()]);
  const body = { session_id: sessionId, session_key: sessionKey, message };
  if (includePage) {
    const ctx = await captureActivePageContext();
    if (ctx) body.page_context = ctx;
  }
  const payload = await requestJson("POST", "/v1/session/send", { body });
  await maybeStoreSessionKey(payload);
  return payload;
}

async function resetSession() {
  const [sessionId, sessionKey] = await Promise.all([ensureSessionId(), getSessionKey()]);
  const payload = await requestJson("POST", "/v1/session/reset", {
    body: { session_id: sessionId, session_key: sessionKey }
  });
  await setSessionKey("");
  await maybeStoreSessionKey(payload);
  return payload;
}

async function interruptSession() {
  const [sessionId, sessionKey] = await Promise.all([ensureSessionId(), getSessionKey()]);
  return requestJson("POST", "/v1/session/interrupt", {
    body: { session_id: sessionId, session_key: sessionKey }
  });
}

chrome.runtime.onInstalled.addListener(async () => {
  await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

const HANDLERS = {
  "sidecar:get-settings": () => getSettings(),
  "sidecar:save-settings": (msg) => saveSettings(msg.payload || {}),
  "sidecar:check-health": () => fetchHealth(),
  "sidecar:get-capabilities": () => fetchCapabilities(),
  "sidecar:get-session-state": () => fetchSessionState(),
  "sidecar:list-sessions": () => fetchSessionList(),
  "sidecar:send": (msg) => sendUserTurn(msg.payload || {}),
  "sidecar:reset": () => resetSession(),
  "sidecar:interrupt": () => interruptSession(),
  "sidecar:get-page-context": () => captureActivePageContext()
};

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const handler = HANDLERS[message?.type];
  if (!handler) {
    sendResponse({ ok: false, error: "Unsupported message type." });
    return false;
  }
  Promise.resolve()
    .then(() => handler(message))
    .then((result) => sendResponse({ ok: true, result }))
    .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
  return true;
});
