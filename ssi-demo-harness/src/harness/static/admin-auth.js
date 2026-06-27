/**
 * Shared admin login helper for platform UIs.
 * Set window.ADMIN_AUTH_STORAGE_KEY before loading if you need a service-specific key.
 */
(function () {
  const STORAGE_KEY = window.ADMIN_AUTH_STORAGE_KEY || "ssi-admin-session";

  function loadSession() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function saveSession(session) {
    if (session) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  function authHeaders() {
    const session = loadSession();
    if (!session) {
      return {};
    }
    return {
      Authorization: `Bearer ${session.session_token}`,
      "X-Session-Id": session.session_id,
    };
  }

  async function adminFetch(url, options = {}) {
    const headers = {
      ...authHeaders(),
      ...(options.headers || {}),
    };
    const response = await fetch(url, { ...options, headers });
    if (response.status === 401 || response.status === 403) {
      saveSession(null);
      throw new Error("Admin authentication required — sign in again.");
    }
    return response;
  }

  async function login(userId, password) {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, password }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    const session = {
      user_id: payload.user_id,
      session_id: payload.session_id,
      session_token: payload.session_token,
    };
    saveSession(session);
    return session;
  }

  function logout() {
    saveSession(null);
  }

  function bindAdminAuthPanel({
    statusEl,
    userEl,
    passwordEl,
    loginBtn,
    logoutBtn,
    onAuthenticated,
    defaultUserId = "admin-001",
  }) {
    if (userEl && defaultUserId && !userEl.value) {
      userEl.value = defaultUserId;
    }

    function refreshUi() {
      const session = loadSession();
      if (session) {
        if (statusEl) {
          statusEl.textContent = `Signed in as ${session.user_id}`;
          statusEl.classList.remove("muted");
        }
        userEl?.classList.add("hidden");
        passwordEl?.classList.add("hidden");
        loginBtn?.classList.add("hidden");
        logoutBtn?.classList.remove("hidden");
        onAuthenticated?.(session);
      } else {
        if (statusEl) {
          statusEl.textContent = "Admin sign-in required";
          statusEl.classList.add("muted");
        }
        userEl?.classList.remove("hidden");
        passwordEl?.classList.remove("hidden");
        loginBtn?.classList.remove("hidden");
        logoutBtn?.classList.add("hidden");
      }
    }

    loginBtn?.addEventListener("click", async () => {
      loginBtn.disabled = true;
      try {
        await login(userEl?.value || defaultUserId, passwordEl?.value || "");
        if (passwordEl) {
          passwordEl.value = "";
        }
        refreshUi();
      } catch (error) {
        if (statusEl) {
          statusEl.textContent = `Login failed: ${error.message}`;
        }
      } finally {
        loginBtn.disabled = false;
      }
    });

    logoutBtn?.addEventListener("click", () => {
      logout();
      refreshUi();
    });

    refreshUi();
    return { refreshUi, requireSession: () => loadSession() };
  }

  window.AdminAuth = {
    loadSession,
    saveSession,
    authHeaders,
    adminFetch,
    login,
    logout,
    bindAdminAuthPanel,
  };
})();
