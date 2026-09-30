import { ApiError } from "~/lib/api/errors";
import type { VerificationJob, VerificationRequest } from "~/lib/api/schemas";
import { validPrice } from "~/lib/formatting/price";

export type VerificationSummary =
  | "idle"
  | "requesting"
  | "fresh"
  | "cooldown"
  | "busy"
  | "rate_limited"
  | "no_offers"
  | "joined"
  | "queued"
  | "running"
  | "completed_unchanged"
  | "completed_changed"
  | "partial"
  | "out_of_stock"
  | "stale_fallback"
  | "blocked"
  | "unavailable"
  | "failed"
  | "expired";

const BLOCKED_TERMS = ["blocked", "captcha", "access denied", "robot", "unusual traffic", "403"];
const UNAVAILABLE_TERMS = [
  "temporarily unavailable",
  "timeout",
  "timed out",
  "network",
  "not found",
  "unavailable",
  "connection",
];

function jobText(job: VerificationJob): string {
  const errors = Array.isArray(job.result.errors) ? job.result.errors.join(" ") : "";
  return [job.last_error, job.error_category, errors, job.result.page_status]
    .filter((value): value is string => typeof value === "string")
    .join(" ")
    .toLowerCase();
}

function failedJobSummary(jobs: VerificationJob[]): VerificationSummary {
  const text = jobs.map(jobText).join(" ");
  if (BLOCKED_TERMS.some((term) => text.includes(term))) return "blocked";
  if (UNAVAILABLE_TERMS.some((term) => text.includes(term))) return "unavailable";
  return "failed";
}

function resultNumber(result: Record<string, unknown>, ...keys: string[]): number | null {
  for (const key of keys) {
    const value = result[key];
    if (validPrice(value)) return Number(value);
  }
  return null;
}

export function jobObservedPrice(job: VerificationJob): number | null {
  return resultNumber(job.result, "price", "new_price", "verified_price");
}

export function jobPreviousPrice(job: VerificationJob): number | null {
  return resultNumber(job.result, "old_price", "previous_price");
}

export function isStaleFallbackResult(job: VerificationJob): boolean {
  const result = job.result;
  if (result.stale === true || result.stale_retained === true || result.stale_fallback === true) {
    return true;
  }
  if (result.source === "stale_fallback" || result.source === "stale") return true;
  const pageStatus =
    typeof result.page_status === "string"
      ? result.page_status
      : typeof result.status === "string"
        ? result.status
        : "";
  const status = pageStatus.toLowerCase();
  return status.includes("stale");
}

function isSuccessfulCheck(job: VerificationJob): boolean {
  if (job.status !== "completed") return false;
  const stock = job.result.stock_status;
  if (stock === "out_of_stock") return true;
  if (jobObservedPrice(job) != null) return true;
  // Worker completed + applied a valid observation (stale-good path still counts).
  return job.result.valid !== false;
}

export interface VerificationCounts {
  successful: number;
  failed: number;
  total: number;
}

export function countVerificationChecks(jobs: VerificationJob[]): VerificationCounts {
  const successful = jobs.filter(isSuccessfulCheck).length;
  const failed = jobs.filter((job) =>
    ["failed", "dead", "cancelled"].includes(job.status),
  ).length;
  return { successful, failed, total: jobs.length };
}

export interface VerificationPriceDelta {
  oldPrice: number | null;
  newPrice: number | null;
  changed: boolean;
}

export function verificationPriceDelta(jobs: VerificationJob[]): VerificationPriceDelta {
  // Never treat OOS / stale-fallback completions as a celebratory price change.
  const completed = jobs.filter(
    (job) =>
      job.status === "completed" &&
      job.result.stock_status !== "out_of_stock" &&
      job.result.status !== "out_of_stock" &&
      !isStaleFallbackResult(job),
  );
  for (const job of completed) {
    const oldPrice = jobPreviousPrice(job);
    const newPrice = jobObservedPrice(job);
    if (validPrice(oldPrice) && validPrice(newPrice) && oldPrice !== newPrice) {
      return { oldPrice, newPrice, changed: true };
    }
  }
  const first = completed[0];
  const price = first ? jobObservedPrice(first) : null;
  const previous = first ? jobPreviousPrice(first) : null;
  return {
    oldPrice: previous,
    newPrice: price ?? previous,
    changed: false,
  };
}

export interface VerificationStateInput {
  mutationPending: boolean;
  mutationError: unknown;
  expired: boolean;
  allTerminal: boolean;
  taskIds: string[];
  jobs: VerificationJob[];
  jobErrors: unknown[];
  initialStatus: VerificationRequest["status"] | null;
}

export function deriveVerificationSummary({
  mutationPending,
  mutationError,
  expired,
  allTerminal,
  taskIds,
  jobs,
  jobErrors,
  initialStatus,
}: VerificationStateInput): VerificationSummary {
  if (mutationPending) return "requesting";

  if (mutationError instanceof ApiError) {
    if (mutationError.status === 429 || mutationError.category === "rate-limit") {
      return "rate_limited";
    }
    if (mutationError.status === 503) return "busy";
    if (mutationError.category === "network" || mutationError.category === "timeout") {
      return "unavailable";
    }
    return "failed";
  }
  if (mutationError) return "failed";

  if (expired && !allTerminal) {
    const counts = countVerificationChecks(jobs);
    // Deadline reached: keep successful store results as partial, never spin forever.
    if (counts.successful > 0) return "partial";
    if (counts.failed > 0 && counts.failed === counts.total) return failedJobSummary(jobs);
    return "expired";
  }
  if (taskIds.length === 0) return initialStatus ?? "idle";
  if (jobs.some((job) => job.status === "running")) return "running";
  if (jobs.some((job) => ["pending", "queued", "paused"].includes(job.status))) {
    return initialStatus === "joined" ? "joined" : "queued";
  }
  if (jobErrors.length > 0 && jobs.length < taskIds.length) return "unavailable";

  if (!allTerminal && jobs.length < taskIds.length) {
    return initialStatus === "joined" ? "joined" : "queued";
  }

  const counts = countVerificationChecks(jobs);
  const outOfStock = jobs.some(
    (job) =>
      job.status === "completed" &&
      (job.result.stock_status === "out_of_stock" || job.result.status === "out_of_stock"),
  );
  const staleFallback =
    counts.successful > 0 &&
    jobs.some((job) => job.status === "completed" && isStaleFallbackResult(job));

  if (counts.successful > 0 && counts.failed > 0) return "partial";
  if (counts.successful > 0 && outOfStock && counts.failed === 0 && counts.successful === 1) {
    return "out_of_stock";
  }
  if (staleFallback && counts.failed === 0) return "stale_fallback";
  if (counts.successful > 0) {
    return verificationPriceDelta(jobs).changed ? "completed_changed" : "completed_unchanged";
  }
  if (counts.failed > 0) {
    return failedJobSummary(
      jobs.filter((job) => ["failed", "dead", "cancelled"].includes(job.status)),
    );
  }
  return initialStatus === "joined" ? "joined" : "queued";
}
