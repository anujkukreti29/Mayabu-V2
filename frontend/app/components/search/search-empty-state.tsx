import { Link } from "react-router";
import { EmptyState } from "~/components/ui/empty-state";
import { categoryDisplayName } from "~/lib/search/categories";
import { facetLabel } from "~/lib/search/facets";
import { routes } from "~/lib/navigation/routes";
import { buildSearchHref, type SearchUrlState } from "~/lib/search/url";

const SEARCH_EXAMPLES = [
  "Gaming laptop under ₹70,000",
  "Galaxy S24",
  "55 inch OLED TV",
  "260 L refrigerator",
  "8kg front load washing machine",
  "ANC earbuds",
  "Sony headphones",
] as const;

function SuggestionChips({ examples = SEARCH_EXAMPLES }: { examples?: readonly string[] }) {
  return (
    <div className="mt-5 flex flex-wrap gap-2">
      {examples.map((item) => (
        <Link
          key={item}
          to={`${routes.search}?q=${encodeURIComponent(item)}`}
          className="inline-flex min-h-10 items-center rounded-lg border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-700 hover:border-brand-300 hover:bg-brand-50"
        >
          {item}
        </Link>
      ))}
    </div>
  );
}

export function SearchNoQueryState() {
  return (
    <div className="mt-10 max-w-3xl">
      <EmptyState
        title="Try a search"
        description="Search products, models, brands, or categories across laptops, phones, TVs, appliances, and audio."
      />
      <p className="mt-5 text-xs font-semibold uppercase tracking-wide text-slate-500">Examples</p>
      <SuggestionChips />
    </div>
  );
}

export function SearchNoResultsState({
  query,
  message,
  state,
}: {
  query: string;
  message?: string | null;
  state?: SearchUrlState;
}) {
  const categoryLabel = state?.category ? categoryDisplayName(state.category) : null;
  const filterKeys = Object.keys(state?.filters ?? {});
  const tips: string[] = [];
  if (filterKeys.length > 0) {
    tips.push(`clearing ${facetLabel(filterKeys[0]!)}`);
  }
  if (state?.maxPrice != null || state?.minPrice != null) {
    tips.push("adjusting your budget");
  }
  tips.push("a broader query");

  return (
    <div className="mt-8 max-w-3xl">
      <EmptyState
        title={
          categoryLabel
            ? `No ${categoryLabel.toLowerCase()} match those filters`
            : "No matching products"
        }
        description={message ?? `Nothing matched “${query}”. Try ${tips.slice(0, 2).join(" or ")}.`}
      />
      {state && (filterKeys.length > 0 || state.minPrice != null || state.maxPrice != null) ? (
        <p className="mt-4">
          <Link
            to={buildSearchHref(state, {
              filters: {},
              minPrice: null,
              maxPrice: null,
              resetOffset: true,
            })}
            className="text-sm font-semibold text-brand-700 hover:text-brand-800"
          >
            Clear filters and retry
          </Link>
        </p>
      ) : null}
      <SuggestionChips />
    </div>
  );
}
