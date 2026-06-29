import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as api from "./api";
import { buildSections, computeViewCounts } from "./taskUtils.js";
import AddTaskForm from "./components/AddTaskForm.jsx";
import Sidebar from "./components/Sidebar.jsx";
import StatsHeader from "./components/StatsHeader.jsx";
import Toolbar from "./components/Toolbar.jsx";
import TaskList from "./components/TaskList.jsx";
import TaskSkeleton from "./components/TaskSkeleton.jsx";
import ToastContainer from "./components/Toast.jsx";

/**
 * The authenticated task dashboard (formerly App). Smart container: owns all
 * task state + API orchestration; children are presentational. Auth itself
 * lives one level up in App — this component just receives the logged-in
 * `email` and an `onLogout` callback to pass to the sidebar. All task requests
 * automatically carry the Bearer token (handled in api.js).
 */
export default function Dashboard({ email, onLogout }) {
  const [tasks, setTasks] = useState([]);
  const [categories, setCategories] = useState([]);
  const [filter, setFilter] = useState(""); // category (server-side)
  const [sort, setSort] = useState("due");
  const [view, setView] = useState("all"); // sidebar view (client-side)
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [theme, setTheme] = useState("light");
  const [toasts, setToasts] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(false); // mobile drawer

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

  // --- Mutations -------------------------------------------------------------
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

  function selectView(next) {
    setView(next);
    setSidebarOpen(false); // close the drawer after navigating on mobile
  }

  // --- Derived views ---------------------------------------------------------
  const counts = useMemo(() => computeViewCounts(tasks), [tasks]);
  const stats = useMemo(
    () => ({ total: counts.all, completed: counts.completed, overdue: counts.overdue }),
    [counts]
  );
  const sections = useMemo(() => buildSections(tasks, view, sort), [tasks, view, sort]);

  return (
    <div className="app-shell">
      <div className="layout">
        <Sidebar
          activeView={view}
          counts={counts}
          onSelectView={selectView}
          theme={theme}
          onToggleTheme={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
          open={sidebarOpen}
          email={email}
          onLogout={onLogout}
        />
        <div
          className={`backdrop ${sidebarOpen ? "show" : ""}`}
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />

        <main className="main">
          <header className="topbar">
            <button
              className="hamburger"
              onClick={() => setSidebarOpen((o) => !o)}
              aria-label="Toggle navigation"
            >
              ☰
            </button>
            <span className="topbar-title">Tidu</span>
          </header>

          <div className="content">
            <StatsHeader stats={stats} />
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
                view={view}
                categoryFilter={filter}
                onUpdate={handleUpdate}
                onDelete={handleDelete}
              />
            )}
          </div>
        </main>
      </div>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
