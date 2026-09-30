import { apiRequest } from "~/lib/api/client";
import {
  searchResponseSchema,
  searchSuggestSchema,
  type SearchResponse,
  type SearchSuggestResponse,
} from "~/lib/api/schemas";
import { serializeFiltersParam, type SearchSort } from "~/lib/search/url";

export interface SearchParams {
  q: string;
  limit?: number;
  offset?: number;
  cursor?: string | null;
  category?: string | null;
  sort?: SearchSort | null;
  minPrice?: number | null;
  maxPrice?: number | null;
  filters?: Record<string, unknown> | null;
}

export function searchProducts(
  params: SearchParams,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const query = new URLSearchParams({ q: params.q, limit: String(params.limit ?? 20) });
  if (params.category) query.set("category", params.category);
  if (params.sort && params.sort !== "relevance") query.set("sort", String(params.sort));
  if (params.minPrice != null) query.set("min_price", String(params.minPrice));
  if (params.maxPrice != null) query.set("max_price", String(params.maxPrice));
  const filters = serializeFiltersParam(params.filters);
  if (filters) query.set("filters", filters);
  if (params.cursor) query.set("cursor", params.cursor);
  else if (params.offset) query.set("offset", String(params.offset));
  return apiRequest(`/api/search?${query.toString()}`, searchResponseSchema, { signal });
}

export function searchSuggest(
  q: string,
  signal?: AbortSignal,
  limit = 6,
): Promise<SearchSuggestResponse> {
  const query = new URLSearchParams({ q, limit: String(limit) });
  return apiRequest(`/api/search/suggest?${query.toString()}`, searchSuggestSchema, {
    signal,
  });
}
