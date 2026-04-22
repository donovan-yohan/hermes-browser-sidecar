const DEFAULT_BACKEND_URL = "http://127.0.0.1:8787";
const CLIENT_SESSION_ID_KEY = "clientSessionId";

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
    includePageByDefault: patch?.includePageByDefault !== false
  };
  await chrome.storage.sync.set(next);
  return next;
}

async function ensureClientSessionId() {
  const stored = await chrome.storage.local.get({ [CLIENT_SESSION_ID_KEY]: "" });
  const existing = String(stored[CLIENT_SESSION_ID_KEY] || "").trim();
  if (existing) {
    return existing;
  }

  const generated =
    typeof crypto?.randomUUID === "function"
      ? crypto.randomUUID()
      : `panel-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  await chrome.storage.local.set({ [CLIENT_SESSION_ID_KEY]: generated });
  return generated;
}

function resolveUrl(baseUrl, pathname, query = {}) {
  const url = new URL(baseUrl);
  url.pathname = pathname;
  url.search = "";
  url.hash = "";
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

async function requestJson(pathname, { method = "GET", query, body } = {}) {
  const settings = await getSettings();
  const requestInit = {
    method,
    headers: {}
  };

  if (body !== undefined) {
    requestInit.headers["Content-Type"] = "application/json";
    requestInit.body = JSON.stringify(body);
  }

  const response = await fetch(resolveUrl(settings.backendUrl, pathname, query), requestInit);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Request failed with status ${response.status}.`);
  }
  return payload;
}

function clampText(value, limit) {
  const text = String(value || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  return text.length > limit ? text.slice(0, limit).trimEnd() : text;
}

function extractPageContextInPage() {
  const selection = window.getSelection ? window.getSelection().toString() : "";
  const rawText = document.body?.innerText || document.body?.textContent || "";
  const normalizedText = rawText.replace(/\n{3,}/g, "\n\n");
  const contentType = String(document.contentType || "").toLowerCase();
  const isPdf = contentType.includes("pdf") || location.href.toLowerCase().includes(".pdf");

  return {
    title: clampText(document.title || "", 512),
    url: clampText(location.href || "", 2048),
    selection: clampText(selection, 8000),
    pageText: clampText(normalizedText, 24000),
    contentKind: isPdf ? "pdf" : "webpage",
    metadata: {
      pageTextSource: "document-body"
    }
  };
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  return tabs[0] || null;
}

async function getPageContext() {
  const tab = await getActiveTab();
  if (!tab) {
    throw new Error("No active tab is available.");
  }

  const fallback = {
    title: String(tab.title || "").trim(),
    url: String(tab.url || "").trim(),
    selection: "",
    pageText: "",
    contentKind: "webpage",
    metadata: {
      pageTextSource: "tab-fallback"
    }
  };

  if (!tab.id) {
    return fallback;
  }

  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPageContextInPage
    });
    const extracted = results?.[0]?.result || {};
    return {
      ...fallback,
      ...extracted,
      title: String(extracted.title || fallback.title || "").trim(),
      url: String(extracted.url || fallback.url || "").trim()
    };
  } catch (error) {
    return {
      ...fallback,
      metadata: {
        ...fallback.metadata,
        extractionError: String(error?.message || error)
      }
    };
  }
}

async function getSessionState(sessionKey = "") {
  const clientSessionId = await ensureClientSessionId();
  return requestJson("/v1/session/state", {
    query: {
      client_session_id: clientSessionId,
      session_key: sessionKey
    }
  });
}

async function listSessions(sessionKey = "") {
  const clientSessionId = await ensureClientSessionId();
  return requestJson("/v1/sessions", {
    query: {
      client_session_id: clientSessionId,
      session_key: sessionKey
    }
  });
}

async function sendMessage({ message = "", sessionKey = "", includePage = false } = {}) {
  const clientSessionId = await ensureClientSessionId();
  const body = {
    client_session_id: clientSessionId,
    session_key: String(sessionKey || "").trim(),
    message: String(message || "").trim()
  };

  if (includePage) {
    body.page_context = await getPageContext();
  }

  if (!body.message && !body.page_context) {
    throw new Error("Add a message or include the current page.");
  }

  return requestJson("/v1/session/send", {
    method: "POST",
    body
  });
}

async function resetChat(sessionKey = "") {
  const clientSessionId = await ensureClientSessionId();
  return requestJson("/v1/session/reset", {
    method: "POST",
    body: {
      client_session_id: clientSessionId,
      session_key: String(sessionKey || "").trim()
    }
  });
}

async function interruptChat(sessionKey = "") {
  const clientSessionId = await ensureClientSessionId();
  return requestJson("/v1/session/interrupt", {
    method: "POST",
    body: {
      client_session_id: clientSessionId,
      session_key: String(sessionKey || "").trim()
    }
  });
}

chrome.runtime.onInstalled.addListener(async () => {
  await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    if (message?.type === "sidecar:get-settings") {
      sendResponse({ ok: true, result: await getSettings() });
      return;
    }

    if (message?.type === "sidecar:save-settings") {
      sendResponse({ ok: true, result: await saveSettings(message.payload || {}) });
      return;
    }

    if (message?.type === "sidecar:check-health") {
      sendResponse({ ok: true, result: await requestJson("/health") });
      return;
    }

    if (message?.type === "sidecar:get-capabilities") {
      sendResponse({ ok: true, result: await requestJson("/v1/capabilities") });
      return;
    }

    if (message?.type === "sidecar:get-page-context") {
      sendResponse({ ok: true, result: await getPageContext() });
      return;
    }

    if (message?.type === "sidecar:get-session-state") {
      sendResponse({ ok: true, result: await getSessionState(message.sessionKey || "") });
      return;
    }

    if (message?.type === "sidecar:list-sessions") {
      sendResponse({ ok: true, result: await listSessions(message.sessionKey || "") });
      return;
    }

    if (message?.type === "sidecar:send-message") {
      sendResponse({ ok: true, result: await sendMessage(message.payload || {}) });
      return;
    }

    if (message?.type === "sidecar:reset-chat") {
      sendResponse({ ok: true, result: await resetChat(message.sessionKey || "") });
      return;
    }

    if (message?.type === "sidecar:interrupt") {
      sendResponse({ ok: true, result: await interruptChat(message.sessionKey || "") });
      return;
    }

    sendResponse({ ok: false, error: "Unsupported message type." });
  })().catch((error) => {
    sendResponse({ ok: false, error: String(error?.message || error) });
  });

  return true;
});
