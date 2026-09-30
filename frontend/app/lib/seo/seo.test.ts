import { describe, expect, it } from "vitest";
import { absoluteUrl, canonicalizePath, pageMeta, sanitizeMetaText } from "~/lib/seo/metadata";
import { productSlug } from "~/lib/seo/slug";
import { organizationJsonLd, websiteJsonLd } from "~/lib/seo/site-jsonld";
import { breadcrumbJsonLd, productJsonLd } from "~/lib/seo/structured-data";
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
  similar_products: [],
  similar_product_count: 0,
  images: [],
  image_count: 0,
};

const cameraDetail: ProductDetail = {
  ...detail,
  product: {
    ...detail.product,
    id: "cam-1",
    title: "Sony Alpha A7 IV Body Only",
    category: "camera",
    brand: "Sony",
  },
  offers: [
    {
      id: "o1",
      platform: "croma",
      listing_id: null,
      native_id: null,
      url: "https://www.croma.com/x",
      title: "Sony",
      image_url: null,
      price: 189990,
      mrp: null,
      effective_price: 189990,
      discount_percent: null,
      currency: "INR",
      stock_status: null,
      rating: null,
      review_count: null,
      last_checked_at: null,
      last_verified_at: null,
      verification_status: null,
      verification_source: null,
      next_allowed_verification_at: null,
      verification_failures: 0,
    },
  ],
  offer_count: 1,
};

describe("SEO utilities", () => {
  it("generates stable safe slugs", () =>
    expect(productSlug("ASUS Vivobook 15 16GB / 512GB")).toBe("asus-vivobook-15-16gb-512gb"));
  it("sanitizes metadata text", () =>
    expect(sanitizeMetaText("<script>bad</script>\nname")).not.toContain("<"));
  it("creates absolute canonical URLs", () => expect(absoluteUrl("/about")).toContain("/about"));
  it("omits offers when no valid price exists", () =>
    expect(productJsonLd(detail)).not.toHaveProperty("offers"));
  it("uses Offer for a single public price and AggregateOffer for multiple", () => {
    const json = productJsonLd(cameraDetail);
    expect(json.offers).toMatchObject({
      "@type": "Offer",
      priceCurrency: "INR",
      price: "189990",
    });
  });
  it("builds category-aware breadcrumbs to canonical landing routes", () => {
    const crumbs = breadcrumbJsonLd(cameraDetail.product);
    expect(crumbs.itemListElement[1]).toMatchObject({
      name: "Cameras",
      item: expect.stringContaining("/cameras"),
    });
  });
  it("exposes truthful Organization and WebSite JSON-LD with SearchAction", () => {
    expect(organizationJsonLd()["@type"]).toBe("Organization");
    expect(websiteJsonLd()["@type"]).toBe("WebSite");
    expect(String(websiteJsonLd().description)).not.toMatch(/only laptops/i);
    expect(websiteJsonLd().potentialAction).toMatchObject({
      "@type": "SearchAction",
    });
  });
  it("canonicalizes paths without trailing slash or query noise", () => {
    expect(canonicalizePath("/laptops/")).toBe("/laptops");
    expect(canonicalizePath("/laptops?utm=1")).toBe("/laptops");
    expect(absoluteUrl("/laptops/")).toMatch(/\/laptops$/);
  });
  it("emits twitter tags with page metadata", () => {
    const tags = pageMeta({
      title: "Compare Laptop Prices & Specifications | Mayabu",
      description: "Compare laptop prices on Mayabu.",
      path: "/laptops",
    });
    expect(tags.some((tag) => "name" in tag && tag.name === "twitter:title")).toBe(true);
    expect(tags.some((tag) => "name" in tag && tag.name === "twitter:image")).toBe(true);
  });
});
