/** XML sitemap builders (SEO V2). */

import { absoluteUrl, canonicalizePath } from "~/lib/seo/metadata";
import { productSlug } from "~/lib/seo/slug";

export const SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9";

export function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function formatSitemapLastmod(value: string | Date | null | undefined): string | null {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString().slice(0, 10);
}

export function urlsetXml(entries: Array<{ loc: string; lastmod?: string | null }>): string {
  const body = entries
    .map((entry) => {
      const loc = escapeXml(entry.loc);
      const lastmod = entry.lastmod ? formatSitemapLastmod(entry.lastmod) : null;
      return lastmod
        ? `<url><loc>${loc}</loc><lastmod>${lastmod}</lastmod></url>`
        : `<url><loc>${loc}</loc></url>`;
    })
    .join("");
  return `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="${SITEMAP_NS}">${body}</urlset>`;
}

export function sitemapIndexXml(entries: Array<{ loc: string; lastmod?: string | null }>): string {
  const body = entries
    .map((entry) => {
      const loc = escapeXml(entry.loc);
      const lastmod = entry.lastmod ? formatSitemapLastmod(entry.lastmod) : null;
      return lastmod
        ? `<sitemap><loc>${loc}</loc><lastmod>${lastmod}</lastmod></sitemap>`
        : `<sitemap><loc>${loc}</loc></sitemap>`;
    })
    .join("");
  return `<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="${SITEMAP_NS}">${body}</sitemapindex>`;
}

export function productSitemapLoc(productId: string, title: string): string {
  const path = canonicalizePath(`/products/${productId}/${productSlug(title)}`);
  return absoluteUrl(path);
}

export function xmlResponse(xml: string, maxAgeSeconds = 3600): Response {
  return new Response(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": `public, max-age=${maxAgeSeconds}`,
    },
  });
}
