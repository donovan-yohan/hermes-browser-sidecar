const backendUrlInput = document.getElementById("backend-url");
const includePageByDefaultInput = document.getElementById("include-page-by-default");
const saveButton = document.getElementById("save-button");
const healthButton = document.getElementById("health-button");
const statusElement = document.getElementById("status");

function setStatus(message, isError = false) {
  statusElement.textContent = message;
  statusElement.dataset.state = isError ? "error" : "normal";
}

function sendRuntimeMessage(message) {
  return chrome.runtime.sendMessage(message);
}

async function loadSettings() {
  const response = await sendRuntimeMessage({ type: "sidecar:get-settings" });
  if (!response?.ok) {
    throw new Error(response?.error || "Unable to load settings.");
  }

  backendUrlInput.value = response.result.backendUrl || "";
  includePageByDefaultInput.checked = response.result.includePageByDefault !== false;
}

async function saveSettings() {
  const response = await sendRuntimeMessage({
    type: "sidecar:save-settings",
    payload: {
      backendUrl: backendUrlInput.value,
      includePageByDefault: includePageByDefaultInput.checked
    }
  });

  if (!response?.ok) {
    throw new Error(response?.error || "Unable to save settings.");
  }

  setStatus("Settings saved.");
}

async function checkHealth() {
  const response = await sendRuntimeMessage({ type: "sidecar:check-health" });
  if (!response?.ok) {
    throw new Error(response?.error || "Health check failed.");
  }

  const transport = response.result.transport || {};
  const upstream = response.result.upstream || {};
  setStatus(
    `Sidecar reachable. Mode=${transport.mode || "unknown"}, adapter=${transport.active_adapter || "unknown"}, upstream=${upstream.ok === true ? "ok" : "down"}.`
  );
}

saveButton.addEventListener("click", () => {
  saveSettings().catch((error) => setStatus(String(error?.message || error), true));
});

healthButton.addEventListener("click", () => {
  checkHealth().catch((error) => setStatus(String(error?.message || error), true));
});

loadSettings()
  .then(() => setStatus("Settings loaded."))
  .catch((error) => setStatus(String(error?.message || error), true));
