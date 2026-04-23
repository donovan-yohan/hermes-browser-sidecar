const backendUrlInput = document.getElementById("backend-url");
const includePageDefault = document.getElementById("include-page-default");
const saveButton = document.getElementById("save-button");
const healthButton = document.getElementById("health-button");
const statusElement = document.getElementById("status");
const capabilitiesElement = document.getElementById("capabilities");

function setStatus(message, isError = false) {
  statusElement.textContent = message;
  statusElement.dataset.state = isError ? "error" : "normal";
}

function send(message) {
  return chrome.runtime.sendMessage(message);
}

async function loadSettings() {
  const response = await send({ type: "sidecar:get-settings" });
  if (!response?.ok) throw new Error(response?.error || "Unable to load settings.");
  backendUrlInput.value = response.result.backendUrl || "";
  includePageDefault.checked = response.result.includePageByDefault !== false;
}

async function saveSettings() {
  const response = await send({
    type: "sidecar:save-settings",
    payload: {
      backendUrl: backendUrlInput.value,
      includePageByDefault: includePageDefault.checked
    }
  });
  if (!response?.ok) throw new Error(response?.error || "Unable to save settings.");
  setStatus("Settings saved.");
}

async function checkHealth() {
  const healthResponse = await send({ type: "sidecar:check-health" });
  if (!healthResponse?.ok) throw new Error(healthResponse?.error || "Health check failed.");
  const transport = healthResponse.result.transport || {};
  const upstream = healthResponse.result.upstream || {};
  setStatus(
    `Sidecar reachable. Mode=${transport.mode || "?"}, adapter=${transport.active_adapter || "?"}, upstream=${upstream.ok ? "ok" : "down"}.`
  );
  const capsResponse = await send({ type: "sidecar:get-capabilities" });
  if (capsResponse?.ok) {
    capabilitiesElement.textContent = JSON.stringify(capsResponse.result.capabilities || {}, null, 2);
  }
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
