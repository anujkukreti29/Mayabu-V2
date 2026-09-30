import { apiRequest } from "~/lib/api/client";
import { compareResponseSchema, type CompareResponse } from "~/lib/api/schemas";

export function getCompareProducts(
  ids: readonly string[],
  signal?: AbortSignal,
): Promise<CompareResponse> {
  const cleaned = [...new Set(ids.map((id) => id.trim()).filter(Boolean))].slice(0, 4);
  if (cleaned.length === 0) {
    return Promise.resolve({
      products: [],
      category: null,
      requested_ids: [],
      missing_ids: [],
      skipped: [],
      warnings: [],
    });
  }
  const query = encodeURIComponent(cleaned.join(","));
  return apiRequest(`/api/compare?ids=${query}`, compareResponseSchema, { signal });
}

export function parseCompareIdsFromSearch(search: string): string[] {
  const params = new URLSearchParams(search);
  const raw = params.get("ids") || params.get("products") || "";
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of raw.split(",")) {
    const id = part.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(id);
    if (out.length >= 4) break;
  }
  return out;
}

export function comparePath(ids: readonly string[]): string {
  const cleaned = [...new Set(ids.map((id) => id.trim()).filter(Boolean))].slice(0, 4);
  if (cleaned.length === 0) return "/compare";
  return `/compare?ids=${encodeURIComponent(cleaned.join(","))}`;
}
