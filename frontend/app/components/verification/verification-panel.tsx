import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { Button } from "~/components/ui/button";
import { Card } from "~/components/ui/card";
import { getErrorMessage } from "~/lib/api/errors";
import { formatPrice, validPrice } from "~/lib/formatting/price";
import { useVerification } from "~/hooks/use-verification";
import type { VerificationSummary } from "~/lib/verification/state";

const copy: Record<VerificationSummary, { title: string; message: string; tone: string }> = {
  idle: {
    title: "Ready to verify",
    message: "Mayabu can check the selected known store listing in the background.",
    tone: "text-slate-700",
  },
  requesting: {
    title: "Preparing verification",
    message:
      "Mayabu is checking whether a recent verification or active shared job already exists.",
    tone: "text-brand-700",
  },
  fresh: {
    title: "Price verified recently",
    message: "Mayabu already has a recent verification, so a new scraper job was not needed.",
    tone: "text-emerald-700",
  },
  cooldown: {
    title: "Recently checked",
    message:
      "This listing is in a short cooldown period. Use the latest result or try again later.",
    tone: "text-amber-800",
  },
  busy: {
    title: "Verification queue is busy",
    message:
      "Mayabu cannot accept another verification job right now. The last known price remains available.",
    tone: "text-amber-800",
  },
  rate_limited: {
    title: "Too many verification requests",
    message:
      "Mayabu is limiting verification traffic to protect reliability. Use the recent result or try again later.",
    tone: "text-amber-800",
  },
  no_offers: {
    title: "No listing available to verify",
    message: "Mayabu does not currently have a known retailer listing for this product.",
    tone: "text-slate-700",
  },
  joined: {
    title: "Joined an existing verification",
    message:
      "Another user already requested this listing, so Mayabu is sharing the same verification job.",
    tone: "text-brand-700",
  },
  queued: {
    title: "Verification queued",
    message:
      "The request is waiting for a verification worker. The last known price remains visible.",
    tone: "text-amber-800",
  },
  running: {
    title: "Checking the store now",
    message: "Mayabu is verifying the selected listing. You can continue using this page.",
    tone: "text-brand-700",
  },
  completed: {
    title: "Price verified",
    message: "The verification completed. Mayabu refreshed the relevant product information.",
    tone: "text-emerald-700",
  },
  out_of_stock: {
    title: "Currently out of stock",
    message:
      "The listing appears out of stock. The previous valid price remains available as historical context.",
    tone: "text-amber-800",
  },
  blocked: {
    title: "Verification blocked by the store",
    message:
      "The retailer blocked the automated check or requested a captcha. Open the seller page to confirm the current price.",
    tone: "text-red-700",
  },
  unavailable: {
    title: "Store temporarily unavailable",
    message:
      "Mayabu could not access the store listing right now. The last known price remains visible.",
    tone: "text-amber-800",
  },
  failed: {
    title: "Could not verify right now",
    message:
      "The verification did not complete successfully. Mayabu kept the last valid known price.",
    tone: "text-red-700",
  },
  expired: {
    title: "Verification status expired",
    message:
      "The browser stopped waiting, but the backend job may still continue. Refresh the product status later.",
    tone: "text-amber-800",
  },
};

function ResultDetail({ jobs }: { jobs: ReturnType<typeof useVerification>["jobs"] }) {
  const completed = jobs.find((job) => job.status === "completed");
  if (!completed) return null;
  const result = completed.result;
  const oldPrice = typeof result.old_price === "number" ? result.old_price : null;
  const newPrice = typeof result.new_price === "number" ? result.new_price : null;
  if (validPrice(oldPrice) && validPrice(newPrice) && oldPrice !== newPrice) {
    return (
      <p className="mt-2 text-sm font-semibold text-emerald-800">
        Price changed from {formatPrice(oldPrice)} to {formatPrice(newPrice)}.
      </p>
    );
  }
  if (result.stock_status === "out_of_stock")
    return (
      <p className="mt-2 text-sm font-semibold text-amber-800">
        The listing appears out of stock. Previous price history remains available.
      </p>
    );
  return null;
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
    verification.summary === "completed" || verification.summary === "fresh"
      ? CheckCircle2
      : verification.active
        ? LoaderCircle
        : ["failed", "blocked"].includes(verification.summary)
          ? ShieldAlert
          : verification.summary === "idle"
            ? RefreshCw
            : Clock3;
  const error = verification.mutation.error;

  return (
    <Card className="p-5" aria-live="polite" aria-atomic="true">
      <div className="flex items-start gap-3">
        <Icon
          aria-hidden="true"
          className={`mt-0.5 h-5 w-5 shrink-0 ${state.tone} ${verification.active ? "animate-spin" : ""}`}
        />
        <div className="min-w-0 flex-1">
          <h2 className="font-black text-slate-950">{state.title}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">{state.message}</p>
          {!verification.visible && verification.active ? (
            <p className="mt-2 text-xs font-semibold text-amber-800">
              Polling is paused while this page is hidden.
            </p>
          ) : null}
          {error ? (
            <p className="mt-2 flex items-start gap-2 text-sm text-red-700">
              <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
              {getErrorMessage(error)}
            </p>
          ) : null}
          <ResultDetail jobs={verification.jobs} />
        </div>
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        <Button
          disabled={verification.active || offerCount === 0}
          onClick={() => verification.mutation.mutate("best_offer")}
        >
          Verify best price
        </Button>
        {offerCount > 1 ? (
          <Button
            variant="outline"
            disabled={verification.active}
            onClick={() => verification.mutation.mutate("all_offers")}
          >
            Verify all offers
          </Button>
        ) : null}
        {["failed", "blocked", "unavailable", "rate_limited", "expired"].includes(
          verification.summary,
        ) ? (
          <Button variant="ghost" onClick={verification.reset}>
            Reset status
          </Button>
        ) : null}
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-500">
        Verification checks known product-detail listings only. It may be queued, rate-limited,
        blocked by a retailer, or unable to confirm the offer.
      </p>
    </Card>
  );
}
