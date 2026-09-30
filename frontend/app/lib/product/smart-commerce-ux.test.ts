import { describe, expect, it } from "vitest";
import { hardConflictWarning, matchEvidenceRows } from "~/lib/search/format-spec";
import type { Product } from "~/lib/api/schemas";
import { validatePriceWatch, watchDistanceLabel, watchSummaryLabel } from "~/lib/product/price-watch";
import { parseTargetPriceInput } from "~/components/product/watch-price-control";

const laptop = {
  id: "p1",
  title: "Laptop",
  brand: "Lenovo",
  category: "laptop",
  specs: { ram_gb: 16, storage_gb: 512, match_confidence: 0.92 },
  display_specs: { ram_gb: 16, storage_gb: 512 },
  model_codes: ["82XXXX"],
  best_price: 54990,
  best_platform: "amazon",
  platform_count: 2,
  image_url: null,
  last_seen_at: null,
  match_group: "exact_match",
  rank_score: 0.88,
  variant_group_id: null,
} as unknown as Product;

describe("matchEvidenceRows", () => {
  it("shows category fields and never surfaces raw scores", () => {
    const rows = matchEvidenceRows(laptop);
    expect(rows.some((row) => row.key === "ram_gb")).toBe(true);
    expect(rows.some((row) => row.key === "storage_gb")).toBe(true);
    const blob = JSON.stringify(rows);
    expect(blob).not.toMatch(/confidence|0\.92|rank_score|0\.88/i);
  });

  it("renders a restrained hard-conflict warning without scores", () => {
    const warning = hardConflictWarning({
      ...laptop,
      hard_conflicts: ["ram_gb", "storage_gb"],
    });
    expect(warning).toMatch(/RAM/i);
    expect(warning).not.toMatch(/confidence|score/i);
  });

  it.each([
    ["laptop", { ram_gb: 16, storage_gb: 512 }, ["ram_gb", "storage_gb"]],
    ["smartphone", { ram_gb: 8, storage_gb: 256 }, ["ram_gb", "storage_gb"]],
    ["television", { screen_size_inch: 55, panel_type: "OLED", resolution: "4K" }, ["panel_type"]],
    ["refrigerator", { capacity_l: 340, door_type: "double" }, ["capacity_l", "door_type"]],
    ["washing_machine", { capacity_kg: 7, load_type: "front" }, ["capacity_kg", "load_type"]],
    ["camera", { body_only: true, kit_lens: "18-55" }, ["kit_lens"]],
    ["headphones", { form_factor: "over-ear", connectivity: "wireless" }, ["form_factor"]],
    ["tws", { anc: true, generation: "3" }, ["anc", "generation"]],
  ] as const)("formats consumer-safe evidence for %s", (category, specs, expectedKeys) => {
    const rows = matchEvidenceRows({
      ...laptop,
      category,
      specs,
      display_specs: specs,
    });
    const keys = rows.map((row) => row.key);
    for (const key of expectedKeys) {
      expect(keys).toContain(key);
    }
    expect(JSON.stringify(rows)).not.toMatch(/hard_conflict|confidence|rank_score/i);
    expect(rows.every((row) => row.value && row.value !== "—")).toBe(true);
  });
});

describe("price watch validation", () => {
  it("accepts any meaningful drop mode", () => {
    expect(validatePriceWatch({ mode: "any_drop" })).toEqual({
      ok: true,
      value: null,
      mode: "any_drop",
    });
  });

  it("validates target prices against the current listed price", () => {
    expect(validatePriceWatch({ mode: "target", targetRaw: "" }).ok).toBe(false);
    expect(validatePriceWatch({ mode: "target", targetRaw: "49,990", currentPrice: 54990 })).toEqual({
      ok: true,
      value: 49990,
      mode: "target",
    });
    expect(
      validatePriceWatch({ mode: "target", targetRaw: "56000", currentPrice: 54990 }).ok,
    ).toBe(false);
  });

  it("formats watching / target labels lightly", () => {
    expect(watchSummaryLabel({ notifyOnDrop: true })).toBe("Watching");
    expect(watchSummaryLabel({ targetPrice: 49990 })).toBe("Target ₹49,990");
  });

  it("does not treat OOS last-known as a target hit", () => {
    expect(
      watchDistanceLabel({ targetPrice: 49999, currentPrice: 47990, purchasable: false }),
    ).toMatch(/buyable price unavailable/i);
    expect(
      watchDistanceLabel({ targetPrice: 49999, currentPrice: 54999, purchasable: true }),
    ).toBe("₹5,000 above target");
  });

  it("shares WatchPriceControl parser behavior", () => {
    expect(parseTargetPriceInput("₹49,999")).toEqual({ ok: true, value: 49999 });
    expect(parseTargetPriceInput("").ok).toBe(false);
  });
});
