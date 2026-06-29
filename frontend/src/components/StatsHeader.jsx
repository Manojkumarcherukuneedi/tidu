import { useCountUp } from "../useCountUp.js";

/**
 * One stat card. The number animates from its previous value to the new one via
 * useCountUp (which itself respects prefers-reduced-motion). It's a separate
 * component because hooks can't be called inside a map callback conditionally.
 */
function StatCard({ label, value, tone }) {
  const display = useCountUp(value);
  return (
    <div className={`stat-card stat-${tone}`}>
      <span className="stat-value">{display}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

/** Live summary stats. Overdue turns red when there's anything overdue. */
export default function StatsHeader({ stats }) {
  const cards = [
    { label: "Total", value: stats.total, tone: "neutral" },
    { label: "Completed", value: stats.completed, tone: "success" },
    { label: "Overdue", value: stats.overdue, tone: stats.overdue > 0 ? "danger" : "neutral" },
  ];
  return (
    <div className="stats">
      {cards.map((c) => (
        <StatCard key={c.label} {...c} />
      ))}
    </div>
  );
}
