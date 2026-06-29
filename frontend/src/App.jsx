import { useEffect, useState } from "react";
import * as api from "./api";
import AuthPage from "./AuthPage.jsx";
import Dashboard from "./Dashboard.jsx";

/**
 * Top-level auth gate. Holds the session (token + email) in React state,
 * seeded from localStorage so a refresh keeps you logged in. Renders the login
 * /signup page when logged out, and the task dashboard when logged in.
 *
 * api.js broadcasts `tidu-unauthorized` when a protected request gets a 401
 * (expired/invalid token); we listen for it and drop back to the login page.
 */
export default function App() {
  const [token, setToken] = useState(() => api.getToken());
  const [email, setEmail] = useState(() => api.getEmail());

  useEffect(() => {
    const onUnauthorized = () => {
      setToken(null);
      setEmail("");
    };
    window.addEventListener("tidu-unauthorized", onUnauthorized);
    return () => window.removeEventListener("tidu-unauthorized", onUnauthorized);
  }, []);

  function handleAuthed({ access_token, email: userEmail }) {
    api.saveSession(access_token, userEmail);
    setToken(access_token);
    setEmail(userEmail);
  }

  function handleLogout() {
    api.clearSession();
    setToken(null);
    setEmail("");
  }

  if (!token) {
    return <AuthPage onAuthed={handleAuthed} />;
  }
  return <Dashboard email={email} onLogout={handleLogout} />;
}
