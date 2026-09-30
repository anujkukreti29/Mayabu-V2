import { z } from "zod";
import { apiRequest } from "~/lib/api/client";

const sitemapMetaSchema = z.object({
  contract_version: z.string().optional(),
  total: z.number().int().nonnegative(),
  page_size: z.number().int().positive(),
  pages: z.number().int().nonnegative(),
  max_urls_per_sitemap: z.number().int().positive().optional(),
});

const sitemapProductsSchema = z.object({
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
  count: z.number().int().nonnegative(),
  items: z.array(
    z.object({
      product_id: z.string(),
      title: z.string(),
      lastmod: z.string().nullable().optional(),
    }),
  ),
  contract_version: z.string().optional(),
});

export type SeoSitemapMeta = z.infer<typeof sitemapMetaSchema>;
export type SeoSitemapProducts = z.infer<typeof sitemapProductsSchema>;

export function getSeoSitemapMeta(pageSize = 5000, signal?: AbortSignal): Promise<SeoSitemapMeta> {
  return apiRequest(`/api/seo/sitemap/meta?page_size=${pageSize}`, sitemapMetaSchema, { signal });
}

export function getSeoSitemapProducts(
  page: number,
  pageSize = 5000,
  signal?: AbortSignal,
): Promise<SeoSitemapProducts> {
  return apiRequest(
    `/api/seo/sitemap/products?page=${page}&page_size=${pageSize}`,
    sitemapProductsSchema,
    { signal },
  );
}
