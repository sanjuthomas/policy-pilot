(function () {
  const KEY = "tech-auditor-session";

  function session() {
    try {
      return JSON.parse(localStorage.getItem(KEY) || "null");
    } catch {
      return null;
    }
  }

  function headers() {
    const current = session();
    return current
      ? {
          Authorization: `Bearer ${current.session_token}`,
          "X-Session-Id": current.session_id,
        }
      : {};
  }

  async function apiFetch(url, options = {}) {
    return fetch(url, {
      ...options,
      headers: { ...headers(), ...(options.headers || {}) },
    });
  }

  async function login(userId, password) {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, password }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
    localStorage.setItem(KEY, JSON.stringify(body));
    return body;
  }

  function logout() {
    localStorage.removeItem(KEY);
    location.reload();
  }

  function bind(onReady) {
    const status = document.getElementById("auth-status");
    const user = document.getElementById("auth-user");
    const password = document.getElementById("auth-password");
    const loginButton = document.getElementById("auth-login");
    const logoutButton = document.getElementById("auth-logout");

    async function ready() {
      const current = session();
      if (!current) {
        status.textContent = "Technology auditor sign-in required";
        return;
      }
      const response = await apiFetch("/api/me");
      if (!response.ok) {
        localStorage.removeItem(KEY);
        status.textContent =
          response.status === 403 ? "TECH_AUDITORS membership required" : "Sign in required";
        return;
      }
      const subject = await response.json();
      status.textContent = `Signed in as ${subject.user_id}`;
      user.classList.add("hidden");
      password.classList.add("hidden");
      loginButton.classList.add("hidden");
      logoutButton.classList.remove("hidden");
      onReady?.();
    }

    loginButton.addEventListener("click", async () => {
      loginButton.disabled = true;
      try {
        await login(user.value, password.value);
        await ready();
      } catch (error) {
        status.textContent = `Login failed: ${error.message}`;
      } finally {
        loginButton.disabled = false;
      }
    });
    logoutButton.addEventListener("click", logout);
    void ready();
  }

  window.AuditorAuth = { apiFetch, bind, session };
})();
