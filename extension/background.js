const DEFAULT_BACKEND_URL = "http://127.0.0.1:8787";
const DEFAULT_TRANSPORT_MODE = "hybrid";

async function getSettings() {
  const stored = await chrome.storage.sync.get({
    backendUrl: DEFAULT_BACKEND_URL,
    transportMode: DEFAULT_TRANSPORT_MODE
  });

  return {
    backendUrl: String(stored.backendUrl || "").trim() || DEFAULT_BACKEND_URL,
    transportMode: String(stored.transportMode || "").trim() || DEFAULT_TRANSPORT_MODE
  };
}

async function saveSettings(patch) {
  const current = await getSettings();
  const next = {
    backendUrl: String(patch?.backendUrl || current.backendUrl).trim() || DEFAULT_BACKEND_URL,
    transportMode: String(patch?.transportMode || current.transportMode).trim() || DEFAULT_TRANSPORT_MODE
  };
  await chrome.storage.sync.set(next);
  return next;
}

function resolveUrl(baseUrl, pathname) {
  const url = new URL(baseUrl);
  url.pathname = pathname;
  url.search = "";
  url.hash = "";
  return url.toString();
}

async function fetchJson(pathname) {
  const settings = await getSettings();
  const response = await fetch(resolveUrl(settings.backendUrl, pathname), { method: "GET" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Request failed with status ${response.status}.`);
  }
  return payload;
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
      sendResponse({ ok: true, result: await fetchJson("/health") });
      return;
    }

    if (message?.type === "sidecar:get-capabilities") {
      sendResponse({ ok: true, result: await fetchJson("/v1/capabilities") });
      return;
    }

    sendResponse({ ok: false, error: "Unsupported message type." });
  })().catch((error) => {
    sendResponse({ ok: false, error: String(error?.message || error) });
  });

  return true;
});

