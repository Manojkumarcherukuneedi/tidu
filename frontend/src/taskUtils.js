// Pure, framework-free helpers for deriving views over the task list.
// Kept out of components so the date/grouping logic is testable and obvious.

/** Local "today" as a YYYY-MM-DD string, comparable lexicographically with
 *  the backend's ISO due_date strings. */
export function todayStr() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** A task is overdue if it has a past due date and isn't done yet. */
export function isOverdue(task, today = todayStr()) {
  return Boolean(task.due_date) && !task.completed && task.due_date < today;
}

/** Which section a task belongs to. Completed always wins. */
export function bucketOf(task, today = todayStr()) {
  if (task.completed) return "completed";
  if (!task.due_date) return "noDate";
  if (task.due_date < today) return "overdue";
  if (task.due_date === today) return "today";
  return "upcoming";
}

const PRIORITY_RANK = { High: 0, Medium: 1, Low: 2 };

function sortTasks(tasks, sort) {
  const copy = [...tasks];
  if (sort === "priority") {
    copy.sort(
      (a, b) =>
        (PRIORITY_RANK[a.priority] ?? 1) - (PRIORITY_RANK[b.priority] ?? 1)
    );
  } else {
    // "due": earliest first, tasks without a date last.
    copy.sort((a, b) => {
      if (!a.due_date && !b.due_date) return 0;
      if (!a.due_date) return 1;
      if (!b.due_date) return -1;
      return a.due_date < b.due_date ? -1 : a.due_date > b.due_date ? 1 : 0;
    });
  }
  return copy;
}

// Section definitions in display order. `tone` drives the accent color.
const SECTION_ORDER = [
  { key: "overdue", title: "Overdue", tone: "danger" },
  { key: "today", title: "Today", tone: "accent" },
  { key: "upcoming", title: "Upcoming", tone: "neutral" },
  { key: "noDate", title: "No date", tone: "neutral" },
  { key: "completed", title: "Completed", tone: "muted" },
];

/** Group tasks into ordered, sorted sections. Empty sections are dropped. */
export function groupTasks(tasks, sort = "due", today = todayStr()) {
  const buckets = { overdue: [], today: [], upcoming: [], noDate: [], completed: [] };
  for (const task of tasks) buckets[bucketOf(task, today)].push(task);

  return SECTION_ORDER.filter((s) => buckets[s.key].length > 0).map((s) => ({
    ...s,
    tasks: sortTasks(buckets[s.key], sort),
  }));
}

/** Live stats for the header. */
export function computeStats(tasks, today = todayStr()) {
  return {
    total: tasks.length,
    completed: tasks.filter((t) => t.completed).length,
    overdue: tasks.filter((t) => isOverdue(t, today)).length,
  };
}
