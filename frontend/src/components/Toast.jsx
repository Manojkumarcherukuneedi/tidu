/**
 * Lightweight toast system — no external library.
 * App owns the `toasts` array and an `addToast` helper; this file just renders
 * them. Each toast auto-dismisses via a timer set when it mounts.
 */
import { useEffect } from "react";

const ICONS = { success: "✓", error: "⚠️", info: "•" };

function Toast({ toast, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 3000);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  return (
    <div className={`toast toast-${toast.type}`} role="status">
      <span className="toast-icon">{ICONS[toast.type] || ICONS.info}</span>
      <span className="toast-msg">{toast.message}</span>
      <button
        className="toast-close"
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  );
}

export default function ToastContainer({ toasts, onDismiss }) {
  return (
    <div className="toast-container" aria-live="polite">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
