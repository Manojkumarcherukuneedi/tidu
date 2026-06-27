/**
 * Dropdown to filter the board by category. "All categories" maps to an empty
 * string, which App translates into an unfiltered GET /tasks.
 */
export default function CategoryFilter({ categories, value, onChange }) {
  return (
    <label className="filter">
      <span className="filter-label">Filter:</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All categories</option>
        {categories.map((category) => (
          <option key={category} value={category}>
            {category}
          </option>
        ))}
      </select>
    </label>
  );
}
