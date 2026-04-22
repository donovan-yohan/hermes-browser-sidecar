const backendUrlElement = document.getElementById("backend-url");
const transportSummaryElement = document.getElementById("transport-summary");
const capabilitiesElement = document.getElementById("capabilities");
const statusElement = document.getElementById("status");
const refreshButton = document.getElementById("refresh-button");
const optionsButton = document.getElementById("options-button");

function setStatus(message, isError = false) {
  statusElement.textContent = message;
  statusElement.dataset.state = isError ? "error" : "normal";
}

function sendRuntimeMessage(message) {
  return chrome.runtime.sendMessage(message);
}

async function refreshView() {
  const settingsResponse = await sendRuntimeMessage({ type: "sidecar:get-settings" });
  if (!settingsResponse?.ok) {
    throw new Error(settingsResponse?.error || "Unable to load settings.");
  }

  backendUrlElement.textContent = settingsResponse.result.backendUrl || "";

  const healthResponse = await sendRuntimeMessage({ type: "sidecar:check-health" });
  if (!healthResponse?.ok) {
    throw new Error(healthResponse?.error || "Unable to reach the sidecar service.");
  }

  const capabilitiesResponse = await sendRuntimeMessage({ type: "sidecar:get-capabilities" });
  if (!capabilitiesResponse?.ok) {
    throw new Error(capabilitiesResponse?.error || "Unable to read sidecar capabilities.");
  }

  const transport = healthResponse.result.transport || {};
  transportSummaryElement.textContent =
    `mode=${transport.mode || "unknown"}, adapter=${transport.active_adapter || "unknown"}`;
  capabilitiesElement.textContent = JSON.stringify(capabilitiesResponse.result.capabilities || {}, null, 2);
  setStatus("Sidecar reachable.");
}

refreshButton.addEventListener("click", () => {
  refreshView().catch((error) => setStatus(String(error?.message || error), true));
});

optionsButton.addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

refreshView().catch((error) => setStatus(String(error?.message || error), true));

