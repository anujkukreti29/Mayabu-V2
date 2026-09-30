import { describe, expect, it } from "vitest";
import { safeRetailerUrl } from "~/lib/security/external-url";

describe("retailer URL validation", () => {
  it("allows approved HTTPS retailer URLs", () => {
    expect(safeRetailerUrl("https://www.amazon.in/dp/example")).toContain("amazon.in");
    expect(safeRetailerUrl("https://www.vijaysales.com/p/1/x")).toContain("vijaysales.com");
    expect(safeRetailerUrl("https://www.jiomart.com/p/electronics/x/1")).toContain("jiomart.com");
    expect(safeRetailerUrl("https://www.poorvika.com/foo/p")).toContain("poorvika.com");
    expect(safeRetailerUrl("https://www.bajajelectronics.com/foo")).toContain(
      "bajajelectronics.com",
    );
  });

  it("rejects HTTP, unknown hosts, and lookalikes", () => {
    expect(safeRetailerUrl("http://amazon.in/item")).toBeNull();
    expect(safeRetailerUrl("https://evil.example/item")).toBeNull();
    expect(safeRetailerUrl("https://vijaysales.com.evil.example/p/1")).toBeNull();
    expect(safeRetailerUrl("https://fake-jiomart.com/p/1")).toBeNull();
    expect(safeRetailerUrl("https://www.amazon.in.evil.example/dp/x")).toBeNull();
    expect(safeRetailerUrl("javascript:alert(1)")).toBeNull();
  });
});
