/**
 * Shimmering placeholder rows shown while the first fetch is in flight.
 * Communicates "content is coming" far better than a bare spinner.
 */
export default function TaskSkeleton({ rows = 4 }) {
  return (
    <div className="skeleton-wrap" aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div className="skeleton-row" key={i}>
          <div className="skeleton-check shimmer" />
          <div className="skeleton-body">
            <div className="skeleton-line shimmer" style={{ width: "55%" }} />
            <div className="skeleton-badges">
              <div className="skeleton-badge shimmer" />
              <div className="skeleton-badge shimmer" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
