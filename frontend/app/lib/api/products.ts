import { apiRequest } from "~/lib/api/client";
import {
  offersResponseSchema,
  priceHistorySchema,
  priceIntelligenceSchema,
  productDetailSchema,
  type PriceHistory,
  type PriceIntelligence,
  type ProductDetail,
} from "~/lib/api/schemas";

export function getProduct(productId: string, signal?: AbortSignal): Promise<ProductDetail> {
  return apiRequest(`/api/products/${encodeURIComponent(productId)}`, productDetailSchema, {
    signal,
  });
}

export function getOffers(productId: string, signal?: AbortSignal) {
  return apiRequest(`/api/products/${encodeURIComponent(productId)}/offers`, offersResponseSchema, {
    signal,
  });
}

export function getPriceHistory(
  productId: string,
  daysOrWindow: number | { days?: number; window?: string } = 180,
  signal?: AbortSignal,
): Promise<PriceHistory> {
  const params = new URLSearchParams();
  if (typeof daysOrWindow === "number") {
    params.set("days", String(daysOrWindow));
  } else {
    if (daysOrWindow.days) params.set("days", String(daysOrWindow.days));
    if (daysOrWindow.window) params.set("window", daysOrWindow.window);
  }
  return apiRequest(
    `/api/products/${encodeURIComponent(productId)}/price-history?${params.toString()}`,
    priceHistorySchema,
    { signal },
  );
}

export function getPriceIntelligence(
  productId: string,
  signal?: AbortSignal,
): Promise<PriceIntelligence> {
  return apiRequest(
    `/api/products/${encodeURIComponent(productId)}/price-intelligence`,
    priceIntelligenceSchema,
    { signal },
  );
}
