import { useState } from "react";

/**
 * Controlled text input for adding a task in natural language.
 * Disables itself while the request is in flight, surfaces its own error, and
 * clears the input on success.
 */
export default function AddTaskForm({ onAdd }) {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;

    setSubmitting(true);
    setError(null);
    try {
      await onAdd(trimmed);
      setText(""); // clear only on success
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="add-form" onSubmit={handleSubmit}>
      <input
        type="text"
        className="add-input"
        placeholder='e.g. "finish DB assignment by Friday"'
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={submitting}
        aria-label="New task"
      />
      <button type="submit" className="btn btn-primary" disabled={submitting}>
        {submitting ? "Adding…" : "Add task"}
      </button>
      {error && <p className="field-error">{error}</p>}
    </form>
  );
}
