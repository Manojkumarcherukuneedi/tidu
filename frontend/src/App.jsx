import { useCallback, useEffect, useState } from "react";
import * as api from "./api";
import AddTaskForm from "./components/AddTaskForm.jsx";
import CategoryFilter from "./components/CategoryFilter.jsx";
import TaskList from "./components/TaskList.jsx";

/**
 * App is the single stateful "container" component. It owns the task list and
 * all the API orchestration, and passes plain data + callbacks down to the
 * presentational components (AddTaskForm, CategoryFilter, TaskList, TaskItem).
 * This "state lives at the top, children are mostly dumb" pattern keeps data
 * flow one-directional and easy to follow.
 */
export default function App() {
  const [tasks, setTasks] = useState([]);
  const [categories, setCategories] = useState([]);
  const [filter, setFilter] = useState(""); // "" means "All categories"
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load the displayed list. Uses the backend's ?category= filter so filtering
  // happens server-side (requirement) rather than in the browser.
  const loadTasks = useCallback(async (activeFilter) => {
    setLoading(true);
    setError(null);
    try {
      setTasks(await api.listTasks(activeFilter));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Categories come from an UNfiltered fetch so the dropdown always lists every
  // category, even while a filter is active. The AI can invent new categories,
  // so we refresh this after every mutation.
  const loadCategories = useCallback(async () => {
    try {
      const all = await api.listTasks("");
      const unique = [...new Set(all.map((t) => t.category).filter(Boolean))];
      setCategories(unique.sort());
    } catch {
      /* non-fatal: the filter just won't populate */
    }
  }, []);

  // Re-fetch the list whenever the filter changes (and once on mount).
  useEffect(() => {
    loadTasks(filter);
  }, [filter, loadTasks]);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  async function handleAdd(rawText) {
    // POST returns the AI-enriched task; reload so it (and any new category)
    // shows up immediately.
    await api.createTask({ raw_text: rawText });
    await Promise.all([loadTasks(filter), loadCategories()]);
  }

  async function handleUpdate(id, patch) {
    const updated = await api.updateTask(id, patch);
    // Update in place for a snappy UI; refresh categories in case it changed.
    setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)));
    loadCategories();
  }

  async function handleDelete(id) {
    await api.deleteTask(id);
    setTasks((prev) => prev.filter((t) => t.id !== id));
    loadCategories();
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI Task Organizer</h1>
        <p className="subtitle">
          Type a task in plain language — the AI fills in the category,
          priority, and due date.
        </p>
      </header>

      <AddTaskForm onAdd={handleAdd} />

      <div className="toolbar">
        <CategoryFilter
          categories={categories}
          value={filter}
          onChange={setFilter}
        />
        <span className="count">
          {tasks.length} {tasks.length === 1 ? "task" : "tasks"}
        </span>
      </div>

      {error && (
        <div className="banner banner-error" role="alert">
          ⚠️ {error}
          <button className="link" onClick={() => loadTasks(filter)}>
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <p className="muted">Loading tasks…</p>
      ) : (
        <TaskList
          tasks={tasks}
          filter={filter}
          onUpdate={handleUpdate}
          onDelete={handleDelete}
        />
      )}
    </div>
  );
}
