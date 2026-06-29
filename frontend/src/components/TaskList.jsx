import TaskSection from "./TaskSection.jsx";

const EMPTY_BY_VIEW = {
  today: { icon: "🌤️", title: "Nothing due today", sub: "Enjoy the breathing room." },
  overdue: { icon: "🎉", title: "Nothing overdue", sub: "You're all caught up." },
  completed: { icon: "📭", title: "No completed tasks yet", sub: "Finish something to see it here." },
};

/**
 * Renders the grouped board for the active view, or an intentional empty state.
 *
 * The whole pane is keyed by `view`, so switching sidebar views remounts it and
 * plays a quick cross-fade (the `viewIn` animation) instead of a hard cut. The
 * grouping itself is computed by App and passed in as ready `sections`.
 */
export default function TaskList({
  sections,
  view,
  categoryFilter,
  onUpdate,
  onDelete,
  onBreakdown,
  onSubtaskToggle,
  onSubtaskDelete,
}) {
  const hasTasks = sections.some((s) => s.tasks.length > 0);

  let empty;
  if (view !== "all") {
    empty = EMPTY_BY_VIEW[view];
  } else if (categoryFilter) {
    empty = { icon: "🗂️", title: `No tasks in “${categoryFilter}”`, sub: "Try a different category filter." };
  } else {
    empty = {
      icon: "🗒️",
      title: "Your board is clear",
      sub: "Add a task above and the AI will sort out its category, priority, and due date.",
    };
  }

  return (
    <div className="view-pane" key={view}>
      {hasTasks ? (
        <div className="board">
          {sections.map((section) => (
            <TaskSection
              key={section.key}
              section={section}
              onUpdate={onUpdate}
              onDelete={onDelete}
              onBreakdown={onBreakdown}
              onSubtaskToggle={onSubtaskToggle}
              onSubtaskDelete={onSubtaskDelete}
            />
          ))}
        </div>
      ) : (
        <div className="empty">
          <div className="empty-icon">{empty.icon}</div>
          <p className="empty-title">{empty.title}</p>
          <p className="empty-sub">{empty.sub}</p>
        </div>
      )}
    </div>
  );
}
