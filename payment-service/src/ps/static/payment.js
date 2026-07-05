const subtitle = document.getElementById("payment-id-subtitle");
const errorEl = document.getElementById("detail-error");
const summaryEl = document.getElementById("detail-summary");
const lifecycleSection = document.getElementById("lifecycle-section");
const lifecycleList = document.getElementById("lifecycle-list");
const jsonSection = document.getElementById("detail-json-section");
const jsonEl = document.getElementById("detail-json");
const copyBtn = document.getElementById("copy-json-btn");

function paymentIdFromPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (parts.length >= 3 && parts[0] === "ui" && parts[1] === "payments") {
    return decodeURIComponent(parts.slice(2).join("/"));
  }
  return null;
}

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toISOString().replace("T", " ").replace(".000Z", "Z");
}

function formatAmount(amount, currency) {
  if (amount === null || amount === undefined) return "—";
  const formatted = Number(amount).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return currency ? `${formatted} ${currency}` : formatted;
}

function statusBadge(status) {
  return `<span class="badge badge-${status || "PENDING"}">${status || "PENDING"}</span>`;
}

function field(label, value) {
  const display = value === null || value === undefined || value === "" ? "—" : value;
  return `
    <div class="detail-field">
      <dt>${label}</dt>
      <dd class="mono">${display}</dd>
    </div>
  `;
}

function userField(label, userRef) {
  if (!userRef || !userRef.user_id) return field(label, null);
  const name = [userRef.given_name, userRef.family_name].filter(Boolean).join(" ");
  const display = name ? `${name} (${userRef.user_id})` : userRef.user_id;
  return field(label, `${display} · ${userRef.title || ""}`);
}

function renderSummary(payment) {
  summaryEl.innerHTML = `
    <div class="detail-card-header">
      ${statusBadge(payment.status)}
      <span class="detail-action mono">${payment.instruction_type || "—"}</span>
      <span class="detail-action mono">${payment.owning_lob || "—"}</span>
      <span class="detail-action" style="font-size:1.05rem;font-weight:700;color:var(--accent)">
        ${formatAmount(payment.amount, payment.currency)}
      </span>
    </div>
    <dl class="detail-grid">
      ${field("Payment ID", payment.payment_id)}
      ${field("Instruction ID", payment.instruction_id)}
      ${field("Instruction Version", payment.instruction_version)}
      ${field("Value Date", payment.value_date)}
      ${field("Amount", formatAmount(payment.amount, payment.currency))}
      ${field("Currency", payment.currency)}
      ${field("LOB", payment.owning_lob)}
      ${field("Instruction Type", payment.instruction_type)}
      ${userField("Created by", payment.created_by)}
      ${userField("Submitted by", payment.submitted_by)}
      ${userField("Approved by", payment.approved_by)}
      ${userField("Rejected by", payment.rejected_by)}
      ${userField("Cancelled by", payment.cancelled_by)}
      ${field("Rejection reason", payment.rejection_reason)}
      ${field("Cancellation reason", payment.cancellation_reason)}
      ${field("Submitted (UTC)", formatTime(payment.submitted_at))}
      ${field("Approved (UTC)", formatTime(payment.approved_at))}
      ${field("Rejected (UTC)", formatTime(payment.rejected_at))}
      ${field("Cancelled (UTC)", formatTime(payment.cancelled_at))}
      ${field("Created (UTC)", formatTime(payment.created_at))}
      ${field("Updated (UTC)", formatTime(payment.updated_at))}
    </dl>
  `;
}

function renderLifecycle(events) {
  if (!events || events.length === 0) return;
  lifecycleList.innerHTML = "";
  events.forEach((ev) => {
    const li = document.createElement("li");
    li.className = "lifecycle-item";
    li.innerHTML = `
      <span class="lifecycle-action">${ev.action || "—"}</span>
      <span class="lifecycle-meta">
        ${formatTime(ev.timestamp)} · actor: ${ev.actor_user_id || "—"}
        ${ev.details && Object.keys(ev.details).length ? " · " + JSON.stringify(ev.details) : ""}
      </span>
    `;
    lifecycleList.appendChild(li);
  });
  lifecycleSection.classList.remove("hidden");
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.classList.remove("hidden");
  summaryEl.classList.add("hidden");
  lifecycleSection.classList.add("hidden");
  jsonSection.classList.add("hidden");
}

async function loadPayment() {
  const paymentId = paymentIdFromPath();
  if (!paymentId) {
    showError("Missing payment id in URL.");
    subtitle.textContent = "Invalid URL";
    return;
  }

  if (!AdminAuth.loadSession()) {
    showError("Admin sign-in required.");
    subtitle.textContent = paymentId;
    return;
  }

  subtitle.textContent = paymentId;
  document.title = `Payment · ${paymentId}`;

  try {
    const response = await AdminAuth.adminFetch(
      `/api/ui/payments/${encodeURIComponent(paymentId)}`
    );
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    const payload = await response.json();
    const payment = payload.payment;

    renderSummary(payment);
    summaryEl.classList.remove("hidden");

    renderLifecycle(payment.lifecycle_events);

    jsonEl.textContent = JSON.stringify(payment, null, 2);
    jsonSection.classList.remove("hidden");
  } catch (error) {
    showError(`Could not load payment: ${error.message}`);
  }
}

copyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(jsonEl.textContent);
    copyBtn.textContent = "Copied";
    window.setTimeout(() => { copyBtn.textContent = "Copy JSON"; }, 1500);
  } catch {
    copyBtn.textContent = "Copy failed";
  }
});

AdminAuth.bindAdminAuthPanel({
  statusEl: document.getElementById("auth-status"),
  userEl: document.getElementById("auth-user"),
  passwordEl: document.getElementById("auth-password"),
  loginBtn: document.getElementById("auth-login-btn"),
  logoutBtn: document.getElementById("auth-logout-btn"),
  onAuthenticated: () => {
    void loadPayment();
  },
});
