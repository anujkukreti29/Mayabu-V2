import { Form, Link } from "react-router";
import { facetLabel, formatFacetValue } from "~/lib/search/facets";
import {
  buildSearchHref,
  serializeFiltersParam,
  toggleFilterValue,
  type SearchUrlState,
} from "~/lib/search/url";
import { cn } from "~/components/ui/cn";

type FacetMap = Record<string, Array<{ value: string; count: number }>>;

function isSelected(filters: Record<string, unknown>, key: string, value: string): boolean {
  const current = filters[key];
  if (Array.isArray(current)) return current.some((item) => String(item) === value);
  if (typeof current === "string" || typeof current === "number" || typeof current === "boolean") {
    return String(current) === value;
  }
  return false;
}

function FacetGroup({
  facetKey,
  values,
  state,
}: {
  facetKey: string;
  values: Array<{ value: string; count: number }>;
  state: SearchUrlState;
}) {
  if (!values.length) return null;
  const filters = state.filters ?? {};

  return (
    <fieldset className="border-b border-slate-100 py-4 last:border-b-0">
      <legend className="text-[13px] font-semibold tracking-wide text-slate-800">
        {facetLabel(facetKey)}
      </legend>
      <ul className="mt-2.5 space-y-1">
        {values.map((item) => {
          const checked = isSelected(filters, facetKey, item.value);
          const href = buildSearchHref(state, {
            filters: toggleFilterValue(filters, facetKey, item.value),
            resetOffset: true,
          });
          return (
            <li key={`${facetKey}-${item.value}`}>
              <Link
                to={href}
                className={cn(
                  "flex min-h-9 items-center justify-between gap-2 rounded-md px-1.5 text-sm hover:bg-surface-muted",
                  checked && "bg-accent-soft",
                )}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "grid h-4 w-4 shrink-0 place-items-center rounded border",
                      checked
                        ? "border-brand-600 bg-brand-600 text-white"
                        : "border-slate-300 bg-white",
                    )}
                  >
                    {checked ? "✓" : null}
                  </span>
                  <span className="truncate text-slate-700">
                    {formatFacetValue(facetKey, item.value)}
                  </span>
                </span>
                <span className="shrink-0 text-[11px] tabular-nums text-slate-400">
                  {item.count}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </fieldset>
  );
}

export function SearchPriceFilter({
  state,
  formId = "search-price-filter",
}: {
  state: SearchUrlState;
  formId?: string;
}) {
  return (
    <Form
      id={formId}
      method="get"
      action="/search"
      className="border-b border-slate-100 py-4 last:border-b-0"
    >
      <input type="hidden" name="q" value={state.q} />
      {state.category ? <input type="hidden" name="category" value={state.category} /> : null}
      {state.sort && state.sort !== "relevance" ? (
        <input type="hidden" name="sort" value={String(state.sort)} />
      ) : null}
      {serializeFiltersParam(state.filters) ? (
        <input type="hidden" name="filters" value={serializeFiltersParam(state.filters) ?? ""} />
      ) : null}
      <p className="text-[13px] font-semibold tracking-wide text-slate-800">Price</p>
      <div className="mt-2.5 grid grid-cols-2 gap-2">
        <label className="block text-xs text-slate-500">
          ₹ Minimum
          <input
            type="number"
            name="min_price"
            min={0}
            max={10_000_000}
            step={100}
            defaultValue={state.minPrice ?? ""}
            inputMode="numeric"
            className="mt-1 min-h-10 w-full rounded-lg border border-line bg-white px-2.5 text-sm text-ink focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
        </label>
        <label className="block text-xs text-slate-500">
          ₹ Maximum
          <input
            type="number"
            name="max_price"
            min={0}
            max={10_000_000}
            step={100}
            defaultValue={state.maxPrice ?? ""}
            inputMode="numeric"
            className="mt-1 min-h-10 w-full rounded-lg border border-line bg-white px-2.5 text-sm text-ink focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
        </label>
      </div>
      <button
        type="submit"
        className="mt-3 inline-flex min-h-9 items-center rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:border-brand-300 hover:bg-brand-50"
      >
        Apply price
      </button>
    </Form>
  );
}

export function SearchFiltersPanel({
  state,
  facets,
  className,
  showHeading = true,
}: {
  state: SearchUrlState;
  facets: FacetMap;
  className?: string;
  showHeading?: boolean;
}) {
  const entries = Object.entries(facets).filter(([, values]) => values.length > 0);

  return (
    <div className={cn(className)}>
      {showHeading ? (
        <div className="flex items-baseline justify-between gap-2 border-b border-slate-100 pb-3">
          <h2 className="text-sm font-semibold text-slate-900">Filters</h2>
          <Link
            to={buildSearchHref(state, {
              filters: {},
              minPrice: null,
              maxPrice: null,
              resetOffset: true,
            })}
            className="text-xs font-medium text-brand-700 hover:text-brand-800"
          >
            Clear
          </Link>
        </div>
      ) : null}
      <SearchPriceFilter state={state} />
      {entries.length === 0 ? (
        <p className="py-4 text-sm text-slate-500">No additional filters for this result set.</p>
      ) : (
        entries.map(([key, values]) => (
          <FacetGroup key={key} facetKey={key} values={values} state={state} />
        ))
      )}
    </div>
  );
}
