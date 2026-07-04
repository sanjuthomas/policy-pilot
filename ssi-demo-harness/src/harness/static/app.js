window.ADMIN_AUTH_STORAGE_KEY = window.ADMIN_AUTH_STORAGE_KEY || "ssi-harness-admin-session";

const logOutput = document.getElementById("log-output");
const patStatus = document.getElementById("pat-status");
const statInstructions = document.getElementById("stat-instructions");
const statPayments = document.getElementById("stat-payments");
const statEvents = document.getElementById("stat-events");
const statPaymentEvents = document.getElementById("stat-payment-events");
const actionGrid = document.getElementById("action-grid");
const paymentActionGrid = document.getElementById("payment-action-grid");
const clearLogButton = document.getElementById("clear-log");

let busy = false;

function appendLog(text, { error = false } = {}) {
  const stamp = new Date().toLocaleTimeString();
  const prefix = error ? "[error]" : "[info]";
  logOutput.textContent += `${stamp} ${prefix} ${text}\n`;
  logOutput.scrollTop = logOutput.scrollHeight;
}

function setBusy(nextBusy) {
  busy = nextBusy;
  [actionGrid, paymentActionGrid].forEach((grid) => {
    if (grid) {
      grid.querySelectorAll("button").forEach((button) => {
        button.disabled = nextBusy;
      });
    }
  });
}

async function refreshStatus() {
  if (!AdminAuth.loadSession()) {
    patStatus.textContent = "Sign in required";
    patStatus.className = "status-pill status-error";
    return;
  }

  try {
    const response = await AdminAuth.adminFetch("/api/status");
    if (!response.ok) {
      throw new Error(`status HTTP ${response.status}`);
    }
    const data = await response.json();

    if (data.zitadel_configured) {
      patStatus.textContent = "ZITADEL ready";
      patStatus.className = "status-pill status-live";
    } else {
      patStatus.textContent = "ZITADEL PAT missing";
      patStatus.className = "status-pill status-error";
    }

    const counts = data.instruction_counts || {};
    const parts = Object.entries(counts)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([status, count]) => `${status}: ${count}`);
    statInstructions.textContent = parts.length
      ? `${data.instruction_total} (${parts.join(", ")})`
      : String(data.instruction_total ?? 0);

    const pCounts = data.payment_counts || {};
    const pParts = Object.entries(pCounts)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([status, count]) => `${status}: ${count}`);
    if (statPayments) {
      statPayments.textContent = pParts.length
        ? `${data.payment_total} (${pParts.join(", ")})`
        : String(data.payment_total ?? 0);
    }

    statEvents.textContent =
      data.security_event_count >= 0 ? String(data.security_event_count) : "—";

    if (statPaymentEvents) {
      statPaymentEvents.textContent =
        data.payment_security_event_count >= 0
          ? String(data.payment_security_event_count)
          : "—";
    }
  } catch (error) {
    patStatus.textContent = "Status unavailable";
    patStatus.className = "status-pill status-error";
    console.error(error);
  }
}

async function runAction(action, count, amount = null) {
  if (busy) {
    return;
  }

  if (!AdminAuth.loadSession()) {
    appendLog("Admin sign-in required before running actions.", { error: true });
    return;
  }

  setBusy(true);
  const label = action.replace(/-/g, " ");
  const amountNote =
    amount !== null && Number.isFinite(amount) && amount > 0 ? `, amount=${amount}` : "";
  appendLog(`Starting ${label}${count ? ` (count=${count}${amountNote})` : ""}...`);

  try {
    const body = count ? { count } : {};
    if (amount !== null && Number.isFinite(amount) && amount > 0) {
      body.amount = amount;
    }
    const response = await AdminAuth.adminFetch(`/api/actions/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    if (!response.ok) {
      const detail = data.detail || JSON.stringify(data);
      throw new Error(detail);
    }

    for (const line of data.logs || []) {
      appendLog(line, { error: !data.ok });
    }

    appendLog(
      `Finished ${label}: succeeded=${data.succeeded}, failed=${data.failed}, skipped=${data.skipped}`,
      { error: !data.ok },
    );
  } catch (error) {
    appendLog(`${label} failed: ${error.message}`, { error: true });
  } finally {
    setBusy(false);
    await refreshStatus();
  }
}

function handleGridClick(event) {
  const button = event.target.closest("button");
  if (!button || button.disabled) {
    return;
  }

  const card = button.closest(".action-card");
  if (!card) {
    return;
  }

  const action = card.dataset.action;
  const input = card.querySelector('input[type="number"]:not([data-role="amount"])');
  const count = input ? Number.parseInt(input.value, 10) : null;
  const amountInput = card.querySelector('input[data-role="amount"]');
  const amountRaw = amountInput && amountInput.value.trim() !== "" ? amountInput.value : null;
  const amount = amountRaw !== null ? Number.parseFloat(amountRaw) : null;

  if (input && (!Number.isFinite(count) || count < 1)) {
    appendLog("Enter a valid count (at least 1).", { error: true });
    return;
  }

  if (amountRaw !== null && (!Number.isFinite(amount) || amount <= 0)) {
    appendLog("Enter a valid amount greater than zero, or leave amount blank.", { error: true });
    return;
  }

  void runAction(action, count, amount);
}

actionGrid.addEventListener("click", handleGridClick);
if (paymentActionGrid) {
  paymentActionGrid.addEventListener("click", handleGridClick);
}

clearLogButton.addEventListener("click", () => {
  logOutput.textContent = "";
});

AdminAuth.bindAdminAuthPanel({
  statusEl: document.getElementById("auth-status"),
  userEl: document.getElementById("auth-user"),
  passwordEl: document.getElementById("auth-password"),
  loginBtn: document.getElementById("auth-login-btn"),
  logoutBtn: document.getElementById("auth-logout-btn"),
  defaultUserId: "admin-001",
  onAuthenticated: () => {
    void refreshStatus();
  },
});

setInterval(() => {
  if (AdminAuth.loadSession()) {
    void refreshStatus();
  }
}, 15000);
