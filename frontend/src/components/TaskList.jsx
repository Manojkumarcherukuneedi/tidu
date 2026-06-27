import TaskItem from "./TaskItem.jsx";

/**
 * Renders the list of tasks, or a friendly empty state. Purely presentational —
 * it just maps data to TaskItem and forwards the callbacks.
 */
export default function TaskList({ tasks, filter, onUpdate, onDelete }) {
  if (tasks.length === 0) {
    return (
      <div className="empty">
        {filter ? (
          <p>
            No tasks in <strong>{filter}</strong>. Try a different filter.
          </p>
        ) : (
          <p>No tasks yet. Add one above to get started. ✨</p>
        )}
      </div>
    );
  }

  return (
    <ul className="task-list">
      {tasks.map((task) => (
        <TaskItem
          key={task.id}
          task={task}
          onUpdate={onUpdate}
          onDelete={onDelete}
        />
      ))}
    </ul>
  );
}
