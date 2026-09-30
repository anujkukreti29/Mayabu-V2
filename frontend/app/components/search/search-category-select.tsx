import { useNavigate } from "react-router";
import { categoryDisplayName, resolvePublicCategories } from "~/lib/search/categories";
import { buildSearchHref, type SearchUrlState } from "~/lib/search/url";
import { cn } from "~/components/ui/cn";

export function SearchCategorySelect({
  state,
  publicCategories,
  className,
}: {
  state: SearchUrlState;
  publicCategories?: string[] | null;
  className?: string;
}) {
  const navigate = useNavigate();
  const categories = resolvePublicCategories(publicCategories);
  const current = state.category || "";

  return (
    <div className={cn("min-w-0", className)}>
      <label htmlFor="search-category" className="sr-only">
        Category
      </label>
      <select
        id="search-category"
        key={`category-${current}`}
        className="min-h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
        defaultValue={current}
        onChange={(event) => {
          const value = event.target.value;
          void navigate(
            buildSearchHref(state, {
              category: value || null,
              resetOffset: true,
            }),
          );
        }}
        aria-label="Filter by category"
      >
        <option value="">All categories</option>
        {categories.map((slug) => (
          <option key={slug} value={slug}>
            {categoryDisplayName(slug)}
          </option>
        ))}
      </select>
    </div>
  );
}
