import TaskSection from "./TaskSection.jsx";

/**
 * Renders the grouped task board, or an intentional empty state. The grouping
 * is computed by App (useMemo over taskUtils.groupTasks) and passed in as
 * ready-to-render `sections`, keeping this component purely presentational.
 */
export default function TaskList({ sections, filter, onUpdate, onDelete }) {
  const hasTasks = sections.some((s) => s.tasks.length > 0);

  if (!hasTasks) {
    return (
      <div className="empty">
        <div className="empty-icon">🗒️</div>
        {filter ? (
          <>
            <p className="empty-title">No tasks in “{filter}”</p>
            <p className="empty-sub">Try a different category filter.</p>
          </>
        ) : (
          <>
            <p className="empty-title">Your board is clear</p>
            <p className="empty-sub">
              Add a task above and the AI will sort out its category, priority,
              and due date.
            </p>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="board">
      {sections.map((section) => (
        <TaskSection
          key={section.key}
          section={section}
          onUpdate={onUpdate}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}
