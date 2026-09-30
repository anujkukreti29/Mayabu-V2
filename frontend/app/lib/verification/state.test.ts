import { describe, expect, it } from "vitest";
import { ApiError } from "~/lib/api/errors";
import type { VerificationJob } from "~/lib/api/schemas";
import {
  deriveVerificationSummary,
  verificationPriceDelta,
  type VerificationStateInput,
} from "./state";

function job(overrides: Partial<VerificationJob>): VerificationJob {
  return {
    task_id: "task-1",
    status: "pending",
    platform: "Amazon India",
    attempts: 0,
    request_count: 1,
    result: {},
    last_error: null,
    error_category: null,
    created_at: null,
    updated_at: null,
    started_at: null,
    completed_at: null,
    ...overrides,
  };
}

const base: VerificationStateInput = {
  mutationPending: false,
  mutationError: null,
  expired: false,
  allTerminal: false,
  taskIds: [],
  jobs: [],
  jobErrors: [],
  initialStatus: null,
};

describe("deriveVerificationSummary", () => {
  it.each([
    ["fresh", "fresh"],
    ["cooldown", "cooldown"],
    ["busy", "busy"],
    ["no_offers", "no_offers"],
  ] as const)("keeps request status %s", (status, expected) => {
    expect(deriveVerificationSummary({ ...base, initialStatus: status })).toBe(expected);
  });

  it("maps a shared pending task to joined", () => {
    expect(
      deriveVerificationSummary({
        ...base,
        initialStatus: "joined",
        taskIds: ["task-1"],
        jobs: [job({ status: "pending" })],
      }),
    ).toBe("joined");
  });

  it("maps running, unchanged, changed, and partial multi-store results", () => {
    expect(
      deriveVerificationSummary({
        ...base,
        taskIds: ["task-1"],
        jobs: [job({ status: "running" })],
      }),
    ).toBe("running");
    expect(
      deriveVerificationSummary({
        ...base,
        allTerminal: true,
        taskIds: ["task-1"],
        jobs: [job({ status: "completed", result: { price: 69999, old_price: 69999 } })],
      }),
    ).toBe("completed_unchanged");
    expect(
      deriveVerificationSummary({
        ...base,
        allTerminal: true,
        taskIds: ["task-1"],
        jobs: [job({ status: "completed", result: { price: 64999, old_price: 69999 } })],
      }),
    ).toBe("completed_changed");
    expect(
      deriveVerificationSummary({
        ...base,
        allTerminal: true,
        taskIds: ["task-1", "task-2"],
        jobs: [
          job({ task_id: "task-1", status: "completed", result: { price: 69999 } }),
          job({
            task_id: "task-2",
            status: "failed",
            last_error: "network timeout",
          }),
        ],
      }),
    ).toBe("partial");
  });

  it("maps stale fallback separately from unchanged", () => {
    expect(
      deriveVerificationSummary({
        ...base,
        allTerminal: true,
        taskIds: ["task-1"],
        jobs: [
          job({
            status: "completed",
            result: { price: 69999, old_price: 69999, stale: true },
          }),
        ],
      }),
    ).toBe("stale_fallback");
  });

  it("preserves out-of-stock as a successful result", () => {
    expect(
      deriveVerificationSummary({
        ...base,
        allTerminal: true,
        taskIds: ["task-1"],
        jobs: [job({ status: "completed", result: { stock_status: "out_of_stock" } })],
      }),
    ).toBe("out_of_stock");
  });

  it("distinguishes blocked, unavailable, and ordinary failures", () => {
    const input = { ...base, allTerminal: true, taskIds: ["task-1"] };
    expect(
      deriveVerificationSummary({
        ...input,
        jobs: [job({ status: "failed", last_error: "retailer captcha blocked" })],
      }),
    ).toBe("blocked");
    expect(
      deriveVerificationSummary({
        ...input,
        jobs: [job({ status: "failed", last_error: "network timeout" })],
      }),
    ).toBe("unavailable");
    expect(
      deriveVerificationSummary({
        ...input,
        jobs: [job({ status: "dead", last_error: "unexpected parser failure" })],
      }),
    ).toBe("failed");
  });

  it("maps admission and network errors without returning idle", () => {
    expect(
      deriveVerificationSummary({
        ...base,
        mutationError: new ApiError("limited", 429, "r1", 60, "rate-limit"),
      }),
    ).toBe("rate_limited");
    expect(
      deriveVerificationSummary({
        ...base,
        mutationError: new ApiError("offline", 0, "r2", undefined, "network"),
      }),
    ).toBe("unavailable");
    expect(
      deriveVerificationSummary({
        ...base,
        mutationError: new ApiError("busy", 503, "r3", 30, "server"),
      }),
    ).toBe("busy");
  });

  it("expires browser polling without changing the backend job", () => {
    expect(
      deriveVerificationSummary({
        ...base,
        expired: true,
        taskIds: ["task-1"],
        jobs: [job({ status: "running" })],
      }),
    ).toBe("expired");
  });

  it("treats deadline with successful stores as partial", () => {
    expect(
      deriveVerificationSummary({
        ...base,
        expired: true,
        taskIds: ["task-1", "task-2"],
        jobs: [
          job({ status: "completed", result: { price: 49990, valid: true } }),
          job({ status: "running" }),
        ],
      }),
    ).toBe("partial");
  });

  it("reports unavailable when job polling fails before status is loaded", () => {
    expect(
      deriveVerificationSummary({
        ...base,
        taskIds: ["task-1"],
        jobErrors: [new ApiError("offline", 0, "r4", undefined, "network")],
      }),
    ).toBe("unavailable");
  });
});

describe("verificationPriceDelta", () => {
  it("detects changed and unchanged outcomes", () => {
    expect(
      verificationPriceDelta([
        job({ status: "completed", result: { old_price: 50000, price: 48000 } }),
      ]),
    ).toEqual({ oldPrice: 50000, newPrice: 48000, changed: true });
    expect(
      verificationPriceDelta([
        job({ status: "completed", result: { old_price: 50000, price: 50000 } }),
      ]).changed,
    ).toBe(false);
  });
});
