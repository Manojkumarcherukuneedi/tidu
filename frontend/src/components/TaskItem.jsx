import { useState } from "react";
import { ClipboardList } from "lucide-react";
import { formatDueDate, isOverdue } from "../taskUtils.js";
import SubtaskRow from "./SubtaskRow.jsx";

const PRIORITIES = ["High", "Medium", "Low"];

/**
 * A single task card with view + inline-edit modes.
 *
 * Local state is only ephemeral UI: are we editing, the edit draft, a busy flag
 * during a request, and a `removing` flag that drives the exit animation before
 * the row actually unmounts. The persisted task is owned by App and arrives as
 * a prop; saves/toggles/deletes call back up via onUpdate / onDelete.
 */
export default function TaskItem({
  task,
  onUpdate,
  onDelete,
  onBreakdown,
  onSubtaskToggle,
  onSubtaskEdit,
  onSubtaskAdd,
  onSubtaskDelete,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(toDraft(task));
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [breakingDown, setBreakingDown] = useState(false);
  const [breakdownFailed, setBreakdownFailed] = useState(false);
  const [newStep, setNewStep] = useState("");

  const overdue = isOverdue(task);
  const subtasks = task.subtasks || [];

  async function handleAddStep(e) {
    e.preventDefault();
    const text = newStep.trim();
    if (!text) return;
    try {
      await onSubtaskAdd(task.id, text);
      setNewStep("");
    } catch {
      /* Dashboard toasts the error; keep the text so the user can retry */
    }
  }

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

  async function handleBreakdown() {
    setBreakingDown(true);
    setBreakdownFailed(false);
    try {
      const res = await onBreakdown(task.id);
      if (res && res.generated === false) setBreakdownFailed(true);
    } catch {
      setBreakdownFailed(true);
    } finally {
      setBreakingDown(false);
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
              {formatDueDate(task.due_date)}
            </span>
          )}
        </div>

        {breakingDown && <p className="subtask-status">Breaking into steps…</p>}
        {breakdownFailed && (
          <p className="subtask-status error">
            Couldn’t generate steps — try rephrasing the task.
          </p>
        )}
        {subtasks.length > 0 && (
          <ul className="subtask-list">
            {subtasks.map((st) => (
              <SubtaskRow
                key={st.id}
                subtask={st}
                onToggle={(s) => onSubtaskToggle(task.id, s)}
                onEdit={(id, text) => onSubtaskEdit(task.id, id, text)}
                onDelete={(id) => onSubtaskDelete(task.id, id)}
              />
            ))}
            <li className="subtask add-step">
              <form className="add-step-form" onSubmit={handleAddStep}>
                <span className="add-step-plus" aria-hidden="true">+</span>
                <input
                  className="subtask-input"
                  value={newStep}
                  maxLength={500}
                  placeholder="add step"
                  onChange={(e) => setNewStep(e.target.value)}
                  aria-label="Add a step"
                />
              </form>
            </li>
          </ul>
        )}
      </div>

      <div className="task-actions">
        <button
          className="btn btn-icon steps-btn"
          onClick={handleBreakdown}
          disabled={busy || breakingDown}
          title="Break into steps with AI"
        >
          {breakingDown ? (
            "…"
          ) : (
            <>
              <ClipboardList className="steps-icon" size={15} aria-hidden="true" />
              Steps
            </>
          )}
        </button>
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
