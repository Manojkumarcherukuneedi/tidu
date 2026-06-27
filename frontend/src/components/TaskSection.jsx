import TaskItem from "./TaskItem.jsx";

/**
 * A titled group of tasks (Overdue / Today / Upcoming / No date / Completed).
 * Presentational: it gets a section descriptor + the shared callbacks and maps
 * tasks to TaskItem. The `tone` drives a colored accent on the heading.
 */
export default function TaskSection({ section, onUpdate, onDelete }) {
  return (
    <section className={`task-section tone-${section.tone}`}>
      <div className="section-head">
        <span className="section-dot" aria-hidden="true" />
        <h2 className="section-title">{section.title}</h2>
        <span className="section-count">{section.tasks.length}</span>
      </div>
      <ul className="task-list">
        {section.tasks.map((task) => (
          <TaskItem
            key={task.id}
            task={task}
            onUpdate={onUpdate}
            onDelete={onDelete}
          />
        ))}
      </ul>
    </section>
  );
}
