/**
 * Live summary stats. Pure presentational — receives the already-computed
 * numbers from App and just renders three cards. The Overdue card turns red
 * when there's anything overdue, so it reads as a warning at a glance.
 */
export default function StatsHeader({ stats }) {
  const cards = [
    { label: "Total", value: stats.total, tone: "neutral" },
    { label: "Completed", value: stats.completed, tone: "success" },
    {
      label: "Overdue",
      value: stats.overdue,
      tone: stats.overdue > 0 ? "danger" : "neutral",
    },
  ];

  return (
    <div className="stats">
      {cards.map((c) => (
        <div key={c.label} className={`stat-card stat-${c.tone}`}>
          <span className="stat-value">{c.value}</span>
          <span className="stat-label">{c.label}</span>
        </div>
      ))}
    </div>
  );
}
