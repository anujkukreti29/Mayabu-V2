import { describe, expect, it } from "vitest";
import {
  categorySitemapPaths,
  indexDecisionForPath,
  staticSitemapPaths,
} from "~/lib/seo/indexability";
import {
  escapeXml,
  formatSitemapLastmod,
  productSitemapLoc,
  sitemapIndexXml,
  urlsetXml,
} from "~/lib/seo/sitemap";

describe("SEO indexability", () => {
  it("indexes homepage, categories, and products; noindexes search/compare/auth", () => {
    expect(indexDecisionForPath("/")).toBe("index");
    expect(indexDecisionForPath("/laptops")).toBe("index");
    expect(indexDecisionForPath("/cameras")).toBe("index");
    expect(indexDecisionForPath("/products/abc/slug")).toBe("index");
    expect(indexDecisionForPath("/search?q=asus")).toBe("noindex");
    expect(indexDecisionForPath("/compare?ids=a,b")).toBe("noindex");
    expect(indexDecisionForPath("/sign-in")).toBe("noindex");
    expect(indexDecisionForPath("/wishlist")).toBe("noindex");
    expect(indexDecisionForPath("/account")).toBe("noindex");
  });

  it("lists eight category sitemap paths and static pages without search", () => {
    expect(categorySitemapPaths()).toHaveLength(8);
    expect(staticSitemapPaths()).toContain("/");
    expect(staticSitemapPaths().join(" ")).not.toMatch(/search|compare|sign-in|wishlist/);
  });
});

describe("sitemap XML helpers", () => {
  it("escapes XML entities", () => {
    expect(escapeXml(`A&B <C> "D"`)).toBe("A&amp;B &lt;C&gt; &quot;D&quot;");
  });

  it("formats lastmod as YYYY-MM-DD", () => {
    expect(formatSitemapLastmod("2026-09-20T12:00:00Z")).toBe("2026-09-20");
  });

  it("builds valid urlset and sitemap index documents", () => {
    const urlset = urlsetXml([{ loc: "https://example.com/laptops", lastmod: "2026-09-20" }]);
    expect(urlset).toContain("<urlset");
    expect(urlset).toContain("<loc>https://example.com/laptops</loc>");
    const index = sitemapIndexXml([{ loc: "https://example.com/sitemaps/static.xml" }]);
    expect(index).toContain("<sitemapindex");
    expect(productSitemapLoc("p1", "ASUS Vivobook 15")).toMatch(
      /\/products\/p1\/asus-vivobook-15$/,
    );
  });
});
