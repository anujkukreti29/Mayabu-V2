import type { LoaderFunctionArgs } from "react-router";
import { getSeoSitemapProducts } from "~/lib/api/seo";
import { productSitemapLoc, urlsetXml, xmlResponse } from "~/lib/seo/sitemap";

const PRODUCT_PAGE_SIZE = 5000;

export async function loader({ params, request }: LoaderFunctionArgs) {
  const raw = params.page ?? "1";
  const page = Math.max(1, Number.parseInt(raw.replace(/\.xml$/i, ""), 10) || 1);
  try {
    const payload = await getSeoSitemapProducts(page, PRODUCT_PAGE_SIZE, request.signal);
    const entries = payload.items.map((item) => ({
      loc: productSitemapLoc(item.product_id, item.title),
      lastmod: item.lastmod ?? null,
    }));
    return xmlResponse(urlsetXml(entries), 1800);
  } catch {
    throw new Response("Sitemap products temporarily unavailable", { status: 503 });
  }
}
