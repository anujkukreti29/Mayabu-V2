import { apiRequest } from "~/lib/api/client";
import { categoryLandingSchema, type CategoryLandingPayload } from "~/lib/api/schemas";

export function getCategoryLanding(
  category: string,
  signal?: AbortSignal,
  opts?: { productLimit?: number; sectionLimit?: number },
): Promise<CategoryLandingPayload> {
  const params = new URLSearchParams();
  if (opts?.productLimit) params.set("product_limit", String(opts.productLimit));
  if (opts?.sectionLimit) params.set("section_limit", String(opts.sectionLimit));
  const qs = params.toString();
  return apiRequest(
    `/api/categories/${encodeURIComponent(category)}/landing${qs ? `?${qs}` : ""}`,
    categoryLandingSchema,
    { signal },
  );
}
