import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as api from "./api";
import { computeStats, groupTasks } from "./taskUtils.js";
import AddTaskForm from "./components/AddTaskForm.jsx";
import StatsHeader from "./components/StatsHeader.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";
import Toolbar from "./components/Toolbar.jsx";
import TaskList from "./components/TaskList.jsx";
import TaskSkeleton from "./components/TaskSkeleton.jsx";
import ToastContainer from "./components/Toast.jsx";

/**
 * Smart container. Owns every piece of state and all API orchestration, then
 * passes plain data + callbacks down to presentational children (StatsHeader,
 * Toolbar, TaskList -> TaskSection -> TaskItem, ToastContainer). Theme and
 * toasts live in React state only — no browser storage.
 *
 * Derived views (stats, grouped sections) are computed with useMemo from the
 * raw `tasks` array, so the stats header and section grouping update live
 * whenever tasks change.
 */
export default function App() {
  const [tasks, setTasks] = useState([]);
  const [categories, setCategories] = useState([]);
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState("due");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [theme, setTheme] = useState("light");
  const [toasts, setToasts] = useState([]);

  // --- Theme (session-only; applied to <html> so CSS vars cascade) ----------
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // --- Toasts ----------------------------------------------------------------
  const toastId = useRef(0);
  const addToast = useCallback((type, message) => {
    const id = ++toastId.current;
    setToasts((prev) => [...prev, { id, type, message }]);
  }, []);
  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // --- Data loading ----------------------------------------------------------
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

  // Categories come from an unfiltered fetch so the dropdown always lists every
  // category, even while a filter is active.
  const loadCategories = useCallback(async () => {
    try {
      const all = await api.listTasks("");
      setCategories([...new Set(all.map((t) => t.category).filter(Boolean))].sort());
    } catch {
      /* non-fatal */
    }
  }, []);

  useEffect(() => {
    loadTasks(filter);
  }, [filter, loadTasks]);
  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  // --- Mutations (each shows a toast; errors re-throw for child UIs) ---------
  async function handleAdd(rawText) {
    try {
      const created = await api.createTask({ raw_text: rawText });
      await Promise.all([loadTasks(filter), loadCategories()]);
      const bits = [created.category, created.priority].filter(Boolean).join(" · ");
      addToast("success", bits ? `Added · ${bits}` : "Task added");
    } catch (err) {
      addToast("error", err.message);
      throw err;
    }
  }

  async function handleUpdate(id, patch) {
    try {
      const updated = await api.updateTask(id, patch);
      setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)));
      loadCategories();
      if ("completed" in patch) {
        addToast("success", patch.completed ? "Marked complete 🎉" : "Marked active");
      } else {
        addToast("success", "Task updated");
      }
    } catch (err) {
      addToast("error", err.message);
      throw err;
    }
  }

  async function handleDelete(id) {
    try {
      await api.deleteTask(id);
      setTasks((prev) => prev.filter((t) => t.id !== id));
      loadCategories();
      addToast("info", "Task deleted");
    } catch (err) {
      addToast("error", err.message);
      throw err;
    }
  }

  // --- Derived views (recompute when tasks/sort change) ----------------------
  const stats = useMemo(() => computeStats(tasks), [tasks]);
  const sections = useMemo(() => groupTasks(tasks, sort), [tasks, sort]);

  return (
    <div className="app-shell">
      <div className="app">
        <header className="app-header">
          <div className="title-row">
            <div>
              <h1>Tidu</h1>
              <p className="subtitle">
                Type a task in plain language — the AI fills in the category,
                priority, and due date.
              </p>
            </div>
            <ThemeToggle theme={theme} onToggle={() => setTheme((t) => (t === "light" ? "dark" : "light"))} />
          </div>
          <StatsHeader stats={stats} />
        </header>

        <AddTaskForm onAdd={handleAdd} />

        <Toolbar
          categories={categories}
          filter={filter}
          onFilterChange={setFilter}
          sort={sort}
          onSortChange={setSort}
        />

        {error && (
          <div className="banner banner-error" role="alert">
            <span>⚠️ {error}</span>
            <button className="btn btn-sm" onClick={() => loadTasks(filter)}>
              Retry
            </button>
          </div>
        )}

        {loading ? (
          <TaskSkeleton rows={4} />
        ) : (
          <TaskList
            sections={sections}
            filter={filter}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
          />
        )}
      </div>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
