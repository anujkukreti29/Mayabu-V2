import { categoryDisplayName } from "~/lib/search/categories";
import type { SearchResponse } from "~/lib/api/schemas";
import type { SearchUrlState } from "~/lib/search/url";

export function SearchResultsHeader({
  query,
  result,
  state,
}: {
  query: string;
  result: SearchResponse;
  state: SearchUrlState;
}) {
  const explicit = state.category;
  const detected = result.detected_category;
  const category = explicit || detected;
  const mixed =
    !explicit &&
    result.search_mode === "cross_category" &&
    Object.keys(result.category_counts ?? {}).length > 1;
  const pageCount = result.result_count;

  return (
    <header className="min-w-0">
      <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">
        Results for “{query}”
      </h1>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-muted">
        {mixed ? (
          <span>Products across categories</span>
        ) : category ? (
          <span>{categoryDisplayName(category)}</span>
        ) : null}
        {result.detected_brand &&
        !query.toLowerCase().includes(result.detected_brand.toLowerCase()) ? (
          <span className="text-ink-faint">·</span>
        ) : null}
        {result.detected_brand &&
        !query.toLowerCase().includes(result.detected_brand.toLowerCase()) ? (
          <span>{result.detected_brand}</span>
        ) : null}
        {pageCount > 0 ? (
          <>
            {(mixed || category) && <span className="text-ink-faint">·</span>}
            <span aria-live="polite">
              {pageCount} product{pageCount === 1 ? "" : "s"}
              {result.has_more ? "+" : ""}
            </span>
          </>
        ) : null}
      </div>
    </header>
  );
}
