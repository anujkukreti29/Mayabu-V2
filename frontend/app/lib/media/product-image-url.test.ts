import { describe, expect, it } from "vitest";
import { normalizeProductImageUrl } from "~/lib/media/product-image-url";

describe("normalizeProductImageUrl", () => {
  it("upgrades protocol-relative URLs to https", () => {
    expect(normalizeProductImageUrl("//cdn.example.com/p.jpg")).toBe(
      "https://cdn.example.com/p.jpg",
    );
  });

  it("rejects unsafe or empty values", () => {
    expect(normalizeProductImageUrl("")).toBeNull();
    expect(normalizeProductImageUrl("javascript:alert(1)")).toBeNull();
    expect(normalizeProductImageUrl("data:image/gif;base64,xxx")).toBeNull();
    expect(normalizeProductImageUrl("ftp://cdn.example.com/a.jpg")).toBeNull();
  });

  it("keeps https product URLs", () => {
    expect(normalizeProductImageUrl("https://m.media-amazon.com/images/I/abc.jpg")).toBe(
      "https://m.media-amazon.com/images/I/abc.jpg",
    );
  });
});
