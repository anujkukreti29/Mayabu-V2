/** Consumer-facing Price Intelligence labels and reason mapping. No confidence %. */

export type IntelligenceSignalState = string;

const REASON_COPY: Record<string, string> = {
  NEAR_RECENT_LOW: "The current price is close to the lowest Mayabu has tracked recently.",
  ABOVE_RECENT_LOW: "The current price sits meaningfully above the recent tracked low.",
  RECENT_DROP_ABOVE_LOW: "The price has fallen recently, but it is still above the tracked low.",
  WITHIN_TRACKED_RANGE: "The current price sits inside the recent tracked range.",
  MIXED_EVIDENCE: "Evidence is mixed, so Mayabu is not issuing a strong buy or wait signal.",
  MULTI_STORE: "More than one store currently shows an in-stock public price.",
  SINGLE_STORE: "Only one eligible retailer currently has an in-stock public price.",
  FRESH: "The latest store checks are recent enough to use.",
  STALE_OFFERS: "Current offers are older than Mayabu’s freshness threshold.",
  FRESHNESS_DOWNGRADED: "Fresher checks would help before treating this as a buying moment.",
  INSUFFICIENT_HISTORY: "Mayabu needs more tracked observations before judging timing.",
  OOS_ONLY: "Checked stores currently show this configuration as out of stock.",
  NO_POSITIVE_BUY_SIGNAL: "Mayabu is not presenting a buy signal while stock or freshness is weak.",
  NO_PRICED_OFFERS: "No current public priced offers are available to evaluate.",
  NO_IN_STOCK_PRICE: "No in-stock public price is available right now.",
  NOT_A_PREDICTION: "This is not a forecast that a lower price will return.",
};

export function normalizeIntelligenceState(state: string | null | undefined): string {
  const raw = (state || "").trim().toUpperCase();
  if (raw === "WAIT") return "WAIT_FOR_BETTER_PRICE";
  return raw || "UNAVAILABLE";
}

export function intelligenceSignalLabel(state: string | null | undefined, fallback?: string | null): string {
  const normalized = normalizeIntelligenceState(state);
  if (normalized === "CONSIDER_NOW") return "Consider now";
  if (normalized === "WATCH") return "Watch";
  if (normalized === "WAIT_FOR_BETTER_PRICE") return "Wait for a better price";
  if (normalized === "INSUFFICIENT_HISTORY") return fallback?.trim() || "Not enough history";
  if (normalized === "UNAVAILABLE") return "Price timing unavailable";
  if (fallback && fallback.trim()) return fallback.trim();
  return normalized.replaceAll("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

/** Restrained tones — not stock-trading red/green. */
export function intelligenceSignalTone(
  state: string | null | undefined,
): "consider" | "watch" | "wait" | "neutral" {
  const normalized = normalizeIntelligenceState(state);
  if (normalized === "CONSIDER_NOW") return "consider";
  if (normalized === "WATCH") return "watch";
  if (normalized === "WAIT_FOR_BETTER_PRICE") return "wait";
  return "neutral";
}

export function mapIntelligenceReasons(
  codes: readonly string[] | null | undefined,
  fallbackReasons: readonly string[] | null | undefined,
): string[] {
  const mapped = (codes || [])
    .map((code) => REASON_COPY[String(code).toUpperCase()] || null)
    .filter((value): value is string => Boolean(value));
  if (mapped.length > 0) return [...new Set(mapped)].slice(0, 4);
  return (fallbackReasons || []).filter((text) => text && !/%\s*confidence/i.test(text)).slice(0, 3);
}

export function primaryIntelligenceExplanation(
  reasons: readonly string[] | null | undefined,
  codes: readonly string[] | null | undefined,
): string {
  // Prefer concrete consumer sentences from the API when present.
  const factual = (reasons || []).find(
    (text) => text && /\d/.test(text) && !/%\s*confidence/i.test(text),
  );
  if (factual) return factual;
  const mapped = mapIntelligenceReasons(codes, reasons);
  if (mapped[0]) return mapped[0];
  return "Mayabu does not yet have a price-timing judgment for this product.";
}
