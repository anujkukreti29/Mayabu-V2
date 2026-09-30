import { describe, expect, it } from "vitest";
import { parseTargetPriceInput } from "~/components/product/watch-price-control";

describe("parseTargetPriceInput", () => {
  it("accepts plain and formatted INR amounts", () => {
    expect(parseTargetPriceInput("49999")).toEqual({ ok: true, value: 49999 });
    expect(parseTargetPriceInput("₹49,999")).toEqual({ ok: true, value: 49999 });
  });

  it("rejects empty, non-positive, and oversized values", () => {
    expect(parseTargetPriceInput("").ok).toBe(false);
    expect(parseTargetPriceInput("0").ok).toBe(false);
    expect(parseTargetPriceInput("-100").ok).toBe(false);
    expect(parseTargetPriceInput("999999999").ok).toBe(false);
  });
});
