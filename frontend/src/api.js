// Single source of truth for the backend location. Change it here only.
export const API_BASE_URL = "http://127.0.0.1:8000";

/**
 * Thin wrapper around fetch that centralizes error handling so every component
 * gets consistent, friendly errors instead of raw exceptions.
 *  - Network failure (backend down) -> a clear "can't reach server" message.
 *  - Non-2xx response -> surfaces the backend's JSON `detail` when present.
 *  - 204 No Content (DELETE) -> returns null instead of trying to parse a body.
 */
async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error(
      `Can't reach the server at ${API_BASE_URL}. Is the backend running?`
    );
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

// --- Endpoint helpers. These mirror the backend's REST routes. ---------------

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
