import { useState } from "react";
import * as api from "./api";

/**
 * Login / Signup page. A single form toggles between the two modes. On success
 * it calls onAuthed with the backend's { access_token, email }. Errors from the
 * backend (e.g. "Email already registered", "Invalid credentials") are shown
 * inline.
 */
export default function AuthPage({ onAuthed }) {
  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const isSignup = mode === "signup";

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);

    if (isSignup && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setSubmitting(true);
    try {
      const fn = isSignup ? api.signup : api.login;
      const result = await fn(email.trim(), password);
      onAuthed(result);
    } catch (err) {
      setError(cleanMessage(err.message));
    } finally {
      setSubmitting(false);
    }
  }

  function switchMode() {
    setMode(isSignup ? "login" : "signup");
    setError(null);
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">Tidu</div>
        <p className="auth-tagline">
          Plain-language tasks, organized by AI.
        </p>

        <h1 className="auth-title">{isSignup ? "Create your account" : "Welcome back"}</h1>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="auth-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              required
              disabled={submitting}
            />
          </label>

          <label className="auth-field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={isSignup ? "At least 8 characters" : "Your password"}
              autoComplete={isSignup ? "new-password" : "current-password"}
              required
              disabled={submitting}
            />
          </label>

          {error && <p className="auth-error" role="alert">{error}</p>}

          <button type="submit" className="btn btn-primary auth-submit" disabled={submitting}>
            {submitting ? "Please wait…" : isSignup ? "Sign up" : "Log in"}
          </button>
        </form>

        <p className="auth-switch">
          {isSignup ? "Already have an account?" : "New to Tidu?"}{" "}
          <button type="button" className="link" onClick={switchMode}>
            {isSignup ? "Log in" : "Create one"}
          </button>
        </p>
      </div>
    </div>
  );
}

// Surface the backend's detail without the "Request failed (NNN):" prefix.
function cleanMessage(message) {
  const m = /^Request failed \(\d+\): (.*)$/.exec(message);
  return m ? m[1] : message;
}
