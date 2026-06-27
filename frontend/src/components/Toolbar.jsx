/**
 * Filter + sort controls. Both are simple controlled <select>s driven by App
 * state. Category filter uses the backend ?category= param; sort is applied
 * client-side within each section.
 */
export default function Toolbar({
  categories,
  filter,
  onFilterChange,
  sort,
  onSortChange,
}) {
  return (
    <div className="toolbar">
      <label className="control">
        <span className="control-label">Category</span>
        <select value={filter} onChange={(e) => onFilterChange(e.target.value)}>
          <option value="">All</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>

      <label className="control">
        <span className="control-label">Sort</span>
        <select value={sort} onChange={(e) => onSortChange(e.target.value)}>
          <option value="due">Due date</option>
          <option value="priority">Priority</option>
        </select>
      </label>
    </div>
  );
}
