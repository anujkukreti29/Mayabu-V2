import { apiRequest } from "~/lib/api/client";
import {
  offersResponseSchema,
  priceHistorySchema,
  productDetailSchema,
  type PriceHistory,
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
  days = 180,
  signal?: AbortSignal,
): Promise<PriceHistory> {
  return apiRequest(
    `/api/products/${encodeURIComponent(productId)}/price-history?days=${days}`,
    priceHistorySchema,
    { signal },
  );
}
