/** Price Watch validation helpers (wishlist target_price / notify_on_drop). */

export type WatchMode = "any_drop" | "target";

export type TargetPriceValidation =
  | { ok: true; value: number | null; mode: WatchMode }
  | { ok: false; error: string };

export function parseTargetPriceInput(raw: string): number | null {
  const cleaned = raw.replace(/[₹,\s]/g, "").trim();
  if (!cleaned) return null;
  const value = Number(cleaned);
  if (!Number.isFinite(value)) return null;
  return value;
}

export function validatePriceWatch(input: {
  mode: WatchMode;
  targetRaw?: string;
  currentPrice?: number | null;
}): TargetPriceValidation {
  if (input.mode === "any_drop") {
    return { ok: true, value: null, mode: "any_drop" };
  }
  const parsed = parseTargetPriceInput(input.targetRaw ?? "");
  if (parsed == null) {
    return { ok: false, error: "Enter a target price in rupees." };
  }
  if (parsed < 100) {
    return { ok: false, error: "Target price must be at least ₹100." };
  }
  if (parsed > 10_000_000) {
    return { ok: false, error: "Target price looks too high." };
  }
  if (
    input.currentPrice != null &&
    Number.isFinite(input.currentPrice) &&
    input.currentPrice > 0 &&
    parsed >= input.currentPrice
  ) {
    return {
      ok: false,
      error: "Choose a target below the current listed price.",
    };
  }
  return { ok: true, value: Math.round(parsed), mode: "target" };
}

export function watchSummaryLabel(input: {
  notifyOnDrop?: boolean | null;
  targetPrice?: number | null;
}): string | null {
  if (input.targetPrice != null && Number.isFinite(input.targetPrice) && input.targetPrice > 0) {
    return `Target ₹${Math.round(input.targetPrice).toLocaleString("en-IN")}`;
  }
  if (input.notifyOnDrop) return "Watching";
  return null;
}

/** Distance to target — never treats OOS last-known as a purchasable hit. */
export function watchDistanceLabel(input: {
  targetPrice?: number | null;
  currentPrice?: number | null;
  purchasable?: boolean;
}): string | null {
  const target = input.targetPrice;
  const current = input.currentPrice;
  if (target == null || !Number.isFinite(target) || target <= 0) return null;
  if (input.purchasable === false) {
    return "Target saved · current buyable price unavailable";
  }
  if (current == null || !Number.isFinite(current) || current <= 0) return null;
  const delta = Math.round(current - target);
  if (delta === 0) return "At target";
  if (delta > 0) {
    return `₹${delta.toLocaleString("en-IN")} above target`;
  }
  return `₹${Math.abs(delta).toLocaleString("en-IN")} below target`;
}

