import { describe, expect, it } from "vitest";
import { buildBuyingInsight } from "~/lib/pricing/insight";

describe("buildBuyingInsight", () => {
  it("uses limited data when the current price or history is insufficient", () => {
    expect(buildBuyingInsight(null, [100, 110, 120]).badge).toBe("Limited data");
    expect(buildBuyingInsight(100, [100, 110]).badge).toBe("Limited data");
  });

  it("identifies a price near the observed low", () => {
    expect(buildBuyingInsight(101, [100, 120, 140]).badge).toBe("Near observed low");
  });

  it("identifies a price above the observed average", () => {
    expect(buildBuyingInsight(150, [100, 110, 120]).badge).toBe("Above recent average");
  });
});
