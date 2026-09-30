/** Shared product-card intelligence signal — max one primary signal. */

import type { Product } from "~/lib/api/schemas";
import { formatPrice, validPrice } from "~/lib/formatting/price";
import { freshnessFrom } from "~/lib/formatting/freshness";

export interface CardIntelligence {
  label: string;
  kind: "drop" | "low" | "stores" | "freshness";
}

/**
 * Deterministic priority:
 * 1. meaningful recent drop (when fields exist)
 * 2. near tracked low (when fields exist)
 * 3. store coverage
 * 4. freshness
 */
export function productCardIntelligence(product: Product): CardIntelligence | null {
  // Prefer unique retailer count (platform_count) over raw listing offer_count.
  const offerCount = product.platform_count ?? product.offer_count ?? 0;
  const extras = product as Product & {
    price_drop_amount?: number | null;
    near_tracked_low?: boolean | null;
    near_90d_low?: boolean | null;
  };

  if (validPrice(extras.price_drop_amount) && Number(extras.price_drop_amount) >= 100) {
    return {
      kind: "drop",
      label: `Dropped ${formatPrice(Math.abs(Number(extras.price_drop_amount)))}`,
    };
  }
  if (extras.near_90d_low || extras.near_tracked_low) {
    return { kind: "low", label: "Near tracked low" };
  }
  if (offerCount >= 3) {
    return { kind: "stores", label: `${offerCount} stores compared` };
  }
  if (product.last_seen_at) {
    const fresh = freshnessFrom(product.last_seen_at);
    if (fresh.tone !== "warning" && fresh.label && !/unknown/i.test(fresh.label)) {
      return { kind: "freshness", label: fresh.label };
    }
  }
  if (offerCount === 2) {
    return { kind: "stores", label: "2 stores compared" };
  }
  return null;
}
