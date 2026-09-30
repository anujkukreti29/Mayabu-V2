import { z } from "zod";
import { apiRequest } from "~/lib/api/client";

export const authUserSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  display_name: z.string().nullable().optional(),
  email_verified: z.boolean(),
  created_at: z.string().nullable().optional(),
});

export type AuthUser = z.infer<typeof authUserSchema>;

const meSchema = z.object({
  user: authUserSchema.nullable(),
  wishlist_count: z.number().int().nonnegative().default(0),
});

const csrfSchema = z.object({
  csrf_token: z.string().min(1),
});

let csrfTokenMemory: string | null = null;

export function getCachedCsrfToken(): string | null {
  if (csrfTokenMemory) return csrfTokenMemory;
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)mayabu_csrf=([^;]+)/);
  if (!match?.[1]) return null;
  return decodeURIComponent(match[1]);
}

export async function ensureCsrfToken(signal?: AbortSignal): Promise<string> {
  const cached = getCachedCsrfToken();
  if (cached) {
    csrfTokenMemory = cached;
    return cached;
  }
  const payload = await apiRequest("/api/auth/csrf", csrfSchema, {
    method: "GET",
    credentials: "include",
    signal,
  });
  csrfTokenMemory = payload.csrf_token;
  return payload.csrf_token;
}

async function authMutation<T>(
  path: string,
  schema: z.ZodType<T>,
  body?: unknown,
  method: "POST" | "PATCH" | "DELETE" = "POST",
): Promise<T> {
  const csrf = await ensureCsrfToken();
  return apiRequest(path, schema, {
    method,
    credentials: "include",
    headers: { "X-CSRF-Token": csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export async function fetchAuthMe(signal?: AbortSignal) {
  return apiRequest("/api/auth/me", meSchema, {
    method: "GET",
    credentials: "include",
    signal,
  });
}

export async function registerAccount(input: {
  email: string;
  password: string;
  display_name?: string;
}) {
  return authMutation(
    "/api/auth/register",
    z.object({
      user: authUserSchema,
      verification_email_queued: z.boolean().optional(),
      message: z.string().optional(),
    }),
    input,
  );
}

export async function loginAccount(input: { email: string; password: string }) {
  return authMutation("/api/auth/login", z.object({ user: authUserSchema }), input);
}

export async function logoutAccount() {
  return authMutation("/api/auth/logout", z.object({ status: z.string() }));
}

export async function logoutAllSessions() {
  return authMutation(
    "/api/auth/logout-all",
    z.object({ status: z.string(), revoked: z.number().optional() }),
  );
}

export async function verifyEmailToken(token: string) {
  return authMutation("/api/auth/verify-email", z.object({ status: z.string() }), { token });
}

export async function resendVerification() {
  return authMutation(
    "/api/auth/resend-verification",
    z.object({
      status: z.string(),
      retry_after_seconds: z.number().nullable().optional(),
    }),
  );
}

export async function forgotPassword(email: string) {
  return authMutation("/api/auth/forgot-password", z.object({ message: z.string() }), { email });
}

export async function resetPassword(token: string, password: string) {
  return authMutation(
    "/api/auth/reset-password",
    z.object({ status: z.string(), message: z.string().optional() }),
    { token, password },
  );
}

export async function updateDisplayName(display_name: string | null) {
  return authMutation(
    "/api/auth/me",
    z.object({ user: authUserSchema }),
    { display_name },
    "PATCH",
  );
}

const sessionSchema = z.object({
  id: z.string(),
  current: z.boolean(),
  created_at: z.string().nullable().optional(),
  last_seen_at: z.string().nullable().optional(),
  device_label: z.string(),
});

export async function fetchAuthSessions(signal?: AbortSignal) {
  return apiRequest("/api/auth/sessions", z.object({ sessions: z.array(sessionSchema) }), {
    method: "GET",
    credentials: "include",
    signal,
  });
}

export async function revokeAuthSession(sessionId: string) {
  return authMutation(
    "/api/auth/sessions/revoke",
    z.object({ status: z.string(), current_revoked: z.boolean().optional() }),
    { session_id: sessionId },
  );
}

export async function logoutOtherSessions() {
  return authMutation(
    "/api/auth/logout-others",
    z.object({ status: z.string(), revoked: z.number().optional() }),
  );
}

const wishlistListSchema = z.object({
  products: z.array(z.record(z.string(), z.unknown())),
  count: z.number().int().nonnegative(),
  recent_watch_activity: z.array(z.record(z.string(), z.unknown())).optional().default([]),
  watch_delivery: z.string().optional(),
});

export async function fetchWishlist(signal?: AbortSignal) {
  return apiRequest("/api/wishlist", wishlistListSchema, {
    method: "GET",
    credentials: "include",
    signal,
  });
}

export async function fetchWishlistStatus(ids: string[], signal?: AbortSignal) {
  if (ids.length === 0) return { status: {} as Record<string, boolean>, count: 0 };
  const params = new URLSearchParams({ ids: ids.join(",") });
  return apiRequest(
    `/api/wishlist/status?${params.toString()}`,
    z.object({
      status: z.record(z.string(), z.boolean()),
      count: z.number().int().nonnegative(),
    }),
    { method: "GET", credentials: "include", signal },
  );
}

export async function addWishlistItem(productId: string) {
  return authMutation(
    `/api/wishlist/${productId}`,
    z.object({ status: z.string(), count: z.number().int().nonnegative() }),
  );
}

export async function removeWishlistItem(productId: string) {
  const csrf = await ensureCsrfToken();
  return apiRequest(
    `/api/wishlist/${productId}`,
    z.object({ status: z.string(), count: z.number().int().nonnegative() }),
    {
      method: "DELETE",
      credentials: "include",
      headers: { "X-CSRF-Token": csrf },
    },
  );
}

const wishlistWatchSchema = z.object({
  status: z.string(),
  product_id: z.string(),
  target_price: z.number().finite().nullable().optional(),
  notify_on_drop: z.boolean().optional(),
  watch_delivery: z.string().optional(),
  message: z.string().optional(),
  count: z.number().int().nonnegative().optional(),
});

export async function updateWishlistWatch(
  productId: string,
  body: { target_price?: number | null; notify_on_drop?: boolean },
) {
  return authMutation(
    `/api/wishlist/${productId}`,
    wishlistWatchSchema,
    {
      target_price: body.target_price ?? null,
      notify_on_drop: Boolean(body.notify_on_drop),
    },
    "PATCH",
  );
}
