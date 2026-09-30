import { useNavigate } from "react-router";
import { buildSearchHref, type SearchSort, type SearchUrlState } from "~/lib/search/url";
import { cn } from "~/components/ui/cn";

const SORT_OPTIONS: Array<{ value: SearchSort; label: string }> = [
  { value: "relevance", label: "Relevance" },
  { value: "price_asc", label: "Price: Low to High" },
  { value: "price_desc", label: "Price: High to Low" },
  { value: "recently_checked", label: "Recently checked" },
];

export function SearchSortSelect({
  state,
  className,
}: {
  state: SearchUrlState;
  className?: string;
}) {
  const navigate = useNavigate();
  const current: SearchSort =
    state.sort === "price_asc" ||
    state.sort === "price_desc" ||
    state.sort === "recently_checked"
      ? state.sort
      : "relevance";

  return (
    <div className={cn("min-w-0", className)}>
      <label htmlFor="search-sort" className="sr-only">
        Sort results
      </label>
      <select
        id="search-sort"
        key={`sort-${current}`}
        className="min-h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
        defaultValue={current}
        onChange={(event) => {
          const next = event.target.value;
          const sort: SearchSort =
            next === "price_asc" || next === "price_desc" || next === "recently_checked"
              ? next
              : "relevance";
          void navigate(
            buildSearchHref(state, {
              sort,
              resetOffset: true,
            }),
          );
        }}
        aria-label="Sort results"
      >
        {SORT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
