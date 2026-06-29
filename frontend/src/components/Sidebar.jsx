import ThemeToggle from "./ThemeToggle.jsx";

// Nav items map 1:1 to client-side views derived from due_date / completed.
const NAV = [
  { key: "all", label: "All tasks", icon: "🗂️" },
  { key: "today", label: "Today", icon: "📅" },
  { key: "overdue", label: "Overdue", icon: "⚠️" },
  { key: "completed", label: "Completed", icon: "✓" },
];

/**
 * Left navigation. Presentational: it receives the active view, the per-view
 * counts, and theme state, and emits selection / toggle callbacks. On mobile it
 * becomes an off-canvas drawer (the `open` prop drives the CSS transform); the
 * backdrop and the responsive behavior are handled in CSS.
 */
export default function Sidebar({
  activeView,
  counts,
  onSelectView,
  theme,
  onToggleTheme,
  open,
}) {
  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="sidebar-brand">Tidu</div>

      <nav className="sidebar-nav">
        {NAV.map((item) => {
          const count = counts[item.key] ?? 0;
          const isActive = activeView === item.key;
          const danger = item.key === "overdue" && count > 0;
          return (
            <button
              key={item.key}
              className={`nav-item ${isActive ? "active" : ""}`}
              onClick={() => onSelectView(item.key)}
              aria-current={isActive ? "page" : undefined}
            >
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
              {count > 0 && (
                <span className={`nav-badge ${danger ? "danger" : ""}`}>{count}</span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        <span className="footer-label">
          {theme === "dark" ? "Dark mode" : "Light mode"}
        </span>
      </div>
    </aside>
  );
}
