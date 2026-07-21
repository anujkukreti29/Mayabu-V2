import { describe, expect, it } from "vitest";
import { safeRetailerUrl } from "~/lib/security/external-url";

describe("retailer URL validation", () => {
  it("allows approved HTTPS retailer URLs", () =>
    expect(safeRetailerUrl("https://www.amazon.in/dp/example")).toContain("amazon.in"));
  it("rejects HTTP and unknown hosts", () => {
    expect(safeRetailerUrl("http://amazon.in/item")).toBeNull();
    expect(safeRetailerUrl("https://evil.example/item")).toBeNull();
    expect(safeRetailerUrl("javascript:alert(1)")).toBeNull();
  });
});
