import { apiRequest } from "~/lib/api/client";
import { z } from "zod";

const activityResponseSchema = z
  .object({
    accepted: z.boolean(),
    deduped: z.boolean().optional(),
    reason: z.string().optional(),
  })
  .passthrough();

export type ActivityEventType = "product_view" | "search_click" | "retailer_click";

/** Client-only engagement ping. Never call from SSR loaders. */
export function recordProductActivity(
  productId: string,
  eventType: ActivityEventType,
): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (!productId) return Promise.resolve();
  return apiRequest("/api/activity", activityResponseSchema, {
    method: "POST",
    body: JSON.stringify({ product_id: productId, event_type: eventType }),
    timeoutMs: 4_000,
  }).then(
    () => undefined,
    () => undefined,
  );
}
