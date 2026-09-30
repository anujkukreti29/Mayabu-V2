import { formatPrice, validPrice } from "~/lib/formatting/price";
import type { PriceIntelligence } from "~/lib/api/schemas";
import {
  intelligenceSignalLabel,
  intelligenceSignalTone,
  mapIntelligenceReasons,
  normalizeIntelligenceState,
  primaryIntelligenceExplanation,
} from "~/lib/product/price-intelligence-copy";
import { cn } from "~/components/ui/cn";

function windowNumber(windows: Record<string, unknown>, key: string, field: string): number | null {
  const node = windows[key];
  if (!node || typeof node !== "object") return null;
  const value = (node as Record<string, unknown>)[field];
  return validPrice(value) ? Number(value) : null;
}

function displayOrDash(value: number | null | undefined): string {
  return validPrice(value) ? formatPrice(value) : "—";
}

const toneClass = {
  consider: "text-accent",
  watch: "text-brand-700",
  wait: "text-amber-900",
  neutral: "text-ink-soft",
} as const;

export function PriceIntelligencePanel({
  intelligence,
}: {
  intelligence: PriceIntelligence;
}) {
  const signal = intelligence.timing_signal;
  const state = normalizeIntelligenceState(signal.state);
  const label = intelligenceSignalLabel(state, signal.label);
  const tone = intelligenceSignalTone(state);
  const codes = intelligence.reason_codes?.length
    ? intelligence.reason_codes
    : signal.reason_codes || [];
  const rawReasons = intelligence.reasons?.length ? intelligence.reasons : signal.reasons || [];
  const explanation = primaryIntelligenceExplanation(rawReasons, codes);
  const decisionReasons = mapIntelligenceReasons(codes, rawReasons);
  const current = intelligence.current?.price ?? intelligence.current_price;
  const tracked = intelligence.history_summary;
  const windows = intelligence.windows || {};
  const low30 = windowNumber(windows, "30d", "low");
  const low90 = windowNumber(windows, "90d", "low");
  const stores = intelligence.store_coverage?.in_stock_count ?? intelligence.store_coverage?.store_count ?? 0;
  const hours = intelligence.freshness?.hours;
  const purchasability = intelligence.purchasability || intelligence.current?.purchasability || signal.purchasability;
  const stale =
    (hours != null && hours > 24) ||
    codes.includes("STALE_OFFERS") ||
    codes.includes("FRESHNESS_DOWNGRADED");
  const oos =
    purchasability === "out_of_stock" ||
    (signal.in_stock_count === 0 && (signal.store_count || 0) > 0) ||
    codes.includes("OOS_ONLY") ||
    codes.includes("NO_IN_STOCK_PRICE");
  const suppressPositive = oos || stale || state === "UNAVAILABLE" || state === "INSUFFICIENT_HISTORY";
  const displayLabel =
    suppressPositive && state === "CONSIDER_NOW"
      ? intelligenceSignalLabel(oos ? "UNAVAILABLE" : "WATCH")
      : label;
  const displayTone = suppressPositive && state === "CONSIDER_NOW" ? "neutral" : tone;

  const freshness =
    hours == null
      ? null
      : hours < 1
        ? "checked just now"
        : hours < 24
          ? `checked ${Math.round(hours)} hour${Math.round(hours) === 1 ? "" : "s"} ago`
          : `checked ${Math.round(hours / 24)} day${Math.round(hours / 24) === 1 ? "" : "s"} ago`;

  const observations = tracked.observation_count ?? 0;
  const trackingDays = tracked.tracking_days ?? 0;

  return (
    <div className="surface p-5">
      <p className="eyebrow">Price intelligence</p>
      <h2 className={cn("mt-1.5 text-title-sm font-semibold tracking-tight", toneClass[displayTone])}>
        {displayLabel}
      </h2>
      <p className="mt-2 text-sm leading-6 text-ink-muted">{explanation}</p>
      {oos ? (
        <p className="mt-2 text-sm text-ink-muted">Last-known price — currently out of stock.</p>
      ) : null}
      {stale && !oos ? (
        <p className="mt-2 text-sm text-ink-muted">
          Current price data is stale. Refresh before treating this as a buying moment.
        </p>
      ) : null}

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-ink-soft">Current</dt>
          <dd className="price-numerals font-semibold text-ink">{displayOrDash(current)}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">30-day low</dt>
          <dd className="price-numerals font-semibold text-ink">{displayOrDash(low30)}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">90-day low</dt>
          <dd className="price-numerals font-semibold text-ink">{displayOrDash(low90)}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Tracked low</dt>
          <dd className="price-numerals font-semibold text-ink">{displayOrDash(tracked.tracked_low)}</dd>
        </div>
      </dl>

      <p className="mt-3 text-xs text-ink-soft">
        {observations} observation{observations === 1 ? "" : "s"}
        {" · "}
        {trackingDays} tracked day{trackingDays === 1 ? "" : "s"}
        {stores ? ` · ${stores} store${stores === 1 ? "" : "s"}` : ""}
        {freshness ? ` · ${freshness}` : ""}
        {" · "}
        Window lows are the lowest Mayabu-tracked prices in that window, not a market all-time claim.
      </p>

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-semibold text-accent">How Mayabu decided</summary>
        <ul className="mt-2 space-y-1.5 leading-6 text-ink-muted">
          {decisionReasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
        <p className="mt-2 leading-6 text-ink-muted">
          {intelligence.disclosure ||
            "Mayabu compares the current public price with prices it has observed over time. It does not predict future retailer prices."}
        </p>
      </details>
    </div>
  );
}
