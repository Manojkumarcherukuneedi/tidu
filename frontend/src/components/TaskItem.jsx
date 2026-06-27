import { useState } from "react";
import { isOverdue } from "../taskUtils.js";

const PRIORITIES = ["High", "Medium", "Low"];

/**
 * A single task card with view + inline-edit modes.
 *
 * Local state is only ephemeral UI: are we editing, the edit draft, a busy flag
 * during a request, and a `removing` flag that drives the exit animation before
 * the row actually unmounts. The persisted task is owned by App and arrives as
 * a prop; saves/toggles/deletes call back up via onUpdate / onDelete.
 */
export default function TaskItem({ task, onUpdate, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(toDraft(task));
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState(false);

  const overdue = isOverdue(task);

  function toggleComplete() {
    setBusy(true);
    Promise.resolve(onUpdate(task.id, { completed: !task.completed })).finally(
      () => setBusy(false)
    );
  }

  function startEditing() {
    setDraft(toDraft(task));
    setEditing(true);
  }

  async function saveEdit() {
    setBusy(true);
    try {
      await onUpdate(task.id, {
        title: draft.title.trim() || null,
        category: draft.category.trim() || null,
        priority: draft.priority,
      });
      setEditing(false);
    } catch {
      /* App toasts the error; stay in edit mode so nothing is lost */
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    setRemoving(true); // play the exit animation first
    await new Promise((r) => setTimeout(r, 220));
    try {
      await onDelete(task.id);
    } catch {
      setRemoving(false); // delete failed — bring the card back
    }
  }

  if (editing) {
    return (
      <li className="task-item editing">
        <div className="edit-fields">
          <label>
            Title
            <input
              value={draft.title}
              onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              placeholder={task.raw_text}
              autoFocus
            />
          </label>
          <label>
            Category
            <input
              value={draft.category}
              onChange={(e) => setDraft({ ...draft, category: e.target.value })}
            />
          </label>
          <label>
            Priority
            <select
              value={draft.priority}
              onChange={(e) => setDraft({ ...draft, priority: e.target.value })}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="task-actions">
          <button className="btn btn-primary" onClick={saveEdit} disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </button>
          <button className="btn" onClick={() => setEditing(false)} disabled={busy}>
            Cancel
          </button>
        </div>
      </li>
    );
  }

  const cls = [
    "task-item",
    task.completed ? "completed" : "",
    overdue ? "overdue" : "",
    removing ? "removing" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <li className={cls}>
      <button
        className={`check ${task.completed ? "checked" : ""}`}
        onClick={toggleComplete}
        disabled={busy}
        aria-pressed={task.completed}
        aria-label={task.completed ? "Mark as not done" : "Mark complete"}
      >
        <span className="check-mark">✓</span>
      </button>

      <div className="task-body">
        <span className="task-title">{task.title || task.raw_text}</span>
        <div className="task-meta">
          {task.category && <span className="badge category">{task.category}</span>}
          <span className={`badge priority-${(task.priority || "Medium").toLowerCase()}`}>
            {task.priority || "Medium"}
          </span>
          {task.due_date && (
            <span className={`due ${overdue ? "due-overdue" : ""}`}>
              {overdue ? "⚠ Overdue · " : "📅 "}
              {task.due_date}
            </span>
          )}
        </div>
      </div>

      <div className="task-actions">
        <button className="btn btn-icon" onClick={startEditing} disabled={busy}>
          Edit
        </button>
        <button className="btn btn-icon btn-danger" onClick={handleDelete} disabled={busy}>
          Delete
        </button>
      </div>
    </li>
  );
}

function toDraft(task) {
  return {
    title: task.title ?? "",
    category: task.category ?? "",
    priority: task.priority ?? "Medium",
  };
}
