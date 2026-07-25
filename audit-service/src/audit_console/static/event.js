function locationParts() {
  const parts = location.pathname.split("/").filter(Boolean);
  return { source: parts[1], id: decodeURIComponent(parts.slice(2).join("/")) };
}

function field(label, value) {
  return `<div class="field"><dt>${label}</dt><dd class="mono">${value ?? "—"}</dd></div>`;
}

async function load() {
  const { source, id } = locationParts();
  document.getElementById("subtitle").textContent = `${source} · ${id}`;
  const response = await AuditorAuth.apiFetch(
    `/api/security-events/${encodeURIComponent(source)}/${encodeURIComponent(id)}`
  );
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const body = await response.json();
  const item = body.event;
  const event = item.event || {};
  const actor = item.actor || {};
  const resource = item.resource || {};
  document.getElementById("summary").innerHTML = `<section class="card">
    <div class="card-header"><h2>${item.message || "Security event"}</h2><span class="badge badge-${item.severity}">${item.severity}</span></div>
    <dl class="grid">
      ${field("Domain", item.domain)}${field("Timestamp", item.timestamp)}
      ${field("Action", event.action)}${field("Outcome", event.outcome)}
      ${field("Actor", actor.user_id)}${field("Roles", (actor.roles || []).join(", "))}
      ${field("Resource", resource.id)}${field("Instruction", resource.instruction_id)}
      ${field("Status", resource.status)}${field("Owning LOB", resource.owning_lob)}
    </dl>
  </section>`;
  document.getElementById("json").textContent = AuditorFormat.prettyJson(item);
}

AuditorAuth.bind(() => void load().catch((error) => {
  document.getElementById("summary").innerHTML = `<p class="empty">Load failed: ${error.message}</p>`;
}));
