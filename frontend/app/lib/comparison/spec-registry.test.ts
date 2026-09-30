import { describe, expect, it } from "vitest";
import {
  compareBlockReasonFor,
  compareBlockMessage,
} from "~/components/comparison/compare-provider";
import { parseCompareIdsFromSearch, comparePath } from "~/lib/api/compare";
import {
  keyDifferenceRows,
  resolveCompareRows,
  formatCompareSpecValue,
  comparisonRowsFor,
  priceDifferenceLabel,
  presentCompareGroups,
  filterCompareRows,
  payingExtraLine,
} from "~/lib/comparison/spec-registry";
import type { Product } from "~/lib/api/schemas";

function product(partial: Partial<Product> & Pick<Product, "id" | "title" | "category">): Product {
  return {
    brand: "Test",
    specs: {},
    best_price: 10000,
    best_platform: "amazon",
    platform_count: 1,
    offer_count: 1,
    image_url: null,
    last_seen_at: null,
    match_group: "exact_match",
    rank_score: null,
    variant_group_id: null,
    ...partial,
  };
}

describe("CompareProvider rules", () => {
  it("allows all public categories and enforces same-category + max 4", () => {
    const phone = product({ id: "1", title: "Phone", category: "smartphone" });
    const phone2 = product({ id: "2", title: "Phone 2", category: "smartphone" });
    const laptop = product({ id: "3", title: "Laptop", category: "laptop" });
    expect(compareBlockReasonFor(phone, [])).toBeNull();
    expect(compareBlockReasonFor(laptop, [phone])).toBe("category_mismatch");
    expect(compareBlockMessage("category_mismatch")).toMatch(/same category/i);
    const full = [
      phone,
      phone2,
      product({ id: "4", title: "P3", category: "smartphone" }),
      product({ id: "5", title: "P4", category: "smartphone" }),
    ];
    expect(
      compareBlockReasonFor(product({ id: "6", title: "P5", category: "smartphone" }), full),
    ).toBe("full");
  });

  it("treats already-selected products as unblocked for toggle", () => {
    const phone = product({ id: "1", title: "Phone", category: "smartphone" });
    expect(compareBlockReasonFor(phone, [phone])).toBeNull();
  });
});

describe("compare URL helpers", () => {
  it("parses ids/products, dedupes, and caps at 4", () => {
    expect(parseCompareIdsFromSearch("?ids=a,a,b,c,d,e")).toEqual(["a", "b", "c", "d"]);
    expect(parseCompareIdsFromSearch("?products=p1,p2")).toEqual(["p1", "p2"]);
    expect(comparePath(["p1", "p1", "p2"])).toBe("/compare?ids=p1%2Cp2");
  });
});

describe("category compare spec registry", () => {
  it("builds camera body vs kit differences", () => {
    const body = product({
      id: "cam-1",
      title: "Body",
      category: "camera",
      display_specs: { body_only: true, megapixels: 33 },
      specs: { body_only: true, megapixels: 33 },
    });
    const kit = product({
      id: "cam-2",
      title: "Kit",
      category: "camera",
      display_specs: { body_only: false, kit_lens: "28-70mm", megapixels: 33 },
      specs: { body_only: false, kit_lens: "28-70mm", megapixels: 33 },
    });
    const rows = resolveCompareRows("camera", [body, kit]);
    const bodyRow = rows.find((row) => row.def.key === "body_only");
    expect(bodyRow?.differs).toBe(true);
    expect(bodyRow?.values).toEqual(["Body Only", "With kit"]);
    expect(keyDifferenceRows(rows).some((row) => row.def.key === "body_only")).toBe(true);
  });

  it("highlights phone storage and TV size variants", () => {
    const phone128 = product({
      id: "a",
      title: "128",
      category: "smartphone",
      display_specs: { storage_gb: 128, ram_gb: 8 },
    });
    const phone256 = product({
      id: "b",
      title: "256",
      category: "smartphone",
      display_specs: { storage_gb: 256, ram_gb: 8 },
    });
    const phoneRows = resolveCompareRows("smartphone", [phone128, phone256]);
    expect(phoneRows.find((row) => row.def.key === "storage_gb")?.differs).toBe(true);

    const tv43 = product({
      id: "t1",
      title: "43",
      category: "television",
      display_specs: { screen_size_inch: 43 },
    });
    const tv55 = product({
      id: "t2",
      title: "55",
      category: "television",
      display_specs: { screen_size_inch: 55 },
    });
    const tvRows = resolveCompareRows("television", [tv43, tv55]);
    expect(tvRows.find((row) => row.def.key === "screen_size_inch")?.differs).toBe(true);
  });

  it("hides all-missing rows and keeps partial missing as differences", () => {
    const a = product({
      id: "a",
      title: "A",
      category: "laptop",
      display_specs: { ram_gb: 16 },
    });
    const b = product({
      id: "b",
      title: "B",
      category: "laptop",
      display_specs: { ram_gb: 16, gpu: "RTX" },
    });
    const rows = resolveCompareRows("laptop", [a, b]);
    expect(rows.every((row) => !row.allMissing)).toBe(true);
    expect(rows.find((row) => row.def.key === "gpu")?.differs).toBe(true);
    expect(rows.find((row) => row.def.key === "ram_gb")?.differs).toBe(false);
  });

  it("covers appliance and audio registries", () => {
    expect(comparisonRowsFor("refrigerator").some((row) => row.key === "capacity_l")).toBe(true);
    expect(comparisonRowsFor("washing_machine").some((row) => row.key === "capacity_kg")).toBe(
      true,
    );
    expect(comparisonRowsFor("tws").some((row) => row.key === "anc")).toBe(true);
    expect(comparisonRowsFor("headphones").some((row) => row.key === "connectivity")).toBe(true);
    const washerA = product({
      id: "w1",
      title: "7kg",
      category: "washing_machine",
      display_specs: { capacity_kg: 7 },
    });
    const washerB = product({
      id: "w2",
      title: "9kg",
      category: "washing_machine",
      display_specs: { capacity_kg: 9 },
    });
    expect(formatCompareSpecValue(washerA, comparisonRowsFor("washing_machine")[0]!)).toBe("7 kg");
    expect(priceDifferenceLabel([washerA, washerB])).toBeNull();
    expect(
      priceDifferenceLabel([
        { ...washerA, best_price: 20000 },
        { ...washerB, best_price: 25000 },
      ]),
    ).toMatch(/₹5,000/);
  });

  it("formats laptop processor tokens instead of raw canonical values", () => {
    const machine = product({
      id: "lap-1",
      title: "TUF",
      category: "laptop",
      display_specs: { cpu_series: "amd_ryzen:7:170", ram_gb: 16 },
      specs: { cpu_models: ["amd_ryzen:7:170"] },
    });
    const processor = comparisonRowsFor("laptop").find((row) => row.key === "processor")!;
    expect(formatCompareSpecValue(machine, processor)).toBe("AMD Ryzen 7 170");
    expect(formatCompareSpecValue(machine, processor)).not.toMatch(/amd_ryzen:/);
    const fromModels = product({
      id: "lap-2",
      title: "TUF 2",
      category: "laptop",
      specs: { cpu_models: ["intel_celeron:n50"] },
    });
    expect(formatCompareSpecValue(fromModels, processor)).toBe("Intel Celeron N50");
  });

  it("exposes group filters and key-difference / storage filters", () => {
    const a = product({
      id: "a",
      title: "A",
      category: "laptop",
      best_price: 50000,
      display_specs: { ram_gb: 8, storage_gb: 256, screen_inch: 15.6 },
    });
    const b = product({
      id: "b",
      title: "B",
      category: "laptop",
      best_price: 65000,
      display_specs: { ram_gb: 16, storage_gb: 512, screen_inch: 15.6 },
    });
    const rows = resolveCompareRows("laptop", [a, b]);
    expect(presentCompareGroups(rows)).toEqual(expect.arrayContaining(["Storage", "Display"]));
    expect(filterCompareRows(rows, "Storage").every((row) => row.def.group === "Storage")).toBe(
      true,
    );
    expect(filterCompareRows(rows, "key_differences").every((row) => row.differs)).toBe(true);
    expect(payingExtraLine([a, b], keyDifferenceRows(rows))).toMatch(/₹15,000 more/);
  });
});
