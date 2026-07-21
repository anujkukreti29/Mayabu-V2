import { searchResponseSchema, type SearchResponse } from "~/lib/api/schemas";
import { apiRequest } from "~/lib/api/client";

export interface SearchParams {
  q: string;
  limit?: number;
  offset?: number;
  cursor?: string | null;
}

export function searchProducts(
  params: SearchParams,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const query = new URLSearchParams({ q: params.q, limit: String(params.limit ?? 20) });
  if (params.cursor) query.set("cursor", params.cursor);
  else if (params.offset) query.set("offset", String(params.offset));
  return apiRequest(`/api/search?${query.toString()}`, searchResponseSchema, { signal });
}
