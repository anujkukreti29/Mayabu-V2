import { apiRequest } from "~/lib/api/client";
import {
  verificationJobSchema,
  verificationRequestSchema,
  verificationStatusSchema,
  type VerificationJob,
  type VerificationRequest,
} from "~/lib/api/schemas";

export function verifyPrice(
  productId: string,
  mode: "best_offer" | "all_offers",
): Promise<VerificationRequest> {
  return apiRequest(
    `/api/products/${encodeURIComponent(productId)}/verify-price`,
    verificationRequestSchema,
    {
      method: "POST",
      body: JSON.stringify({ mode }),
      timeoutMs: 15_000,
    },
  );
}

export function getVerificationJob(taskId: string, signal?: AbortSignal): Promise<VerificationJob> {
  return apiRequest(`/api/verification-jobs/${encodeURIComponent(taskId)}`, verificationJobSchema, {
    signal,
  });
}

export function getVerificationStatus(productId: string, signal?: AbortSignal) {
  return apiRequest(
    `/api/products/${encodeURIComponent(productId)}/verification-status`,
    verificationStatusSchema,
    { signal },
  );
}
