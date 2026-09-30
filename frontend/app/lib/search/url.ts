/** Robust search URL construction — single source for q/category/filters/sort/price/offset. */

import { routes } from "~/lib/navigation/routes";

export type SearchSort = "relevance" | "price_asc" | "price_desc" | "recently_checked";

export interface SearchUrlState {
  q: string;
  category?: string | null;
  sort?: SearchSort | null;
  minPrice?: number | null;
  maxPrice?: number | null;
  filters?: Record<string, unknown> | null;
  offset?: number | null;
  cursor?: string | null;
}

export function parseFiltersParam(raw: string | null | undefined): Record<string, unknown> {
  if (!raw) return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return parsed as Record<string, unknown>;
  } catch {
    return {};
  }
}

export function serializeFiltersParam(
  filters: Record<string, unknown> | null | undefined,
): string | null {
  if (!filters) return null;
  const cleaned: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (
      value === null ||
      value === undefined ||
      value === "" ||
      (Array.isArray(value) && value.length === 0)
    ) {
      continue;
    }
    cleaned[key] = value;
  }
  if (Object.keys(cleaned).length === 0) return null;
  return JSON.stringify(cleaned);
}

export function parseSearchUrl(url: URL): SearchUrlState {
  const q = (url.searchParams.get("q") ?? "").trim().slice(0, 160);
  const category = url.searchParams.get("category");
  const sortRaw = url.searchParams.get("sort");
  const sort: SearchSort =
    sortRaw === "price_asc" || sortRaw === "price_desc" || sortRaw === "recently_checked"
      ? sortRaw
      : "relevance";
  const minRaw = url.searchParams.get("min_price");
  const maxRaw = url.searchParams.get("max_price");
  const minPrice = minRaw !== null && minRaw !== "" ? Number(minRaw) : null;
  const maxPrice = maxRaw !== null && maxRaw !== "" ? Number(maxRaw) : null;
  const offset = Math.max(0, Math.min(5000, Number(url.searchParams.get("offset") ?? 0) || 0));
  const cursor = url.searchParams.get("cursor");
  return {
    q,
    category: category || null,
    sort: sort || "relevance",
    minPrice: Number.isFinite(minPrice) ? minPrice : null,
    maxPrice: Number.isFinite(maxPrice) ? maxPrice : null,
    filters: parseFiltersParam(url.searchParams.get("filters")),
    offset,
    cursor,
  };
}

export function buildSearchHref(
  state: SearchUrlState,
  patch: Partial<SearchUrlState> & { resetOffset?: boolean } = {},
): string {
  const next: SearchUrlState = {
    ...state,
    ...patch,
    filters: patch.filters !== undefined ? patch.filters : state.filters,
  };
  if (
    patch.resetOffset ||
    patch.category !== undefined ||
    patch.filters !== undefined ||
    patch.sort !== undefined ||
    patch.minPrice !== undefined ||
    patch.maxPrice !== undefined
  ) {
    if (patch.offset === undefined) next.offset = 0;
    next.cursor = null;
  }

  const params = new URLSearchParams();
  const q = (next.q ?? "").trim().slice(0, 160);
  if (q) params.set("q", q);
  if (next.category) params.set("category", next.category);
  if (next.sort && next.sort !== "relevance") params.set("sort", String(next.sort));
  if (next.minPrice != null && Number.isFinite(next.minPrice)) {
    params.set("min_price", String(Math.max(0, Math.floor(next.minPrice))));
  }
  if (next.maxPrice != null && Number.isFinite(next.maxPrice)) {
    params.set("max_price", String(Math.max(0, Math.floor(next.maxPrice))));
  }
  const filtersJson = serializeFiltersParam(next.filters ?? undefined);
  if (filtersJson) params.set("filters", filtersJson);
  if (next.cursor) params.set("cursor", next.cursor);
  else if (next.offset && next.offset > 0) params.set("offset", String(next.offset));

  const qs = params.toString();
  return qs ? `${routes.search}?${qs}` : routes.search;
}

export function toggleFilterValue(
  filters: Record<string, unknown>,
  key: string,
  value: string | number | boolean,
): Record<string, unknown> {
  const next = { ...filters };
  const current = next[key];
  const asList: Array<string | number | boolean> = Array.isArray(current)
    ? current.filter(
        (item): item is string | number | boolean =>
          typeof item === "string" || typeof item === "number" || typeof item === "boolean",
      )
    : current === undefined || current === null || current === ""
      ? []
      : typeof current === "string" || typeof current === "number" || typeof current === "boolean"
        ? [current]
        : [];
  const valueKey = String(value);
  const idx = asList.findIndex((item) => String(item) === valueKey);
  if (idx >= 0) asList.splice(idx, 1);
  else asList.push(value);

  if (asList.length === 0) {
    delete next[key];
  } else if (asList.length === 1) {
    next[key] = asList[0];
  } else {
    next[key] = asList;
  }
  return next;
}

export function removeFilterKey(
  filters: Record<string, unknown>,
  key: string,
  value?: string | number | boolean,
): Record<string, unknown> {
  if (value === undefined) {
    const next = { ...filters };
    delete next[key];
    return next;
  }
  return toggleFilterValue(filters, key, value);
}

export function hasActiveSearchConstraints(state: SearchUrlState): boolean {
  return Boolean(
    state.category ||
      state.minPrice != null ||
      state.maxPrice != null ||
      (state.filters && Object.keys(state.filters).length > 0) ||
      (state.sort && state.sort !== "relevance"),
  );
}
