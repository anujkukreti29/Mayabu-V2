import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRevalidator } from "react-router";
import { getVerificationJob, verifyPrice } from "~/lib/api/verification";
import type { VerificationJob, VerificationRequest } from "~/lib/api/schemas";
import { productKeys, verificationKeys } from "~/lib/query/keys";
import { usePageVisibility } from "~/hooks/use-page-visibility";
import { deriveVerificationSummary, type VerificationSummary } from "~/lib/verification/state";

const TERMINAL = new Set<VerificationJob["status"]>(["completed", "failed", "dead", "cancelled"]);
const POLL_TIMEOUT_MS = 90_000;
const STORED_TASK_MAX_AGE_MS = 30 * 60_000;
const MAX_TASK_IDS = 4;
const MAX_TASK_ID_LENGTH = 128;
const REQUEST_STATUSES: readonly VerificationRequest["status"][] = [
  "queued",
  "joined",
  "fresh",
  "cooldown",
  "busy",
  "no_offers",
];
const ACTIVE_SUMMARIES = new Set<VerificationSummary>([
  "requesting",
  "queued",
  "joined",
  "running",
]);

interface StoredTasks {
  taskIds: string[];
  startedAt: number;
  initialStatus?: VerificationRequest["status"];
}

function storageKey(productId: string) {
  return `mayabu-verification-${productId}`;
}

function normalizeTaskIds(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  for (const item of value) {
    if (typeof item !== "string") continue;
    const taskId = item.trim();
    if (!taskId || taskId.length > MAX_TASK_ID_LENGTH || seen.has(taskId)) continue;
    seen.add(taskId);
    if (seen.size === MAX_TASK_IDS) break;
  }
  return [...seen];
}

function normalizeInitialStatus(value: unknown): VerificationRequest["status"] | undefined {
  return typeof value === "string" && (REQUEST_STATUSES as readonly string[]).includes(value)
    ? (value as VerificationRequest["status"])
    : undefined;
}

function removeStored(productId: string): void {
  try {
    window.sessionStorage.removeItem(storageKey(productId));
  } catch {
    // Verification continues in memory when browser storage is unavailable.
  }
}

function readStored(productId: string): StoredTasks | null {
  if (typeof window === "undefined") return null;
  try {
    const parsed = JSON.parse(
      window.sessionStorage.getItem(storageKey(productId)) ?? "null",
    ) as Partial<StoredTasks> | null;
    const taskIds = normalizeTaskIds(parsed?.taskIds);
    if (!parsed || taskIds.length === 0 || typeof parsed.startedAt !== "number") {
      removeStored(productId);
      return null;
    }
    if (Date.now() - parsed.startedAt > STORED_TASK_MAX_AGE_MS) {
      removeStored(productId);
      return null;
    }
    return {
      taskIds,
      startedAt: parsed.startedAt,
      initialStatus: normalizeInitialStatus(parsed.initialStatus),
    };
  } catch {
    removeStored(productId);
    return null;
  }
}

function writeStored(productId: string, value: StoredTasks | null): void {
  if (typeof window === "undefined") return;
  if (!value) {
    removeStored(productId);
    return;
  }
  try {
    window.sessionStorage.setItem(
      storageKey(productId),
      JSON.stringify({ ...value, taskIds: normalizeTaskIds(value.taskIds) }),
    );
  } catch {
    // Verification continues in memory when browser storage is unavailable.
  }
}

export function useVerification(productId: string) {
  const queryClient = useQueryClient();
  const revalidator = useRevalidator();
  const visible = usePageVisibility();
  const [taskIds, setTaskIds] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [initialStatus, setInitialStatus] = useState<VerificationRequest["status"] | null>(null);
  const terminalHandled = useRef(false);

  useEffect(() => {
    terminalHandled.current = false;
    const stored = readStored(productId);
    setTaskIds(stored?.taskIds ?? []);
    setStartedAt(stored?.startedAt ?? null);
    setInitialStatus(stored?.initialStatus ?? null);
  }, [productId]);

  const elapsed = startedAt ? Date.now() - startedAt : 0;
  const expired = Boolean(startedAt && elapsed >= POLL_TIMEOUT_MS);

  const mutation = useMutation({
    mutationFn: (mode: "best_offer" | "all_offers") => verifyPrice(productId, mode),
    onSuccess: (response) => {
      const now = Date.now();
      terminalHandled.current = false;
      const nextTaskIds = normalizeTaskIds(response.task_ids);
      setInitialStatus(response.status);
      setTaskIds(nextTaskIds);
      setStartedAt(nextTaskIds.length > 0 ? now : null);
      if (nextTaskIds.length > 0) {
        writeStored(productId, {
          taskIds: nextTaskIds,
          startedAt: now,
          initialStatus: response.status,
        });
      } else {
        writeStored(productId, null);
      }
      if (response.status === "fresh" || response.status === "cooldown") {
        void queryClient.invalidateQueries({ queryKey: productKeys.detail(productId) });
        void queryClient.invalidateQueries({ queryKey: verificationKeys.status(productId) });
        void revalidator.revalidate();
      }
    },
  });

  const jobQueries = useQueries({
    queries: taskIds.map((taskId) => ({
      queryKey: verificationKeys.job(taskId),
      queryFn: ({ signal }: { signal: AbortSignal }) => getVerificationJob(taskId, signal),
      enabled: visible && !expired,
      staleTime: 750,
      retry: 1,
      refetchIntervalInBackground: false,
        refetchInterval: (query: { state: { data?: VerificationJob } }) => {
        const status = query.state.data?.status;
        if (status && TERMINAL.has(status)) return false;
        // Faster initial polls so completed retailer tasks surface quickly;
        // modest backoff after 8s to limit API load.
        return Date.now() - (startedAt ?? Date.now()) < 8_000 ? 1_250 : 3_000;
      },
    })),
  });

  const jobs = jobQueries.flatMap((query) => (query.data ? [query.data] : []));
  const jobErrors = jobQueries.flatMap((query) => (query.isError ? [query.error] : []));
  const allTerminal =
    taskIds.length > 0 &&
    jobs.length === taskIds.length &&
    jobs.every((job) => TERMINAL.has(job.status));

  useEffect(() => {
    if (!allTerminal || terminalHandled.current) return;
    terminalHandled.current = true;
    writeStored(productId, null);
    void queryClient.invalidateQueries({ queryKey: productKeys.detail(productId) });
    void queryClient.invalidateQueries({ queryKey: productKeys.offers(productId) });
    void queryClient.invalidateQueries({ queryKey: verificationKeys.status(productId) });
    if (jobs.some((job) => job.status === "completed")) {
      void queryClient.invalidateQueries({ queryKey: productKeys.priceHistory(productId, 180) });
    }
    // PDP uses loader data — revalidate so best price / freshness / offers refresh.
    void revalidator.revalidate();
  }, [allTerminal, jobs, productId, queryClient, revalidator]);

  const summary = useMemo<VerificationSummary>(
    () =>
      deriveVerificationSummary({
        mutationPending: mutation.isPending,
        mutationError: mutation.error,
        expired,
        allTerminal,
        taskIds,
        jobs,
        jobErrors,
        initialStatus,
      }),
    [
      allTerminal,
      expired,
      initialStatus,
      jobErrors,
      jobs,
      mutation.error,
      mutation.isPending,
      taskIds,
    ],
  );

  const reset = () => {
    setTaskIds([]);
    setStartedAt(null);
    setInitialStatus(null);
    writeStored(productId, null);
    terminalHandled.current = false;
    mutation.reset();
  };

  return {
    mutation,
    jobs,
    summary,
    active: ACTIVE_SUMMARIES.has(summary),
    visible,
    expired,
    reset,
  };
}
