import TaskItem from "./TaskItem.jsx";

/**
 * A group of tasks. In the "All tasks" view it shows a labeled header
 * (Overdue / Today / Upcoming / No date / Completed). In a single sidebar view
 * the section is `headerless` — the sidebar nav already names it.
 */
export default function TaskSection({
  section,
  onUpdate,
  onDelete,
  onBreakdown,
  onSubtaskToggle,
  onSubtaskDelete,
}) {
  return (
    <section className={`task-section tone-${section.tone}`}>
      {!section.headerless && (
        <div className="section-head">
          <span className="section-dot" aria-hidden="true" />
          <h2 className="section-title">{section.title}</h2>
          <span className="section-count">{section.tasks.length}</span>
        </div>
      )}
      <ul className="task-list">
        {section.tasks.map((task) => (
          <TaskItem
            key={task.id}
            task={task}
            onUpdate={onUpdate}
            onDelete={onDelete}
            onBreakdown={onBreakdown}
            onSubtaskToggle={onSubtaskToggle}
            onSubtaskDelete={onSubtaskDelete}
          />
        ))}
      </ul>
    </section>
  );
}
