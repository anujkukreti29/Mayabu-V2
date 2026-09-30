import { describe, expect, it } from "vitest";
import { laptopSpecSummary } from "~/components/product/laptop-spec-summary";
import { productDisplaySpecs } from "~/lib/search/display-specs";
import type { Product } from "~/lib/api/schemas";

const base: Product = {
  id: "p1",
  title: "ASUS Vivobook 15",
  brand: "ASUS",
  category: "laptop",
  specs: {},
  best_price: 54990,
  best_platform: "Amazon India",
  platform_count: 2,
  image_url: null,
  last_seen_at: null,
  match_group: "exact_match",
  rank_score: null,
  variant_group_id: null,
};

describe("productDisplaySpecs / laptopSpecSummary", () => {
  it("builds chips from specs for laptops", () => {
    expect(
      laptopSpecSummary({
        ...base,
        specs: {
          model_codes: ["X1504VA"],
          cpu_models: ["Intel Core i5"],
          ram_gb: 16,
          storage_gb: 512,
          gpu: "Intel Iris Xe",
          screen_inch: 15.6,
        },
      }),
    ).toEqual(["X1504VA", "16 GB", "512 GB", '15.6"', "Intel Iris Xe"]);
  });

  it("formats terabyte storage cleanly", () => {
    expect(
      laptopSpecSummary({
        ...base,
        specs: { storage_gb: 1000 },
      }),
    ).toEqual(["1 TB"]);
  });

  it("prefers backend display_specs when present", () => {
    expect(
      productDisplaySpecs({
        ...base,
        category: "smartphone",
        display_specs: { ram_gb: 8, storage_gb: 256, network_generation: "5G" },
        specs: {},
      }),
    ).toEqual(["8 GB", "256 GB", "Network: 5G"]);
  });

  it("returns an empty list when specs are missing", () => {
    expect(laptopSpecSummary(base)).toEqual([]);
  });
});
