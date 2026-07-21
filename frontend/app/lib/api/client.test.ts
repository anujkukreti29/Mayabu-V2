import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { ApiError } from "~/lib/api/errors";
import { apiRequest } from "~/lib/api/client";

const schema = z.object({ ok: z.boolean() });

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("apiRequest", () => {
  it("validates successful JSON responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(apiRequest("/api/health", schema)).resolves.toEqual({ ok: true });
  });

  it("normalizes FastAPI validation details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: [{ msg: "Invalid query" }] }), {
          status: 422,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(apiRequest("/api/search", schema)).rejects.toMatchObject({
      status: 422,
      message: "Invalid query",
    });
  });

  it("reports internal timeouts without converting caller cancellation", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener(
              "abort",
              () =>
                reject(
                  init.signal?.reason instanceof Error
                    ? init.signal.reason
                    : new DOMException("Request aborted", "AbortError"),
                ),
              { once: true },
            );
          }),
      ),
    );

    const timeoutResult = apiRequest("/api/slow", schema, { timeoutMs: 50 }).catch(
      (error: unknown) => error,
    );
    await vi.advanceTimersByTimeAsync(60);
    expect(await timeoutResult).toBeInstanceOf(ApiError);

    const controller = new AbortController();
    const cancelledResult = apiRequest("/api/cancelled", schema, {
      signal: controller.signal,
    }).catch((error: unknown) => error);
    controller.abort(new DOMException("cancelled", "AbortError"));
    await expect(cancelledResult).resolves.toMatchObject({ name: "AbortError" });
  });

  it("rejects absolute or protocol-relative API paths", async () => {
    await expect(apiRequest("https://example.com", schema)).rejects.toThrow(
      "API paths must be relative",
    );
    await expect(apiRequest("//example.com", schema)).rejects.toThrow("API paths must be relative");
  });
});
