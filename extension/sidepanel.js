const pageTitle = document.getElementById("page-title");
const pageMeta = document.getElementById("page-meta");
const messagesElement = document.getElementById("chat-messages");
const includePage = document.getElementById("include-page");
const chatInput = document.getElementById("chat-input");
const chatForm = document.getElementById("chat-form");
const sendButton = document.getElementById("send-button");
const resetButton = document.getElementById("reset-button");
const interruptButton = document.getElementById("interrupt-button");
const refreshButton = document.getElementById("refresh-button");
const optionsButton = document.getElementById("options-button");
const statusElement = document.getElementById("status");

let pollHandle = null;
let capabilities = {};

function setStatus(message, isError = false) {
  statusElement.textContent = message || "";
  statusElement.dataset.state = isError ? "error" : "normal";
}

function send(message) {
  return chrome.runtime.sendMessage(message);
}

function applyCapabilities(caps) {
  capabilities = caps || {};
  includePage.parentElement.hidden = !capabilities.page_context;
  resetButton.hidden = !capabilities.session_reset;
  sendButton.disabled = !capabilities.session_send;
}

function normalizeMessageRole(role) {
  const normalized = String(role || "assistant").toLowerCase();
  return ["user", "assistant", "system"].includes(normalized) ? normalized : "assistant";
}

function renderMessages(messages) {
  messagesElement.replaceChildren();

  if (!messages || messages.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-state";
    emptyState.textContent = "No messages yet.";
    messagesElement.appendChild(emptyState);
    return;
  }

  messages.forEach((msg) => {
    const role = normalizeMessageRole(msg.role);
    const meta = `${role} · ${msg.timestamp || ""} · ${msg.kind || "text"}`;

    const article = document.createElement("article");
    article.className = `message message--${role}`;

    const metaElement = document.createElement("p");
    metaElement.className = "message-meta";
    metaElement.textContent = meta;

    const bodyElement = document.createElement("div");
    bodyElement.className = "message-body";

    const content = String(msg.content || "");
    const lines = content.split("\n");
    lines.forEach((line, index) => {
      if (index > 0) {
        bodyElement.appendChild(document.createElement("br"));
      }
      bodyElement.appendChild(document.createTextNode(line));
    });

    article.appendChild(metaElement);
    article.appendChild(bodyElement);
    messagesElement.appendChild(article);
  });
  messagesElement.scrollTop = messagesElement.scrollHeight;
}

function setRunning(running) {
  interruptButton.hidden = !(running && capabilities.session_interrupt);
  sendButton.disabled = running || !capabilities.session_send;
}

async function refreshPageMeta() {
  try {
    const response = await send({ type: "sidecar:get-page-context" });
    if (response?.ok && response.result) {
      pageTitle.textContent = response.result.title || "(untitled page)";
      pageMeta.textContent = response.result.url || "";
    }
  } catch (error) {
    pageTitle.textContent = "(no active page)";
    pageMeta.textContent = "";
  }
}

async function refreshCapabilities() {
  const response = await send({ type: "sidecar:get-capabilities" });
  if (!response?.ok) throw new Error(response?.error || "Capability check failed.");
  applyCapabilities(response.result?.capabilities);
}

async function refreshSession() {
  const response = await send({ type: "sidecar:get-session-state" });
  if (!response?.ok) throw new Error(response?.error || "Session fetch failed.");
  const session = response.result?.session || {};
  renderMessages(session.messages);
  setRunning(Boolean(session.progress?.running));
  schedulePoll(session.progress?.running);
}

function schedulePoll(running) {
  if (pollHandle) {
    clearTimeout(pollHandle);
    pollHandle = null;
  }
  if (running) {
    pollHandle = setTimeout(() => {
      refreshSession().catch((error) => setStatus(String(error?.message || error), true));
    }, 750);
  }
}

async function refreshAll() {
  setStatus("Refreshing…");
  await refreshPageMeta();
  await refreshCapabilities();
  await refreshSession();
  setStatus("Ready.");
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  setRunning(true);
  setStatus("Sending…");
  try {
    const response = await send({
      type: "sidecar:send",
      payload: { message, includePage: includePage.checked }
    });
    if (!response?.ok) throw new Error(response?.error || "Send failed.");
    chatInput.value = "";
    const session = response.result?.session || {};
    renderMessages(session.messages);
    setRunning(Boolean(session.progress?.running));
    schedulePoll(session.progress?.running);
    setStatus("Ready.");
  } catch (error) {
    setStatus(String(error?.message || error), true);
    setRunning(false);
  }
});

resetButton.addEventListener("click", async () => {
  setStatus("Resetting…");
  try {
    const response = await send({ type: "sidecar:reset" });
    if (!response?.ok) throw new Error(response?.error || "Reset failed.");
    renderMessages(response.result?.session?.messages);
    setRunning(false);
    setStatus("Session reset.");
  } catch (error) {
    setStatus(String(error?.message || error), true);
  }
});

interruptButton.addEventListener("click", async () => {
  setStatus("Interrupting…");
  try {
    const response = await send({ type: "sidecar:interrupt" });
    if (!response?.ok) throw new Error(response?.error || "Interrupt failed.");
    setRunning(false);
    setStatus("Interrupted.");
    await refreshSession();
  } catch (error) {
    setStatus(String(error?.message || error), true);
  }
});

refreshButton.addEventListener("click", () => {
  refreshAll().catch((error) => setStatus(String(error?.message || error), true));
});

optionsButton.addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

chatInput.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

refreshAll().catch((error) => setStatus(String(error?.message || error), true));
