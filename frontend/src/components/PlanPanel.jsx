/**
 * "Plan my day" modal. Presentational — Dashboard owns the plan state and the
 * open/close + retry callbacks. Shows a loading skeleton while the AI thinks,
 * a friendly error on failure, and the ordered plan (with the AI's reasoning)
 * on success. A `fallback` source is flagged so the user knows it's the basic
 * sort rather than an AI plan.
 */
export default function PlanPanel({ open, loading, error, plan, onClose, onRetry }) {
  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Plan for today"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <h2 className="modal-title">✨ Your plan for today</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {loading && (
          <div className="plan-skeleton" aria-hidden="true">
            <div className="skeleton-line shimmer" style={{ width: "80%" }} />
            <div className="skeleton-line shimmer" style={{ width: "60%" }} />
            <div className="skeleton-line shimmer" style={{ width: "70%" }} />
          </div>
        )}

        {!loading && error && (
          <div className="modal-error">
            <p>Couldn’t build a plan: {error}</p>
            <button className="btn btn-sm" onClick={onRetry}>
              Try again
            </button>
          </div>
        )}

        {!loading && !error && plan && (
          <>
            {plan.source === "fallback" && (
              <p className="plan-note">⚠ Basic plan — the AI was unavailable.</p>
            )}
            <p className="plan-summary">{plan.summary}</p>
            {plan.items.length === 0 ? (
              <p className="muted">Nothing to plan yet — add a few tasks first.</p>
            ) : (
              <ol className="plan-list">
                {plan.items.map((item, i) => (
                  <li key={`${item.task_id}-${i}`} className="plan-item">
                    <span className="plan-rank">{i + 1}</span>
                    <div className="plan-item-body">
                      <div className="plan-item-title">{item.title}</div>
                      <div className="plan-item-reason">{item.reason}</div>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </>
        )}
      </div>
    </div>
  );
}
