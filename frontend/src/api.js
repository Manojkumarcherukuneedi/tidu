// Single source of truth for the backend location. Change it here only.
export const API_BASE_URL = "http://127.0.0.1:8000";

// --- Token storage (Slice 6) -------------------------------------------------
// This is the real browser, so localStorage is the right place to persist the
// JWT across refreshes. Token + email live under these keys.
const TOKEN_KEY = "tidu_token";
const EMAIL_KEY = "tidu_email";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const getEmail = () => localStorage.getItem(EMAIL_KEY) || "";
export function saveSession(token, email) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(EMAIL_KEY, email);
}
export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EMAIL_KEY);
}

/**
 * Thin wrapper around fetch. Centralizes:
 *  - attaching the Bearer token (from localStorage) to every request;
 *  - friendly errors (network down, backend `detail`);
 *  - 401 handling: on an expired/invalid token for a PROTECTED endpoint, clear
 *    the session and broadcast `tidu-unauthorized` so App can show the login
 *    page. Auth endpoints (/auth/*) are exempt — a 401 there means "bad
 *    credentials" and should surface to the form, not log the user out.
 */
async function request(path, options = {}) {
  const token = getToken();
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...options,
    });
  } catch {
    throw new Error(
      `Can't reach the server at ${API_BASE_URL}. Is the backend running?`
    );
  }

  if (response.status === 401 && !path.startsWith("/auth/")) {
    clearSession();
    window.dispatchEvent(new Event("tidu-unauthorized"));
    throw new Error("Your session has expired. Please log in again.");
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body && body.detail) {
        detail =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch {
      /* response had no JSON body; fall back to statusText */
    }
    throw new Error(`Request failed (${response.status}): ${detail}`);
  }

  if (response.status === 204) return null;
  return response.json();
}

// --- Auth endpoints ----------------------------------------------------------
export function signup(email, password) {
  return request("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function login(email, password) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

// --- Task endpoints (token attached automatically) ---------------------------
export function listTasks(category) {
  const query = category ? `?category=${encodeURIComponent(category)}` : "";
  return request(`/tasks${query}`);
}

export function createTask(payload) {
  return request("/tasks", { method: "POST", body: JSON.stringify(payload) });
}

export function updateTask(id, patch) {
  return request(`/tasks/${id}`, { method: "PUT", body: JSON.stringify(patch) });
}

export function deleteTask(id) {
  return request(`/tasks/${id}`, { method: "DELETE" });
}
