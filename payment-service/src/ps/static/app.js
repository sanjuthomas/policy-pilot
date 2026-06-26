const MAX_ROWS = 500;

const tbody = document.getElementById("payments-body");
const emptyState = document.getElementById("empty-state");
const loadStatus = document.getElementById("load-status");
const statTotal = document.getElementById("stat-total");
const statusFilter = document.getElementById("status-filter");
const lobFilter = document.getElementById("lob-filter");
const typeFilter = document.getElementById("type-filter");
const refreshBtn = document.getElementById("refresh-btn");
const pauseBtn = document.getElementById("pause-btn");
const clearBtn = document.getElementById("clear-btn");

let payments = [];
let paused = false;
let source = null;

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toISOString().replace("T", " ").replace(".000Z", "Z");
}

function shortId(value) {
  if (!value) return "—";
  const parts = String(value).split("-");
  return parts.length > 1 ? parts[parts.length - 1] : value;
}

function paymentIdLink(paymentId) {
  if (!paymentId) return "—";
  const href = `/ui/payments/${encodeURIComponent(paymentId)}`;
  return `<a class="id-link mono" href="${href}" title="${paymentId}">${shortId(paymentId)}</a>`;
}

function instructionLink(instructionId) {
  if (!instructionId) return "—";
  const href = `http://localhost:8000/ui/instructions/${encodeURIComponent(instructionId)}`;
  return `<a class="id-link mono" href="${href}" target="_blank" rel="noopener" title="${instructionId}">${shortId(instructionId)}</a>`;
}

function statusBadge(status) {
  return `<span class="badge badge-${status || "PENDING"}">${status || "PENDING"}</span>`;
}

function formatAmount(amount, currency) {
  if (amount === null || amount === undefined) return "—";
  const formatted = Number(amount).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `<span class="amount-cell">${formatted}</span>`;
}

function passesFilters(p) {
  if (statusFilter.value !== "ALL" && p.status !== statusFilter.value) return false;
  if (lobFilter.value !== "ALL" && p.owning_lob !== lobFilter.value) return false;
  if (typeFilter.value !== "ALL" && p.instruction_type !== typeFilter.value) return false;
  return true;
}

function updateLobOptions() {
  const lobs = new Set(payments.map((p) => p.owning_lob).filter(Boolean));
  const current = lobFilter.value;
  lobFilter.innerHTML = '<option value="ALL">All</option>';
  [...lobs].sort().forEach((lob) => {
    const opt = document.createElement("option");
    opt.value = lob;
    opt.textContent = lob;
    lobFilter.appendChild(opt);
  });
  if ([...lobs, "ALL"].includes(current)) lobFilter.value = current;
}

function renderTable({ highlightFirst = false } = {}) {
  tbody.innerHTML = "";
  const visible = payments.filter(passesFilters);
  emptyState.classList.toggle("hidden", visible.length > 0);
  statTotal.textContent = String(visible.length);

  visible.forEach((p, index) => {
    const row = document.createElement("tr");
    if (highlightFirst && index === 0) row.classList.add("row-new");

    const creatorId = p.created_by?.user_id || "—";
    const creatorTitle = p.created_by?.title || "";
    const approverId = p.approved_by?.user_id || "—";

    row.innerHTML = `
      <td class="col-id">${paymentIdLink(p.payment_id)}</td>
      <td class="col-id">${instructionLink(p.instruction_id)}</td>
      <td class="mono">${p.instruction_version ?? "—"}</td>
      <td>${statusBadge(p.status)}</td>
      <td class="mono">${p.instruction_type || "—"}</td>
      <td class="mono">${p.owning_lob || "—"}</td>
      <td class="mono">${formatAmount(p.amount)}</td>
      <td class="mono">${p.currency || "—"}</td>
      <td class="mono">${p.value_date || "—"}</td>
      <td>
        <div class="mono">${creatorId}</div>
        <div class="muted">${creatorTitle}</div>
      </td>
      <td class="mono">${approverId}</td>
      <td class="mono">${formatTime(p.created_at)}</td>
      <td class="mono">${formatTime(p.updated_at)}</td>
    `;
    tbody.appendChild(row);
  });

  if (highlightFirst) {
    const firstRow = tbody.querySelector("tr.row-new");
    if (firstRow) window.setTimeout(() => firstRow.classList.remove("row-new"), 1200);
  }
}

function setLoadStatus(state, label) {
  loadStatus.className = `status-pill status-${state}`;
  loadStatus.textContent = label;
}

function upsertPayment(payment, { isLive = false } = {}) {
  const id = payment?.payment_id;
  if (!id) return;
  const idx = payments.findIndex((p) => p.payment_id === id);
  if (idx >= 0) payments.splice(idx, 1);
  payments.unshift(payment);
  if (payments.length > MAX_ROWS) payments.pop();
  updateLobOptions();
  renderTable({ highlightFirst: isLive });
}

async function loadPayments() {
  setLoadStatus("connecting", "Loading");
  try {
    const response = await fetch("/api/ui/payments?limit=500");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    payments = payload.payments || [];
    updateLobOptions();
    renderTable();
    setLoadStatus("live", `Loaded ${payments.length}`);
  } catch (error) {
    setLoadStatus("error", "Load failed");
    console.error(error);
  }
}

function connectStream() {
  if (source) source.close();
  source = new EventSource("/api/ui/payments/stream");

  source.addEventListener("connected", () => {
    setLoadStatus("live", "Live · change stream");
  });

  source.onmessage = (message) => {
    if (paused) return;
    try {
      const payment = JSON.parse(message.data);
      upsertPayment(payment, { isLive: true });
    } catch (error) {
      console.error("invalid SSE payload", error);
    }
  };

  source.onerror = () => {
    setLoadStatus("error", "Reconnecting…");
    source.close();
    window.setTimeout(connectStream, 2000);
  };
}

statusFilter.addEventListener("change", () => renderTable());
lobFilter.addEventListener("change", () => renderTable());
typeFilter.addEventListener("change", () => renderTable());

refreshBtn.addEventListener("click", loadPayments);

pauseBtn.addEventListener("click", () => {
  paused = !paused;
  pauseBtn.textContent = paused ? "Resume live feed" : "Pause live feed";
});

clearBtn.addEventListener("click", () => {
  payments = [];
  renderTable();
});

loadPayments().then(connectStream);
