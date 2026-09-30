import { describe, expect, it } from "vitest";
import { buildPriceEvidence, buildTimelineNote } from "~/lib/product/price-evidence";
import type { Offer, Product } from "~/lib/api/schemas";

const product = {
  id: "p1",
  title: "Phone",
  brand: "Samsung",
  category: "smartphone",
  best_price: 54990,
  best_platform: "amazon",
  platform_count: 2,
  image_url: null,
  last_seen_at: "2026-09-21T10:00:00Z",
} as unknown as Product;

describe("buildTimelineNote", () => {
  it("does not call a failed attempt a successful check", () => {
    expect(
      buildTimelineNote({
        status: "failed",
        lastSuccessAt: "2026-09-21T07:00:00Z",
        lastAttemptAt: "2026-09-21T10:00:00Z",
        failures: 1,
      }),
    ).toMatch(/Latest refresh unavailable · last successful check/i);
  });

  it("uses success freshness when the latest attempt succeeded", () => {
    const note = buildTimelineNote({
      status: "checked",
      lastSuccessAt: "2026-09-21T10:00:00Z",
      lastAttemptAt: "2026-09-21T10:00:00Z",
      failures: 0,
    });
    expect(note).not.toMatch(/unavailable/i);
  });
});

describe("buildPriceEvidence", () => {
  it("orders timeline by last successful check, not failed attempts", () => {
    const offers = [
      {
        id: "o1",
        platform: "amazon",
        price: 54990,
        stock_status: "in_stock",
        last_verified_at: "2026-09-21T07:00:00Z",
        last_checked_at: "2026-09-21T11:00:00Z",
        verification_status: "failed",
        verification_failures: 1,
      },
      {
        id: "o2",
        platform: "flipkart",
        price: 55990,
        stock_status: "in_stock",
        last_verified_at: "2026-09-21T09:00:00Z",
        last_checked_at: "2026-09-21T09:00:00Z",
        verification_status: "verified",
        verification_failures: 0,
      },
    ] as unknown as Offer[];

    const evidence = buildPriceEvidence({ product, offers });
    expect(evidence.timeline[0]?.platform).toBe("flipkart");
    expect(evidence.timeline.find((row) => row.platform === "amazon")?.timelineNote).toMatch(
      /Latest refresh unavailable/i,
    );
  });
});
