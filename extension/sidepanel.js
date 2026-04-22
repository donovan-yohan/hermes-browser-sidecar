const backendUrlElement = document.getElementById("backend-url");
const transportSummaryElement = document.getElementById("transport-summary");
const sessionIdElement = document.getElementById("session-id");
const pageTitleElement = document.getElementById("page-title");
const pageUrlElement = document.getElementById("page-url");
const pageMetaElement = document.getElementById("page-meta");
const chatMessagesElement = document.getElementById("chat-messages");
const chatInputElement = document.getElementById("chat-input");
const usePageCheckbox = document.getElementById("use-page");
const sendButton = document.getElementById("send-button");
const refreshButton = document.getElementById("refresh-button");
const resetButton = document.getElementById("reset-button");
const interruptButton = document.getElementById("interrupt-button");
const optionsButton = document.getElementById("options-button");
const statusElement = document.getElementById("status");

let activeSessionKey = "";
let pollTimer = null;
let settingsInitialized = false;

function setStatus(message, isError = false) {
  statusElement.textContent = message;
  statusElement.dataset.state = isError ? "error" : "normal";
}

function sendRuntimeMessage(message) {
  return chrome.runtime.sendMessage(message);
}

function clearPollTimer() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function schedulePoll(isRunning) {
  clearPollTimer();
  if (!isRunning) {
    return;
  }
  pollTimer = setTimeout(() => {
    refreshSession().catch((error) => setStatus(String(error?.message || error), true));
  }, 1000);
}

function renderMessage(message) {
  const article = document.createElement("article");
  article.className = `message ${message.role || "assistant"}`;

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent =
    message.role === "user"
      ? message.kind === "page_context"
        ? "You shared page context"
        : "You"
      : "Hermes";
  article.appendChild(meta);

  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = String(message.display_content || message.content || "").trim() || "(empty)";
  article.appendChild(body);

  if (message.kind === "page_context" && (message.page_title || message.page_url)) {
    const detail = document.createElement("div");
    detail.className = "message-detail";
    detail.textContent = [message.page_title, message.page_url].filter(Boolean).join(" • ");
    article.appendChild(detail);
  }

  if (Array.isArray(message.images) && message.images.length) {
    const gallery = document.createElement("div");
    gallery.className = "message-gallery";
    for (const image of message.images) {
      if (!image?.media_url) {
        continue;
      }
      const img = document.createElement("img");
      img.src = image.media_url;
      img.alt = image.alt_text || "Hermes sidecar image";
      gallery.appendChild(img);
    }
    if (gallery.childNodes.length) {
      article.appendChild(gallery);
    }
  }

  return article;
}

function renderMessages(messages) {
  chatMessagesElement.textContent = "";

  if (!Array.isArray(messages) || !messages.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No messages yet. Ask Hermes something or share the current page.";
    chatMessagesElement.appendChild(empty);
    return;
  }

  for (const message of messages) {
    chatMessagesElement.appendChild(renderMessage(message));
  }
  chatMessagesElement.scrollTop = chatMessagesElement.scrollHeight;
}

function renderPageContext(pageContext) {
  const title = String(pageContext?.title || "").trim();
  const url = String(pageContext?.url || "").trim();
  const selectionLength = String(pageContext?.selection || "").length;
  const pageTextLength = String(pageContext?.pageText || "").length;

  pageTitleElement.textContent = title || "Active tab unavailable";
  pageUrlElement.textContent = url || "";
  pageMetaElement.textContent = `${selectionLength} selected chars • ${pageTextLength} page chars`;
}

function applySessionState(result) {
  const session = result?.session || {};
  activeSessionKey = String(session.session_key || activeSessionKey || "").trim();
  transportSummaryElement.textContent = result?.adapter
    ? `Adapter: ${result.adapter}`
    : "Adapter unknown.";
  sessionIdElement.textContent = session.session_id
    ? `Session ID: ${session.session_id}`
    : "Session ID unavailable";

  renderMessages(session.messages || []);

  const progress = session.progress || {};
  const detail = String(progress.detail || "").trim() || "Ready.";
  setStatus(detail, Boolean(progress.error));
  interruptButton.hidden = progress.running !== true;
  schedulePoll(progress.running === true);
}

async function refreshSession() {
  const [settingsResponse, pageContextResponse, sessionResponse] = await Promise.all([
    sendRuntimeMessage({ type: "sidecar:get-settings" }),
    sendRuntimeMessage({ type: "sidecar:get-page-context" }),
    sendRuntimeMessage({ type: "sidecar:get-session-state", sessionKey: activeSessionKey })
  ]);

  if (!settingsResponse?.ok) {
    throw new Error(settingsResponse?.error || "Unable to load settings.");
  }
  if (!pageContextResponse?.ok) {
    throw new Error(pageContextResponse?.error || "Unable to read the current page.");
  }
  if (!sessionResponse?.ok) {
    throw new Error(sessionResponse?.error || "Unable to load session state.");
  }

  backendUrlElement.textContent = settingsResponse.result.backendUrl || "";
  if (!settingsInitialized) {
    usePageCheckbox.checked = settingsResponse.result.includePageByDefault !== false;
    settingsInitialized = true;
  }
  renderPageContext(pageContextResponse.result || {});
  applySessionState(sessionResponse.result || {});
}

async function sendMessage() {
  const message = chatInputElement.value.trim();
  const includePage = usePageCheckbox.checked;
  setStatus("Sending...");
  sendButton.disabled = true;

  try {
    const response = await sendRuntimeMessage({
      type: "sidecar:send-message",
      payload: {
        message,
        includePage,
        sessionKey: activeSessionKey
      }
    });

    if (!response?.ok) {
      throw new Error(response?.error || "Unable to send message.");
    }

    chatInputElement.value = "";
    applySessionState(response.result || {});
  } finally {
    sendButton.disabled = false;
  }
}

async function resetChat() {
  const response = await sendRuntimeMessage({
    type: "sidecar:reset-chat",
    sessionKey: activeSessionKey
  });
  if (!response?.ok) {
    throw new Error(response?.error || "Unable to start a new chat.");
  }
  applySessionState(response.result || {});
}

async function interruptChat() {
  const response = await sendRuntimeMessage({
    type: "sidecar:interrupt",
    sessionKey: activeSessionKey
  });
  if (!response?.ok) {
    throw new Error(response?.error || "Unable to interrupt the current turn.");
  }
  applySessionState(response.result || {});
}

sendButton.addEventListener("click", () => {
  sendMessage().catch((error) => setStatus(String(error?.message || error), true));
});

chatInputElement.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    sendMessage().catch((error) => setStatus(String(error?.message || error), true));
  }
});

refreshButton.addEventListener("click", () => {
  refreshSession().catch((error) => setStatus(String(error?.message || error), true));
});

resetButton.addEventListener("click", () => {
  resetChat().catch((error) => setStatus(String(error?.message || error), true));
});

interruptButton.addEventListener("click", () => {
  interruptChat().catch((error) => setStatus(String(error?.message || error), true));
});

optionsButton.addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

refreshSession().catch((error) => setStatus(String(error?.message || error), true));
