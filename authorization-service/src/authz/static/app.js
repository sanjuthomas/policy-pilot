const loadStatus = document.getElementById("load-status");
const statTotal = document.getElementById("stat-total");
const searchInput = document.getElementById("search-input");
const roleFilter = document.getElementById("role-filter");
const groupFilter = document.getElementById("group-filter");
const clearFiltersBtn = document.getElementById("clear-filters");
const userRows = document.getElementById("user-rows");

let allUsers = [];

function setStatus(text, kind) {
  loadStatus.textContent = text;
  loadStatus.className = `status-pill status-${kind}`;
}

function chipList(values) {
  if (!values || values.length === 0) {
    return '<span class="muted">—</span>';
  }
  return values.map((value) => `<span class="chip">${escapeHtml(value)}</span>`).join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderRows(users) {
  statTotal.textContent = String(users.length);

  if (users.length === 0) {
    userRows.innerHTML = '<tr><td colspan="10" class="empty-cell">No users match the current filters.</td></tr>';
    return;
  }

  userRows.innerHTML = users
    .map(
      (user) => `
    <tr>
      <td class="mono">${escapeHtml(user.user_id)}</td>
      <td>${escapeHtml(user.display_name)}</td>
      <td>${escapeHtml(user.title)}</td>
      <td class="mono">${escapeHtml(user.lob || "—")}</td>
      <td class="chip-cell">${chipList(user.roles)}</td>
      <td class="chip-cell">${chipList(user.groups)}</td>
      <td class="chip-cell">${chipList(user.amount_clubs)}</td>
      <td class="chip-cell">${chipList(user.covering_lobs)}</td>
      <td>
        ${
          user.supervisor_id
            ? `<span class="mono">${escapeHtml(user.supervisor_id)}</span>${
                user.supervisor_display_name
                  ? `<div class="subtle">${escapeHtml(user.supervisor_display_name)}</div>`
                  : ""
              }`
            : '<span class="muted">—</span>'
        }
      </td>
      <td class="mono subtle">${escapeHtml(user.login_name)}</td>
    </tr>`
    )
    .join("");
}

function populateFilters(users) {
  const roles = new Set();
  const groups = new Set();

  users.forEach((user) => {
    user.roles.forEach((role) => roles.add(role));
    user.groups.forEach((group) => groups.add(group));
    user.amount_clubs.forEach((club) => groups.add(club));
  });

  roleFilter.innerHTML =
    '<option value="">All roles</option>' +
    [...roles]
      .sort()
      .map((role) => `<option value="${escapeHtml(role)}">${escapeHtml(role)}</option>`)
      .join("");

  groupFilter.innerHTML =
    '<option value="">All groups</option>' +
    [...groups]
      .sort()
      .map((group) => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`)
      .join("");
}

function applyFilters() {
  const q = searchInput.value.trim().toLowerCase();
  const role = roleFilter.value;
  const group = groupFilter.value;

  const filtered = allUsers.filter((user) => {
    if (role && !user.roles.includes(role)) {
      return false;
    }
    if (
      group &&
      !user.groups.includes(group) &&
      !user.amount_clubs.includes(group) &&
      !user.covering_lobs.includes(group)
    ) {
      return false;
    }
    if (!q) {
      return true;
    }
    const haystack = [
      user.user_id,
      user.display_name,
      user.login_name,
      user.title,
      user.lob || "",
      user.supervisor_id || "",
      user.supervisor_display_name || "",
      ...user.roles,
      ...user.groups,
      ...user.amount_clubs,
      ...user.covering_lobs,
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });

  renderRows(filtered);
}

async function loadUsers() {
  if (!AdminAuth.loadSession()) {
    setStatus("Sign in required", "error");
    userRows.innerHTML = '<tr><td colspan="10" class="empty-cell">Admin sign-in required.</td></tr>';
    return;
  }
  setStatus("Loading", "connecting");
  try {
    const response = await AdminAuth.adminFetch("/api/ui/users");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    allUsers = data.users || [];
    populateFilters(allUsers);
    applyFilters();
    setStatus("Live", "live");
  } catch (error) {
    setStatus("Error", "error");
    userRows.innerHTML = `<tr><td colspan="10" class="empty-cell">Failed to load users: ${escapeHtml(
      error.message
    )}</td></tr>`;
  }
}

searchInput.addEventListener("input", applyFilters);
roleFilter.addEventListener("change", applyFilters);
groupFilter.addEventListener("change", applyFilters);
clearFiltersBtn.addEventListener("click", () => {
  searchInput.value = "";
  roleFilter.value = "";
  groupFilter.value = "";
  applyFilters();
});

AdminAuth.bindAdminAuthPanel({
  statusEl: document.getElementById("auth-status"),
  userEl: document.getElementById("auth-user"),
  passwordEl: document.getElementById("auth-password"),
  loginBtn: document.getElementById("auth-login-btn"),
  logoutBtn: document.getElementById("auth-logout-btn"),
  onAuthenticated: () => {
    void loadUsers();
  },
});
