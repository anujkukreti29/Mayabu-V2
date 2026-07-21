import { describe, expect, it } from "vitest";
import { formatPrice, validDiscount, validPrice } from "~/lib/formatting/price";

describe("price formatting", () => {
  it("formats a valid INR price", () => expect(formatPrice(69999)).toBe("₹69,999"));
  it("never renders zero, NaN, or missing values as prices", () => {
    expect(formatPrice(0)).toBe("Price unavailable");
    expect(formatPrice(Number.NaN)).toBe("Price unavailable");
    expect(formatPrice(undefined)).toBe("Price unavailable");
  });
  it("accepts only finite positive values", () => {
    expect(validPrice(1)).toBe(true);
    expect(validPrice(-1)).toBe(false);
  });
  it("validates discounts against price and MRP", () => {
    expect(validDiscount(800, 1000, 20)).toBe(20);
    expect(validDiscount(1000, 800, 20)).toBeNull();
    expect(validDiscount(0, 1000, 100)).toBeNull();
  });
});
