import { describe, expect, it } from "vitest";
import {
  buildSearchHref,
  parseFiltersParam,
  parseSearchUrl,
  serializeFiltersParam,
  toggleFilterValue,
} from "~/lib/search/url";
import { formatFacetValue, facetLabel } from "~/lib/search/facets";
import {
  formatProcessorValue,
  looksLikeInternalToken,
  variantIdentityLine,
} from "~/lib/search/format-spec";
import { categoryDisplayName } from "~/lib/search/categories";
import { platformDisplayName } from "~/lib/search/platforms";
import { compareBlockReasonFor } from "~/components/comparison/compare-provider";
import type { Product } from "~/lib/api/schemas";

const phone: Product = {
  id: "phone-1",
  title: "Samsung Galaxy S24",
  brand: "Samsung",
  category: "smartphone",
  specs: { ram_gb: 8, storage_gb: 256 },
  best_price: 69990,
  best_platform: "croma",
  platform_count: 2,
  image_url: null,
  last_seen_at: null,
  match_group: "exact_match",
  rank_score: null,
  variant_group_id: null,
};

const laptop: Product = {
  ...phone,
  id: "laptop-1",
  title: "ASUS Vivobook",
  category: "laptop",
};

describe("search URL helpers", () => {
  it("serializes category, filters, sort, and price", () => {
    const href = buildSearchHref(
      { q: "Galaxy S24", filters: {} },
      {
        category: "smartphone",
        sort: "price_asc",
        minPrice: 20000,
        maxPrice: 80000,
        filters: { storage_gb: [128, 256], ram_gb: 8 },
        resetOffset: true,
      },
    );
    expect(href).toContain("q=Galaxy+S24");
    expect(href).toContain("category=smartphone");
    expect(href).toContain("sort=price_asc");
    expect(href).toContain("min_price=20000");
    expect(href).toContain("max_price=80000");
    expect(href).toContain("filters=");
    expect(href).not.toContain("offset=");
  });

  it("toggles multi-value filters and clears empty keys", () => {
    let filters = toggleFilterValue({}, "brand", "samsung");
    expect(filters).toEqual({ brand: "samsung" });
    filters = toggleFilterValue(filters, "brand", "lg");
    expect(filters.brand).toEqual(["samsung", "lg"]);
    filters = toggleFilterValue(filters, "brand", "samsung");
    expect(filters).toEqual({ brand: "lg" });
    filters = toggleFilterValue(filters, "brand", "lg");
    expect(filters).toEqual({});
  });

  it("parses filters JSON safely", () => {
    expect(parseFiltersParam('{"ram_gb":8}')).toEqual({ ram_gb: 8 });
    expect(parseFiltersParam("not-json")).toEqual({});
    expect(serializeFiltersParam({ ram_gb: 8 })).toBe('{"ram_gb":8}');
  });

  it("parses a full search URL", () => {
    const url = new URL(
      "https://mayabu.local/search?q=tv&category=television&sort=price_desc&min_price=30000&filters=%7B%22screen_size_inch%22%3A55%7D&offset=20",
    );
    const state = parseSearchUrl(url);
    expect(state.q).toBe("tv");
    expect(state.category).toBe("television");
    expect(state.sort).toBe("price_desc");
    expect(state.minPrice).toBe(30000);
    expect(state.filters).toEqual({ screen_size_inch: 55 });
    expect(state.offset).toBe(20);
  });
});

describe("facet and category formatting", () => {
  it("maps facet labels and values", () => {
    expect(facetLabel("ram_gb")).toBe("RAM");
    expect(facetLabel("capacity_kg")).toBe("Capacity");
    expect(formatFacetValue("ram_gb", 8)).toBe("8 GB");
    expect(formatFacetValue("storage_gb", 256)).toBe("256 GB");
    expect(formatFacetValue("screen_size_inch", 55)).toBe('55"');
    expect(formatFacetValue("capacity_l", 260)).toBe("260 L");
    expect(formatFacetValue("capacity_kg", 8)).toBe("8 kg");
    expect(formatFacetValue("anc", true)).toBe("ANC");
    expect(formatFacetValue("load_type", "front_load")).toBe("Front Load");
    expect(formatFacetValue("brand", "lg")).toBe("LG");
    expect(formatFacetValue("panel_type", "qled")).toBe("QLED");
    expect(formatFacetValue("resolution", "4k")).toBe("4K");
    expect(formatFacetValue("cpu_series", "amd_ryzen:7:170")).toBe("AMD Ryzen 7 170");
    expect(formatFacetValue("cpu_series", "intel_core_ultra:7:155h")).toBe("Intel Core Ultra 7 155H");
    expect(formatFacetValue("chipset", "snapdragon:8_gen_3")).toBe("Snapdragon 8 Gen 3");
    expect(formatFacetValue("door_type", "double_door")).toBe("Double Door");
    expect(formatFacetValue("kit_lens", "body_18_45mm")).toBe("Body + 18–45mm Kit");
    expect(formatFacetValue("body_only", true)).toBe("Body Only");
    expect(formatFacetValue("inverter", false)).toBe("No");
    expect(formatFacetValue("cpu_series", null)).toBe("");
  });

  it("never renders raw processor or snake_case tokens in display form", () => {
    const samples = [
      formatFacetValue("cpu_series", "amd_ryzen:7:170"),
      formatFacetValue("cpu_series", "intel_core_ultra:7:155h"),
      formatFacetValue("load_type", "front_load"),
      formatFacetValue("body_only", true),
      formatProcessorValue("intel_celeron:n50"),
    ];
    for (const sample of samples) {
      expect(sample).not.toMatch(/amd_ryzen:/);
      expect(sample).not.toMatch(/front_load/);
      expect(sample).not.toMatch(/body_only/);
      expect(looksLikeInternalToken(sample)).toBe(false);
    }
    expect(formatProcessorValue("intel_celeron:n50")).toBe("Intel Celeron N50");
  });

  it("builds a compact variant identity line", () => {
    expect(
      variantIdentityLine({
        ...laptop,
        specs: { ram_gb: 8, storage_gb: 256 },
        display_specs: { ram_gb: 8, storage_gb: 256 },
      }),
    ).toBe("8 GB · 256 GB");
  });

  it("maps category and platform display names", () => {
    expect(categoryDisplayName("washing_machine")).toBe("Washing Machines");
    expect(categoryDisplayName("tws")).toBe("TWS & Earbuds");
    expect(platformDisplayName("reliancedigital")).toBe("Reliance Digital");
    expect(platformDisplayName("amazon")).toBe("Amazon");
  });
});

describe("compare safety", () => {
  it("allows all public categories", () => {
    expect(compareBlockReasonFor(laptop, [])).toBeNull();
    expect(compareBlockReasonFor(phone, [])).toBeNull();
  });

  it("blocks cross-category compare even for supported categories", () => {
    const fridge: Product = { ...laptop, id: "f1", category: "refrigerator" };
    expect(compareBlockReasonFor(fridge, [laptop])).toBe("category_mismatch");
  });
});
