/**
 * Theme toggle button. Theme lives in React state in App (no localStorage),
 * so the choice persists for the session only. This component is stateless —
 * it shows the icon for the *other* theme and emits onToggle.
 */
export default function ThemeToggle({ theme, onToggle }) {
  const isDark = theme === "dark";
  return (
    <button
      className="theme-toggle"
      onClick={onToggle}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Light mode" : "Dark mode"}
    >
      {isDark ? "☀️" : "🌙"}
    </button>
  );
}
