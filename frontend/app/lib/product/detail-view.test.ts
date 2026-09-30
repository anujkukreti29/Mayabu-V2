import { describe, expect, it } from "vitest";
import type { Offer, Product } from "~/lib/api/schemas";
import {
  bestOfferId,
  categorySearchHref,
  limitedCoverageHint,
  productDetailSpecRows,
  sortOffersByPrice,
  storeCoverageCopy,
} from "~/lib/product/detail-view";
import { formatFacetValue } from "~/lib/search/facets";

function offer(partial: Partial<Offer> & { id: string }): Offer {
  return {
    platform: "amazon",
    listing_id: null,
    native_id: null,
    url: null,
    title: "Offer",
    image_url: null,
    price: null,
    mrp: null,
    effective_price: null,
    discount_percent: null,
    currency: "INR",
    stock_status: null,
    rating: null,
    review_count: null,
    last_checked_at: null,
    last_verified_at: null,
    verification_status: null,
    verification_source: null,
    next_allowed_verification_at: null,
    verification_failures: 0,
    ...partial,
  };
}

const baseProduct = {
  id: "x",
  title: "Sample",
  brand: "Brand",
  category: "laptop",
  specs: {},
  best_price: 1000,
  best_platform: "amazon",
  platform_count: 1,
  image_url: null,
  last_seen_at: null,
  match_group: "exact_match" as const,
  rank_score: null,
  variant_group_id: null,
};

describe("detail-view helpers", () => {
  it("prefers in-stock offers over cheaper out-of-stock last-known prices", () => {
    const sorted = sortOffersByPrice([
      offer({ id: "oos", platform: "amazon", price: 50_000, stock_status: "out_of_stock" }),
      offer({ id: "live", platform: "croma", price: 55_000, stock_status: "in_stock" }),
    ]);
    expect(sorted.map((row) => row.id)).toEqual(["live", "oos"]);
    expect(bestOfferId(sorted)).toBe("live");
  });

  it("builds category search breadcrumbs to canonical landing routes", () => {
    expect(categorySearchHref("laptop")).toBe("/laptops");
    expect(categorySearchHref("smartphone")).toBe("/smartphones");
    expect(categorySearchHref("camera")).toBe("/cameras");
    expect(categorySearchHref("television")).toBe("/televisions");
  });

  it("reports truthful store coverage copy", () => {
    expect(storeCoverageCopy(1)).toBe("Available from 1 store");
    expect(storeCoverageCopy(3)).toBe("Compare prices at 3 stores");
    expect(limitedCoverageHint(1)).toMatch(/More store coverage/);
    expect(limitedCoverageHint(3)).toBeNull();
  });

  it("renders camera body-only vs kit distinctly from display specs", () => {
    const body: Product = {
      ...baseProduct,
      category: "camera",
      title: "Body",
      display_specs: { body_only: true, megapixels: 33, camera_type: "mirrorless" },
    };
    const kit: Product = {
      ...baseProduct,
      category: "camera",
      title: "Kit",
      display_specs: { body_only: false, kit_lens: "28-70mm", megapixels: 33 },
    };
    const bodyRows = productDetailSpecRows(body);
    const kitRows = productDetailSpecRows(kit);
    expect(bodyRows.some((row) => row.value === "Body Only")).toBe(true);
    expect(kitRows.some((row) => row.value === "With kit")).toBe(true);
    expect(kitRows.some((row) => row.value === "28-70mm")).toBe(true);
    expect(formatFacetValue("megapixels", 33)).toBe("33 MP");
  });

  it("falls back to normalized specs for smartphones and TVs", () => {
    const phoneRows = productDetailSpecRows({
      ...baseProduct,
      category: "smartphone",
      display_specs: { ram_gb: 8, storage_gb: 256, network_generation: "5G" },
    });
    expect(phoneRows.map((row) => row.label)).toEqual(
      expect.arrayContaining(["RAM", "Storage", "Network"]),
    );

    const tvRows = productDetailSpecRows({
      ...baseProduct,
      category: "television",
      display_specs: { screen_size_inch: 55, panel_type: "oled", resolution: "4k" },
    });
    expect(tvRows.some((row) => row.label === "Screen Size")).toBe(true);
  });
});
