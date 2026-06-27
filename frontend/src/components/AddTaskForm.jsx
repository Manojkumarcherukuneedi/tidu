import { useState } from "react";

/**
 * Controlled input for adding a task in natural language. Disables itself while
 * the request is in flight and clears only on success. Errors are surfaced by
 * App as a toast, so this component no longer renders its own error text — it
 * just avoids clearing the input when the add fails.
 */
export default function AddTaskForm({ onAdd }) {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;

    setSubmitting(true);
    try {
      await onAdd(trimmed);
      setText(""); // clear only on success
    } catch {
      /* App shows the error toast; keep the text so the user can retry */
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="add-form" onSubmit={handleSubmit}>
      <input
        type="text"
        className="add-input"
        placeholder='Add a task in plain language — e.g. "finish DB assignment by Friday"'
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={submitting}
        aria-label="New task"
      />
      <button type="submit" className="btn btn-primary" disabled={submitting}>
        {submitting ? "Adding…" : "Add task"}
      </button>
    </form>
  );
}
