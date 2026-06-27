import { useState } from "react";

const PRIORITIES = ["High", "Medium", "Low"];

/**
 * A single task row with two modes:
 *  - view mode: complete checkbox, title/raw_text, category + priority badges,
 *    due date, and Edit/Delete actions.
 *  - edit mode: inline inputs for title, category, and priority.
 *
 * Local component state covers only the editing UI (whether we're editing and
 * the draft field values). The persisted task data is owned by App and flows in
 * as props — saving calls back up via onUpdate.
 */
export default function TaskItem({ task, onUpdate, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({
    title: task.title ?? "",
    category: task.category ?? "",
    priority: task.priority ?? "Medium",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function run(action) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function toggleComplete() {
    run(() => onUpdate(task.id, { completed: !task.completed }));
  }

  function startEditing() {
    setDraft({
      title: task.title ?? "",
      category: task.category ?? "",
      priority: task.priority ?? "Medium",
    });
    setError(null);
    setEditing(true);
  }

  async function saveEdit() {
    await run(async () => {
      await onUpdate(task.id, {
        title: draft.title.trim() || null,
        category: draft.category.trim() || null,
        priority: draft.priority,
      });
      setEditing(false);
    });
  }

  const priorityClass = `badge priority-${(task.priority || "Medium").toLowerCase()}`;

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
          <button
            className="btn"
            onClick={() => setEditing(false)}
            disabled={busy}
          >
            Cancel
          </button>
        </div>
        {error && <p className="field-error">{error}</p>}
      </li>
    );
  }

  return (
    <li className={`task-item ${task.completed ? "completed" : ""}`}>
      <input
        type="checkbox"
        className="check"
        checked={task.completed}
        onChange={toggleComplete}
        disabled={busy}
        aria-label="Mark complete"
      />

      <div className="task-body">
        <span className="task-title">{task.title || task.raw_text}</span>
        <div className="task-meta">
          {task.category && <span className="badge category">{task.category}</span>}
          <span className={priorityClass}>{task.priority || "Medium"}</span>
          {task.due_date && <span className="due">📅 {task.due_date}</span>}
        </div>
        {error && <p className="field-error">{error}</p>}
      </div>

      <div className="task-actions">
        <button className="btn" onClick={startEditing} disabled={busy}>
          Edit
        </button>
        <button
          className="btn btn-danger"
          onClick={() => run(() => onDelete(task.id))}
          disabled={busy}
        >
          Delete
        </button>
      </div>
    </li>
  );
}
