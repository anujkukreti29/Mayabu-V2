import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { Button } from "~/components/ui/button";
import { getErrorMessage } from "~/lib/api/errors";
import { formatPrice, validPrice } from "~/lib/formatting/price";
import { useVerification } from "~/hooks/use-verification";
import {
  countVerificationChecks,
  verificationPriceDelta,
  type VerificationSummary,
} from "~/lib/verification/state";
import { cn } from "~/components/ui/cn";
import { platformDisplayName } from "~/lib/search/platforms";

const copy: Record<
  VerificationSummary,
  { title: string; message: string; tone: string; button: string }
> = {
  idle: {
    title: "Check latest price",
    message:
      "Mayabu can re-check known store product pages for this item. Current listed prices stay visible.",
    tone: "text-ink",
    button: "Check latest price",
  },
  requesting: {
    title: "Checking stores…",
    message: "Mayabu is preparing a fresh price check against known store listings.",
    tone: "text-brand-700",
    button: "Checking latest prices…",
  },
  fresh: {
    title: "Checked recently",
    message: "A recent successful check already exists, so Mayabu did not start another full refresh.",
    tone: "text-brand-700",
    button: "Check again later",
  },
  cooldown: {
    title: "Checked recently",
    message: "This product was checked recently. Please wait a few minutes before requesting again.",
    tone: "text-ink-soft",
    button: "Check again later",
  },
  busy: {
    title: "Checks are busy right now",
    message:
      "Mayabu cannot start another live check at the moment. The last known price remains available.",
    tone: "text-ink-soft",
    button: "Try again later",
  },
  rate_limited: {
    title: "Too many requests",
    message: "Please wait a minute before checking again. The last known price remains available.",
    tone: "text-ink-soft",
    button: "Try again later",
  },
  no_offers: {
    title: "No store listing to check",
    message: "No supported store listings are available to refresh right now.",
    tone: "text-ink-muted",
    button: "Check latest price",
  },
  joined: {
    title: "Joined an existing check",
    message: "A check for this product is already running. Mayabu is sharing that request.",
    tone: "text-brand-700",
    button: "Checking latest prices…",
  },
  queued: {
    title: "Check queued",
    message: "Your request is queued. Current listed prices stay visible until the check finishes.",
    tone: "text-ink-soft",
    button: "Checking latest prices…",
  },
  running: {
    title: "Checking latest prices…",
    message: "Mayabu is contacting known store pages now. You can keep browsing this product.",
    tone: "text-brand-700",
    button: "Checking latest prices…",
  },
  completed_unchanged: {
    title: "Price unchanged",
    message: "The latest check matched the previously stored price.",
    tone: "text-brand-700",
    button: "Checked just now",
  },
  completed_changed: {
    title: "Price updated",
    message: "Mayabu recorded a newer observed price from a store listing.",
    tone: "text-accent",
    button: "Checked just now",
  },
  partial: {
    title: "Partial check complete",
    message:
      "Some stores refreshed successfully; one or more stores were temporarily unavailable. Previous trusted prices remain available.",
    tone: "text-brand-700",
    button: "Partial check complete",
  },
  out_of_stock: {
    title: "Currently out of stock",
    message:
      "The checked listing appears out of stock. The previous valid price remains available as historical context.",
    tone: "text-ink-soft",
    button: "Checked just now",
  },
  stale_fallback: {
    title: "Showing last trusted price",
    message:
      "A fresher store check was not available. Mayabu is showing the last trusted price.",
    tone: "text-ink-soft",
    button: "Checked just now",
  },
  blocked: {
    title: "Latest check unavailable",
    message:
      "Latest check unavailable. Showing the last trusted price. Open the seller page to confirm.",
    tone: "text-ink-soft",
    button: "Couldn't refresh right now",
  },
  unavailable: {
    title: "Latest check unavailable",
    message: "Latest check unavailable. Showing the last trusted price.",
    tone: "text-ink-soft",
    button: "Couldn't refresh right now",
  },
  failed: {
    title: "Latest check unavailable",
    message: "Latest check unavailable. Showing the last trusted price.",
    tone: "text-ink-soft",
    button: "Couldn't refresh right now",
  },
  expired: {
    title: "Still checking in the background",
    message:
      "This page stopped waiting, but the check may still finish. Refresh the product shortly.",
    tone: "text-ink-soft",
    button: "Check status later",
  },
};

function ResultDetail({
  jobs,
  summary,
}: {
  jobs: ReturnType<typeof useVerification>["jobs"];
  summary: VerificationSummary;
}) {
  const counts = countVerificationChecks(jobs);
  const delta = verificationPriceDelta(jobs);
  const showJobRows = jobs.length > 0 && (summary === "running" || summary === "queued" || summary === "joined" || summary === "partial");

  return (
    <div className="mt-2 space-y-2">
      {showJobRows ? (
        <ul className="space-y-1.5" aria-label="Store check progress">
          {jobs.map((job) => {
            const label = platformDisplayName(job.platform) || job.platform || "Store";
            const done = ["completed", "failed", "dead", "cancelled"].includes(job.status);
            const running = job.status === "running";
            const failed = ["failed", "dead", "cancelled"].includes(job.status);
            return (
              <li
                key={job.task_id}
                className={cn(
                  "flex items-center gap-2 rounded-md border border-transparent px-2 py-1.5 text-sm transition duration-standard ease-mayabu",
                  running && "border-brand-200 bg-brand-50/80",
                  done && !failed && "border-emerald-100 bg-emerald-50/60",
                  failed && "border-slate-200 bg-slate-50",
                )}
              >
                <span
                  className={cn(
                    "inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold",
                    running && "bg-brand-600 text-white",
                    done && !failed && "bg-emerald-600 text-white",
                    failed && "bg-slate-400 text-white",
                    !running && !done && "bg-slate-300 text-white",
                  )}
                  aria-hidden="true"
                >
                  {done && !failed ? "✓" : running ? "…" : failed ? "!" : "○"}
                </span>
                <span className="min-w-0 flex-1 font-medium text-ink">{label}</span>
                <span className="text-xs text-ink-muted">
                  {running
                    ? "Checking"
                    : done && !failed
                      ? "Done"
                      : failed
                        ? "Unavailable"
                        : "Queued"}
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}

      {summary === "partial" && counts.total > 0 ? (
        <p className="text-sm font-medium text-brand-700">
          Checked {counts.successful} of {counts.total} stores
        </p>
      ) : null}

      {summary === "completed_changed" && validPrice(delta.oldPrice) && validPrice(delta.newPrice) ? (
        <p
          className={cn(
            "rounded-md bg-accent/10 px-2 py-1.5 text-sm font-semibold text-accent",
            "motion-safe:transition-[background-color,opacity] motion-safe:duration-slow",
            "motion-reduce:transition-none",
          )}
        >
          <span className="price-numerals">
            {formatPrice(delta.oldPrice)} → {formatPrice(delta.newPrice)}
          </span>
          <span className="font-medium text-ink-muted"> · checked just now</span>
        </p>
      ) : null}

      {summary === "completed_unchanged" ? (
        (() => {
          const still = validPrice(delta.newPrice)
            ? delta.newPrice
            : validPrice(delta.oldPrice)
              ? delta.oldPrice
              : null;
          if (still == null) {
            return <p className="text-sm font-medium text-brand-700">Checked just now</p>;
          }
          return (
            <p className="text-sm font-medium text-brand-700">
              Still <span className="price-numerals">{formatPrice(still)}</span>
              <span className="text-ink-muted"> · checked just now</span>
            </p>
          );
        })()
      ) : null}

      {summary === "out_of_stock" ? (
        <p className="text-sm font-medium text-ink-soft">
          The listing appears out of stock. Previous price history remains available.
        </p>
      ) : null}

      {["failed", "blocked", "unavailable"].includes(summary) ? (
        <p className="text-sm font-medium text-ink-soft">
          Latest check unavailable. Showing the last trusted price.
        </p>
      ) : null}
    </div>
  );
}

export function VerificationPanel({
  productId,
  offerCount,
}: {
  productId: string;
  offerCount: number;
}) {
  const verification = useVerification(productId);
  const state = copy[verification.summary];
  const Icon =
    verification.summary === "completed_unchanged" ||
    verification.summary === "completed_changed" ||
    verification.summary === "fresh" ||
    verification.summary === "partial"
      ? CheckCircle2
      : verification.active
        ? LoaderCircle
        : ["failed", "blocked"].includes(verification.summary)
          ? ShieldAlert
          : verification.summary === "idle"
            ? RefreshCw
            : Clock3;
  const error = verification.mutation.error;
  const canRequest =
    !verification.active &&
    offerCount > 0 &&
    !["fresh", "cooldown"].includes(verification.summary);
  const counts = countVerificationChecks(verification.jobs);
  const checkingProgress =
    verification.active && counts.total > 0
      ? counts.successful + counts.failed > 0
        ? `Checking ${counts.successful + counts.failed} of ${counts.total} stores…`
        : `Checking ${counts.total} store listing${counts.total === 1 ? "" : "s"}…`
      : verification.active && offerCount > 0
        ? "Checking known store listings…"
        : null;

  const buttonLabel = verification.active
    ? "Checking latest prices…"
    : verification.summary === "completed_unchanged" ||
        verification.summary === "completed_changed" ||
        verification.summary === "fresh" ||
        verification.summary === "stale_fallback"
      ? "Checked just now"
      : verification.summary === "partial"
        ? `Checked ${counts.successful} of ${counts.total || offerCount} stores`
        : verification.summary === "cooldown"
          ? "Checked recently"
          : ["failed", "blocked", "unavailable"].includes(verification.summary)
            ? "Couldn't refresh right now"
            : "Check latest price";

  return (
    <section
      id="check-price"
      className="surface-elevated scroll-mt-28 p-4 sm:p-5"
      aria-live="polite"
      aria-atomic="true"
    >
      <div className="flex items-start gap-3">
        <Icon
          aria-hidden="true"
          className={`mt-0.5 h-5 w-5 shrink-0 ${state.tone} ${verification.active ? "animate-spin" : ""}`}
        />
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold text-ink">{state.title}</h2>
          <p className="mt-1 text-sm leading-6 text-ink-muted">{state.message}</p>
          {checkingProgress ? (
            <p className="mt-2 text-sm font-medium text-brand-700">{checkingProgress}</p>
          ) : null}
          {!verification.visible && verification.active ? (
            <p className="mt-2 text-xs font-semibold text-ink-soft">
              Live updates pause while this tab is hidden.
            </p>
          ) : null}
          {error ? (
            <p className="mt-2 flex items-start gap-2 text-sm text-ink-soft">
              <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
              {getErrorMessage(error)}
            </p>
          ) : null}
          <ResultDetail jobs={verification.jobs} summary={verification.summary} />
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          disabled={!canRequest}
          onClick={() => verification.mutation.mutate("best_offer")}
          aria-label={state.button}
        >
          {verification.active ? "Checking latest prices…" : buttonLabel}
        </Button>
        {offerCount > 1 ? (
          <Button
            variant="outline"
            disabled={!canRequest}
            onClick={() => verification.mutation.mutate("all_offers")}
          >
            Check all stores
          </Button>
        ) : null}
        {[
          "failed",
          "blocked",
          "unavailable",
          "rate_limited",
          "expired",
          "partial",
          "stale_fallback",
        ].includes(verification.summary) ? (
          <Button variant="ghost" onClick={verification.reset}>
            Dismiss
          </Button>
        ) : null}
      </div>
      <p className="mt-3 text-xs leading-5 text-ink-muted">
        Checks known public store product pages only. Results may be queued, rate-limited, or
        blocked by a retailer. Mayabu never erases a previous trustworthy price on failure.
      </p>
    </section>
  );
}
