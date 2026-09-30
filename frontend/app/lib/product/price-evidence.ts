import { formatPrice, validPrice } from "~/lib/formatting/price";
import { freshnessFrom } from "~/lib/formatting/freshness";
import { platformDisplayName } from "~/lib/search/platforms";
import type { Offer, PriceHistory, Product } from "~/lib/api/schemas";

export interface StoreCheckFact {
  platform: string;
  label: string;
  status: "checked" | "failed" | "blocked" | "pending" | "unknown";
  statusLabel: string;
  price: number | null;
  checkedAt: string | null;
  freshnessLabel: string;
  timelineNote: string;
}

export interface PriceEvidenceModel {
  checkedCount: number;
  storeCount: number;
  bestPrice: number | null;
  bestRetailer: string | null;
  previousTrackedPrice: number | null;
  lowestSinceTracking: number | null;
  freshestCheckedAt: string | null;
  freshnessLabel: string;
  stores: StoreCheckFact[];
  timeline: StoreCheckFact[];
  decisionFacts: string[];
  priceMovement: string | null;
}

function offerStatus(offer: Offer): StoreCheckFact["status"] {
  const raw = (offer.verification_status || "").toLowerCase();
  if (raw === "verified" || raw === "out_of_stock") return "checked";
  if (raw === "failed") return "failed";
  if (raw === "blocked") return "blocked";
  if (raw === "pending" || raw === "queued" || raw === "running") return "pending";
  if ((offer.verification_failures || 0) > 0) return "failed";
  return "unknown";
}

function statusLabel(status: StoreCheckFact["status"], stock?: string | null): string {
  if (status === "checked" && stock === "out_of_stock") return "Checked · out of stock";
  if (status === "checked") return "Checked";
  if (status === "failed") return "Latest refresh unavailable";
  if (status === "blocked") return "Latest refresh unavailable";
  if (status === "pending") return "Check in progress";
  return "Not checked recently";
}

/** Attempt vs success: never call a failed attempt a successful check. */
export function buildTimelineNote(input: {
  status: StoreCheckFact["status"];
  lastSuccessAt: string | null;
  lastAttemptAt: string | null;
  failures: number;
}): string {
  const { status, lastSuccessAt, lastAttemptAt, failures } = input;
  const successLabel = lastSuccessAt ? freshnessFrom(lastSuccessAt).label : null;
  const attemptNewerThanSuccess =
    Boolean(lastAttemptAt) &&
    Boolean(lastSuccessAt) &&
    Date.parse(lastAttemptAt!) > Date.parse(lastSuccessAt!) + 1000;

  if (status === "pending") return "Check in progress";

  if (status === "failed" || status === "blocked" || (failures > 0 && attemptNewerThanSuccess)) {
    if (successLabel) {
      return `Latest refresh unavailable · last successful check ${successLabel.replace(/^Checked\s+/i, "")}`;
    }
    return "Latest refresh unavailable";
  }

  if (status === "checked" && successLabel) return successLabel;
  if (successLabel) return successLabel;
  return "No recent successful check yet";
}

export function buildPriceEvidence({
  product,
  offers,
  history,
}: {
  product: Product;
  offers: readonly Offer[];
  history?: PriceHistory | null;
}): PriceEvidenceModel {
  const stores: StoreCheckFact[] = offers.map((offer) => {
    const status = offerStatus(offer);
    const lastSuccessAt = offer.last_verified_at || null;
    const lastAttemptAt = offer.last_checked_at || null;
    const failures = offer.verification_failures || 0;
    const attemptNewerThanSuccess =
      Boolean(lastAttemptAt) &&
      Boolean(lastSuccessAt) &&
      Date.parse(lastAttemptAt!) > Date.parse(lastSuccessAt!) + 1000;
    const displayStatus: StoreCheckFact["status"] =
      status === "checked" && failures > 0 && attemptNewerThanSuccess ? "failed" : status;
    const checkedAt = lastSuccessAt;
    const freshnessLabel = freshnessFrom(checkedAt).label;
    return {
      platform: offer.platform || "unknown",
      label: platformDisplayName(offer.platform) || offer.platform || "Store",
      status: displayStatus,
      statusLabel: statusLabel(displayStatus, offer.stock_status),
      price: validPrice(offer.price) ? offer.price : null,
      checkedAt,
      freshnessLabel,
      timelineNote: buildTimelineNote({
        status: displayStatus,
        lastSuccessAt,
        lastAttemptAt,
        failures,
      }),
    };
  });

  const timeline = [...stores].sort((a, b) => {
    const aTime = a.checkedAt ? Date.parse(a.checkedAt) : 0;
    const bTime = b.checkedAt ? Date.parse(b.checkedAt) : 0;
    if (aTime !== bTime) return bTime - aTime;
    return a.label.localeCompare(b.label);
  });

  const checked = stores.filter((store) => store.status === "checked");
  const freshest = timeline.find((store) => store.checkedAt) ?? null;

  const historyPoints = [...(history?.history ?? [])].sort((a, b) =>
    String(b.date || b.observed_at || "").localeCompare(String(a.date || a.observed_at || "")),
  );
  const previousHistory = historyPoints[1];
  const previousTracked =
    previousHistory && validPrice(previousHistory.best_price)
      ? previousHistory.best_price
      : null;
  const lows = historyPoints
    .map((point) => point.best_price)
    .filter((price): price is number => validPrice(price));
  const lowestSinceTracking = lows.length >= 2 ? Math.min(...lows) : null;

  const bestPrice = validPrice(product.best_price) ? product.best_price : null;
  const bestRetailer = platformDisplayName(product.best_platform);
  let priceMovement: string | null = null;
  if (bestPrice != null && previousTracked != null) {
    const delta = bestPrice - previousTracked;
    if (Math.abs(delta) >= 100 || Math.abs(delta) / previousTracked >= 0.02) {
      priceMovement =
        delta < 0
          ? `Down ${formatPrice(Math.abs(delta))} since previous tracked price`
          : `Up ${formatPrice(delta)} since previous tracked price`;
    } else {
      priceMovement = "No meaningful change since previous tracked price";
    }
  }

  const decisionFacts: string[] = [];
  const storeCount = offers.length;
  if (storeCount > 0) {
    decisionFacts.push(
      `${storeCount} public store${storeCount === 1 ? "" : "s"} currently compared`,
    );
  }
  if (bestPrice != null && lowestSinceTracking != null && bestPrice <= lowestSinceTracking) {
    decisionFacts.push(`At lowest since Mayabu started tracking (${formatPrice(lowestSinceTracking)})`);
  }
  if (
    bestPrice != null &&
    previousTracked != null &&
    previousTracked > bestPrice &&
    (previousTracked - bestPrice >= 100 || (previousTracked - bestPrice) / previousTracked >= 0.02)
  ) {
    decisionFacts.push(`Price fell ${formatPrice(previousTracked - bestPrice)} vs prior tracked day`);
  }
  if (freshest?.freshnessLabel) {
    decisionFacts.push(freshest.freshnessLabel);
  }

  return {
    checkedCount: checked.length,
    storeCount,
    bestPrice,
    bestRetailer,
    previousTrackedPrice: previousTracked,
    lowestSinceTracking,
    freshestCheckedAt: freshest?.checkedAt ?? null,
    freshnessLabel: freshest ? freshest.freshnessLabel : freshnessFrom(product.last_seen_at).label,
    stores,
    timeline,
    decisionFacts: decisionFacts.slice(0, 4),
    priceMovement,
  };
}
