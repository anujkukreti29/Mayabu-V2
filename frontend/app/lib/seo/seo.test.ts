import { describe, expect, it } from "vitest";
import { absoluteUrl, sanitizeMetaText } from "~/lib/seo/metadata";
import { productSlug } from "~/lib/seo/slug";
import { productJsonLd } from "~/lib/seo/structured-data";
import type { ProductDetail } from "~/lib/api/schemas";

const detail: ProductDetail = {
  product: {
    id: "p1",
    title: "ASUS Vivobook 15 16GB / 512GB",
    brand: "ASUS",
    category: "laptop",
    specs: { model_codes: ["X1504"] },
    best_price: 54990,
    best_platform: "Amazon India",
    platform_count: 2,
    image_url: null,
    last_seen_at: null,
    match_group: "exact_match",
    rank_score: null,
    variant_group_id: null,
  },
  offers: [],
  offer_count: 0,
  similar_variants: [],
  similar_variant_count: 0,
};

describe("SEO utilities", () => {
  it("generates stable safe slugs", () =>
    expect(productSlug("ASUS Vivobook 15 16GB / 512GB")).toBe("asus-vivobook-15-16gb-512gb"));
  it("sanitizes metadata text", () =>
    expect(sanitizeMetaText("<script>bad</script>\nname")).not.toContain("<"));
  it("creates absolute canonical URLs", () => expect(absoluteUrl("/about")).toContain("/about"));
  it("omits offers when no valid price exists", () =>
    expect(productJsonLd(detail)).not.toHaveProperty("offers"));
});
