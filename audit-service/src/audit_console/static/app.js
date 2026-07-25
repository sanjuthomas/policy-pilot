const eventsBody = document.getElementById("events-body");
const auditBody = document.getElementById("audit-body");
const statusEl = document.getElementById("status");
const eventsView = document.getElementById("events-view");
const auditView = document.getElementById("audit-view");
const eventsToolbar = document.getElementById("events-toolbar");
const auditToolbar = document.getElementById("audit-toolbar");
const eventsTab = document.getElementById("events-tab");
const auditTab = document.getElementById("audit-tab");

function time(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value || "—" : date.toISOString();
}

function text(value) {
  return value === null || value === undefined || value === "" ? "—" : String(value);
}

async function loadEvents() {
  statusEl.textContent = "Loading security events…";
  const params = new URLSearchParams();
  const source = document.getElementById("source-filter").value;
  const severity = document.getElementById("severity-filter").value;
  if (source) params.set("source", source);
  if (severity) params.set("severity", severity);
  const response = await AuditorAuth.apiFetch(`/api/security-events?${params}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const body = await response.json();
  eventsBody.innerHTML = (body.events || []).map((item) => {
    const event = item.event || {};
    const actor = item.actor || {};
    const resource = item.resource || {};
    return `<tr>
      <td><a class="mono" href="/events/${encodeURIComponent(item.domain)}/${encodeURIComponent(item.event_id)}">${text(item.event_id)}</a></td>
      <td class="mono">${time(item.timestamp)}</td>
      <td>${text(item.domain)}</td>
      <td><span class="badge badge-${text(item.severity)}">${text(item.severity)}</span></td>
      <td class="mono">${text(event.action)}</td>
      <td class="outcome-${text(event.outcome)}">${text(event.outcome)}</td>
      <td class="mono">${text(actor.user_id)}</td>
      <td class="mono">${text(resource.id)}</td>
      <td>${text(item.message)}</td>
    </tr>`;
  }).join("");
  document.getElementById("events-empty").classList.toggle("hidden", body.count > 0);
  statusEl.textContent = `${body.count} security events`;
}

function paymentId(item) {
  const request = item.request || {};
  const result = item.result || {};
  // Denies often only carry payment_id on request (no mutation result).
  return result.payment_id || request.payment_id || "";
}

async function loadAudit() {
  statusEl.textContent = "Loading audit records…";
  const response = await AuditorAuth.apiFetch("/api/audit-executions");
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const body = await response.json();
  auditBody.innerHTML = (body.executions || []).map((item) => {
    const actor = item.actor || {};
    const request = item.request || {};
    const governance = item.governance || {};
    const eventId = governance.security_event_id;
    let evidence = "—";
    if (eventId) {
      evidence = `<a class="mono" href="/events/payment/${encodeURIComponent(eventId)}">${text(eventId)}</a>`;
    } else if (governance.policy_exchange) {
      evidence = "preflight";
    }
    return `<tr>
      <td class="col-execution"><a class="mono" href="/audit/${encodeURIComponent(item.execution_id)}">${text(item.execution_id)}</a></td>
      <td class="mono">${time(item.created_at)}</td>
      <td class="mono">${text(item.capability)}</td>
      <td class="outcome-${text(item.outcome)}">${text(item.outcome)}</td>
      <td>${text(item.status)}</td>
      <td class="mono">${text(actor.user_id)}</td>
      <td class="mono">${text(request.instruction_id)}</td>
      <td class="mono">${text(paymentId(item))}</td>
      <td>${evidence}</td>
    </tr>`;
  }).join("");
  document.getElementById("audit-empty").classList.toggle("hidden", body.count > 0);
  statusEl.textContent = `${body.count} audit records`;
}

function showEvents() {
  eventsTab.classList.add("active");
  auditTab.classList.remove("active");
  eventsView.classList.remove("hidden");
  eventsToolbar.classList.remove("hidden");
  auditView.classList.add("hidden");
  auditToolbar.classList.add("hidden");
  if (AuditorAuth.session()) void loadEvents().catch(showError);
}

function showAudit() {
  auditTab.classList.add("active");
  eventsTab.classList.remove("active");
  auditView.classList.remove("hidden");
  auditToolbar.classList.remove("hidden");
  eventsView.classList.add("hidden");
  eventsToolbar.classList.add("hidden");
  if (AuditorAuth.session()) void loadAudit().catch(showError);
}

function showError(error) {
  statusEl.textContent = `Load failed: ${error.message || error}`;
}

eventsTab.addEventListener("click", showEvents);
auditTab.addEventListener("click", showAudit);
document.getElementById("refresh-events").addEventListener("click", () => void loadEvents().catch(showError));
document.getElementById("refresh-audit").addEventListener("click", () => void loadAudit().catch(showError));
document.getElementById("source-filter").addEventListener("change", () => void loadEvents().catch(showError));
document.getElementById("severity-filter").addEventListener("change", () => void loadEvents().catch(showError));
AuditorAuth.bind(() => void loadEvents().catch(showError));
