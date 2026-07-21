import type { z } from "zod";
import { ApiError } from "~/lib/api/errors";
import { env } from "~/lib/config/env";

const CLIENT_ID_KEY = "mayabu-anonymous-client-id";
const DEFAULT_TIMEOUT_MS = 12_000;

function getAnonymousClientId(): string | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    const existing = window.localStorage.getItem(CLIENT_ID_KEY);
    if (existing) return existing;
    const generated = crypto.randomUUID();
    window.localStorage.setItem(CLIENT_ID_KEY, generated);
    return generated;
  } catch {
    return undefined;
  }
}

interface RequestSignal {
  signal: AbortSignal;
  timedOut: () => boolean;
  cleanup: () => void;
}

function createRequestSignal(external: AbortSignal | undefined, timeoutMs: number): RequestSignal {
  const controller = new AbortController();
  let timeoutReached = false;

  const abortFromExternal = () => controller.abort(external?.reason);
  if (external?.aborted) abortFromExternal();
  else external?.addEventListener("abort", abortFromExternal, { once: true });

  const timeoutId = setTimeout(
    () => {
      timeoutReached = true;
      controller.abort(new DOMException("Request timed out", "TimeoutError"));
    },
    Math.max(1, timeoutMs),
  );

  return {
    signal: controller.signal,
    timedOut: () => timeoutReached,
    cleanup: () => {
      clearTimeout(timeoutId);
      external?.removeEventListener("abort", abortFromExternal);
    },
  };
}

function messageFromDetail(value: unknown): string | undefined {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (Array.isArray(value)) {
    const messages = value
      .map((item) => messageFromDetail(item))
      .filter((item): item is string => Boolean(item));
    return messages.length > 0 ? messages.slice(0, 3).join("; ") : undefined;
  }
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return (
      messageFromDetail(record.message) ??
      messageFromDetail(record.msg) ??
      messageFromDetail(record.detail)
    );
  }
  return undefined;
}

async function parseError(response: Response): Promise<string> {
  const contentType = response.headers.get("Content-Type") ?? "";
  try {
    if (contentType.includes("json")) {
      const payload = (await response.json()) as Record<string, unknown>;
      const message = messageFromDetail(payload.detail) ?? messageFromDetail(payload.message);
      if (message) return message;
    } else {
      const text = (await response.text()).trim();
      if (text && response.status < 500) return text.slice(0, 300);
    }
  } catch {
    // Fall through to a stable user-safe message.
  }
  return response.status >= 500
    ? "Mayabu's product service is temporarily unavailable."
    : "Mayabu could not complete this request.";
}

function apiUrl(path: string): string {
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw new Error("API paths must be relative to the configured Mayabu backend.");
  }
  return `${env.apiBaseUrl}${path}`;
}

export interface RequestOptions extends Omit<RequestInit, "signal"> {
  signal?: AbortSignal;
  timeoutMs?: number;
}

export async function apiRequest<T>(
  path: string,
  schema: z.ZodType<T, z.ZodTypeDef, unknown>,
  options: RequestOptions = {},
): Promise<T> {
  const requestId = crypto.randomUUID();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  headers.set("X-Request-ID", requestId);
  const clientId = getAnonymousClientId();
  if (clientId) headers.set("X-Mayabu-Client-Id", clientId);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const url = apiUrl(path);
  const requestSignal = createRequestSignal(
    options.signal,
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  );
  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      signal: requestSignal.signal,
    });
  } catch (error) {
    if (options.signal?.aborted && !requestSignal.timedOut()) throw error;
    if (
      requestSignal.timedOut() ||
      (error instanceof DOMException && error.name === "TimeoutError")
    ) {
      throw new ApiError("The request timed out.", 0, requestId, undefined, "timeout");
    }
    throw new ApiError(
      "Mayabu could not reach the product service.",
      0,
      requestId,
      undefined,
      "network",
    );
  } finally {
    requestSignal.cleanup();
  }

  const responseRequestId = response.headers.get("X-Request-ID") ?? requestId;
  if (!response.ok) {
    const retryAfter = Number(response.headers.get("Retry-After"));
    const category =
      response.status === 429 ? "rate-limit" : response.status >= 500 ? "server" : "unknown";
    throw new ApiError(
      await parseError(response),
      response.status,
      responseRequestId,
      Number.isFinite(retryAfter) ? retryAfter : undefined,
      category,
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(
      "Mayabu received an unreadable API response.",
      502,
      responseRequestId,
      undefined,
      "validation",
    );
  }
  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new ApiError(
      "Mayabu received an unexpected API response.",
      502,
      responseRequestId,
      undefined,
      "validation",
    );
  }
  return parsed.data;
}
