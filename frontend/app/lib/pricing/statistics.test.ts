import { describe, expect, it } from "vitest";
import { priceStatistics } from "~/lib/pricing/statistics";

describe("priceStatistics", () => {
  it("calculates valid values in one pass and ignores invalid prices", () => {
    expect(priceStatistics([100, null, 0, Number.NaN, 300, 200])).toEqual({
      count: 3,
      minimum: 100,
      maximum: 300,
      average: 200,
    });
  });

  it("returns null when no valid price exists", () => {
    expect(priceStatistics([null, undefined, 0, -1])).toBeNull();
  });
});
