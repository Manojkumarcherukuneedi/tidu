import { useState } from "react";

/**
 * One subtask: a toggle checkbox, inline-editable text (click to edit, save on
 * blur/Enter, cancel on Escape), and a delete button. Owns only its own edit
 * draft; the persisted subtask arrives as a prop and changes flow up via the
 * callbacks (bound to the parent task in TaskItem).
 */
export default function SubtaskRow({ subtask, onToggle, onEdit, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(subtask.text);

  function startEditing() {
    setDraft(subtask.text);
    setEditing(true);
  }

  function save() {
    setEditing(false);
    const text = draft.trim();
    if (text && text !== subtask.text) onEdit(subtask.id, text);
    else setDraft(subtask.text); // empty or unchanged — revert
  }

  function onKeyDown(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      e.target.blur(); // triggers save via onBlur
    } else if (e.key === "Escape") {
      setDraft(subtask.text);
      setEditing(false);
    }
  }

  return (
    <li className={`subtask ${subtask.completed ? "done" : ""}`}>
      <button
        className={`subtask-check ${subtask.completed ? "checked" : ""}`}
        onClick={() => onToggle(subtask)}
        aria-pressed={subtask.completed}
        aria-label="Toggle step"
      >
        <span className="check-mark">✓</span>
      </button>

      {editing ? (
        <input
          className="subtask-input"
          value={draft}
          autoFocus
          maxLength={500}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={save}
          onKeyDown={onKeyDown}
        />
      ) : (
        <span
          className="subtask-text"
          onClick={startEditing}
          onKeyDown={(e) => e.key === "Enter" && startEditing()}
          role="button"
          tabIndex={0}
          title="Click to edit"
        >
          {subtask.text}
        </span>
      )}

      <button
        className="subtask-del"
        onClick={() => onDelete(subtask.id)}
        aria-label="Delete step"
      >
        ×
      </button>
    </li>
  );
}
