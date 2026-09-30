import { absoluteUrl } from "~/lib/seo/metadata";
import { getSeoSitemapMeta } from "~/lib/api/seo";
import { sitemapIndexXml, xmlResponse } from "~/lib/seo/sitemap";

const PRODUCT_PAGE_SIZE = 5000;

export async function loader({ request }: { request: Request }) {
  const today = new Date().toISOString().slice(0, 10);
  const entries = [
    { loc: absoluteUrl("/sitemaps/static.xml"), lastmod: today },
    { loc: absoluteUrl("/sitemaps/categories.xml"), lastmod: today },
  ];

  try {
    const meta = await getSeoSitemapMeta(PRODUCT_PAGE_SIZE, request.signal);
    const pages = Math.max(0, meta.pages);
    for (let page = 1; page <= pages; page += 1) {
      entries.push({
        loc: absoluteUrl(`/sitemaps/products/${page}.xml`),
        lastmod: today,
      });
    }
  } catch {
    // Product sitemap pages omitted when API unavailable — static/categories still emitted.
  }

  return xmlResponse(sitemapIndexXml(entries), 1800);
}
