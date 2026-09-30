import { describe, expect, it } from "vitest";
import { buildDisplayTitle } from "./display-title";

describe("buildDisplayTitle", () => {
  it("shortens noisy smartphone titles and keeps memory line", () => {
    const parts = buildDisplayTitle({
      title: "Samsung Galaxy S24 5G AI Smartphone 8GB RAM 256GB Storage Marble Gray",
      brand: "Samsung",
      category: "smartphone",
      specs: { ram: "8 GB", storage: "256 GB" },
    });
    expect(parts.title.toLowerCase()).toContain("samsung");
    expect(parts.title.length).toBeLessThan(70);
    expect(parts.subtitle).toMatch(/8 GB/);
    expect(parts.subtitle).toMatch(/256 GB/);
  });

  it("does not invent model names when data is thin", () => {
    const parts = buildDisplayTitle({
      title: "Unknown Device Special Edition Bundle Pack",
      brand: null,
      category: "laptop",
      specs: {},
    });
    expect(parts.title).toContain("Unknown Device");
    expect(parts.title).not.toMatch(/Galaxy|Invented/i);
  });
});
