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

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/**
 * Format an ISO date (YYYY-MM-DD) for DISPLAY only — e.g. "July 3", or
 * "July 3, 2027" when it's not the current year. We parse the string parts
 * rather than `new Date(iso)` to avoid timezone off-by-one (an ISO date string
 * is parsed as UTC midnight, which can shift the day in local time). Storage
 * and API traffic stay ISO — this is purely presentational.
 */
export function formatDueDate(iso) {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso; // not an ISO date — show as-is
  const year = Number(m[1]);
  const month = Number(m[2]);
  const day = Number(m[3]);
  const label = `${MONTHS[month - 1]} ${day}`;
  return year === new Date().getFullYear() ? label : `${label}, ${year}`;
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

/** Counts used by both the stats row and the sidebar nav badges. */
export function computeViewCounts(tasks, today = todayStr()) {
  return {
    all: tasks.length,
    today: tasks.filter((t) => bucketOf(t, today) === "today").length,
    overdue: tasks.filter((t) => isOverdue(t, today)).length,
    completed: tasks.filter((t) => t.completed).length,
  };
}

// Metadata for the single-bucket sidebar views (everything except "all").
const VIEW_META = {
  today: { title: "Today", tone: "accent", match: (t, d) => bucketOf(t, d) === "today" },
  overdue: { title: "Overdue", tone: "danger", match: (t, d) => isOverdue(t, d) },
  completed: { title: "Completed", tone: "muted", match: (t) => t.completed },
};

/**
 * Build the sections to render for the active sidebar view.
 *
 *  - "all"  -> the full grouped board (Overdue / Today / Upcoming / No date /
 *              Completed) with section headers, via groupTasks.
 *  - else   -> a single flat, sorted list for that view, with no header (the
 *              sidebar nav already labels it). This is the one place sidebar
 *              filtering lives, and it reuses the same bucket logic as the
 *              grouping — no duplicated date rules.
 */
export function buildSections(tasks, view, sort = "due", today = todayStr()) {
  if (view === "all" || !VIEW_META[view]) {
    return groupTasks(tasks, sort, today);
  }
  const meta = VIEW_META[view];
  const filtered = sortTasks(
    tasks.filter((t) => meta.match(t, today)),
    sort
  );
  if (filtered.length === 0) return [];
  return [{ key: view, title: meta.title, tone: meta.tone, headerless: true, tasks: filtered }];
}
