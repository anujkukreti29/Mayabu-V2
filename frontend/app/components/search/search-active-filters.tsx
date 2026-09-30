import { X } from "lucide-react";
import { Link } from "react-router";
import { facetLabel, formatFacetValue } from "~/lib/search/facets";
import { categoryDisplayName } from "~/lib/search/categories";
import { buildSearchHref, removeFilterKey, type SearchUrlState } from "~/lib/search/url";

function chipClass() {
  return "inline-flex max-w-full items-center gap-1 rounded-full border border-line bg-white py-1 pl-2.5 pr-1 text-xs text-ink-soft";
}

export function SearchActiveFilters({ state }: { state: SearchUrlState }) {
  const chips: Array<{ key: string; href: string; label: string; removeLabel: string }> = [];

  if (state.category) {
    chips.push({
      key: `category:${state.category}`,
      href: buildSearchHref(state, { category: null, resetOffset: true }),
      label: categoryDisplayName(state.category),
      removeLabel: `Remove category ${categoryDisplayName(state.category)}`,
    });
  }
  if (state.minPrice != null) {
    chips.push({
      key: "min_price",
      href: buildSearchHref(state, { minPrice: null, resetOffset: true }),
      label: `Min ₹${state.minPrice.toLocaleString("en-IN")}`,
      removeLabel: "Remove minimum price",
    });
  }
  if (state.maxPrice != null) {
    chips.push({
      key: "max_price",
      href: buildSearchHref(state, { maxPrice: null, resetOffset: true }),
      label: `Max ₹${state.maxPrice.toLocaleString("en-IN")}`,
      removeLabel: "Remove maximum price",
    });
  }

  for (const [key, raw] of Object.entries(state.filters ?? {})) {
    const values = Array.isArray(raw) ? raw : [raw];
    for (const value of values) {
      chips.push({
        key: `${key}:${String(value)}`,
        href: buildSearchHref(state, {
          filters: removeFilterKey(state.filters ?? {}, key, value as string | number | boolean),
          resetOffset: true,
        }),
        label: `${facetLabel(key)}: ${formatFacetValue(key, value)}`,
        removeLabel: `Remove filter ${facetLabel(key)} ${formatFacetValue(key, value)}`,
      });
    }
  }

  if (chips.length === 0) return null;

  const clearHref = buildSearchHref(state, {
    category: null,
    filters: {},
    minPrice: null,
    maxPrice: null,
    sort: "relevance",
    resetOffset: true,
  });

  return (
    <div className="flex flex-wrap items-center gap-2" aria-label="Active filters">
      {chips.map((chip) => (
        <span key={chip.key} className={chipClass()}>
          <span className="truncate">{chip.label}</span>
          <Link
            to={chip.href}
            className="grid h-6 w-6 place-items-center rounded-full text-ink-muted hover:bg-surface-muted hover:text-ink"
            aria-label={chip.removeLabel}
          >
            <X aria-hidden="true" className="h-3.5 w-3.5" />
          </Link>
        </span>
      ))}
      <Link to={clearHref} className="text-xs font-medium text-accent hover:text-accent-strong">
        Clear all
      </Link>
    </div>
  );
}
