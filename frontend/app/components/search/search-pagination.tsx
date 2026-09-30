import { Link } from "react-router";
import { buildSearchHref, type SearchUrlState } from "~/lib/search/url";

export function nextSearchOffset(currentOffset: number, limit: number): number {
  return Math.max(0, currentOffset + limit);
}

export function previousSearchOffset(currentOffset: number, limit: number): number {
  return Math.max(0, currentOffset - limit);
}

export function searchPaginationHref(state: SearchUrlState, offset: number): string {
  return buildSearchHref(state, { offset, cursor: null });
}

export function SearchPagination({
  state,
  offset,
  limit,
  hasMore,
  hasResults,
}: {
  state: SearchUrlState;
  offset: number;
  limit: number;
  hasMore: boolean;
  hasResults: boolean;
}) {
  const showPrevious = offset > 0;
  const previousHref = searchPaginationHref(state, previousSearchOffset(offset, limit));
  const nextHref = searchPaginationHref(state, nextSearchOffset(offset, limit));

  if (!showPrevious && !hasMore && !hasResults) return null;

  return (
    <nav
      aria-label="Search pagination"
      className="mt-10 flex flex-col gap-3 border-t border-slate-100 pt-6 sm:flex-row sm:items-center sm:justify-between"
    >
      {showPrevious ? (
        <Link
          to={previousHref}
          className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:border-brand-300 hover:bg-brand-50"
        >
          Previous page
        </Link>
      ) : (
        <span className="hidden sm:block" />
      )}
      {hasMore ? (
        <Link
          to={nextHref}
          className="inline-flex min-h-11 items-center justify-center rounded-lg bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700"
        >
          Next page
        </Link>
      ) : hasResults ? (
        <p className="text-center text-sm text-slate-500 sm:text-right">End of these results</p>
      ) : null}
    </nav>
  );
}
