import { ApiError } from "~/lib/api/errors";
import type { VerificationJob, VerificationRequest } from "~/lib/api/schemas";

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
  | "completed"
  | "out_of_stock"
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

  if (expired && !allTerminal) return "expired";
  if (taskIds.length === 0) return initialStatus ?? "idle";
  if (jobs.some((job) => job.status === "running")) return "running";
  if (jobs.some((job) => ["pending", "queued", "paused"].includes(job.status))) {
    return initialStatus === "joined" ? "joined" : "queued";
  }
  if (jobErrors.length > 0 && jobs.length < taskIds.length) return "unavailable";

  const completedJobs = jobs.filter((job) => job.status === "completed");
  if (
    completedJobs.some(
      (job) => job.result.stock_status === "out_of_stock" || job.result.status === "out_of_stock",
    )
  ) {
    return "out_of_stock";
  }

  const failedJobs = jobs.filter((job) => ["failed", "dead", "cancelled"].includes(job.status));
  if (failedJobs.length > 0) return failedJobSummary(failedJobs);
  if (jobs.length === taskIds.length && jobs.every((job) => job.status === "completed")) {
    return "completed";
  }
  return initialStatus === "joined" ? "joined" : "queued";
}
