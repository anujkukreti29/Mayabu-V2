/** Indexability matrix for Mayabu public routes (SEO V2). */

import { CATEGORY_ROUTE_BY_SLUG } from "~/lib/category/landing-registry";
import { PUBLIC_CATEGORY_SLUGS } from "~/lib/search/categories";
import { routes } from "~/lib/navigation/routes";
import { canonicalizePath } from "~/lib/seo/metadata";

export type IndexDecision = "index" | "noindex";

const STATIC_INDEXABLE = new Set<string>([
  routes.home,
  routes.platforms,
  routes.howItWorks,
  routes.about,
  routes.contact,
  routes.privacy,
  routes.terms,
  routes.disclaimer,
]);

const CATEGORY_INDEXABLE = new Set<string>(
  PUBLIC_CATEGORY_SLUGS.map((slug) => CATEGORY_ROUTE_BY_SLUG[slug]),
);

const NOINDEX_PREFIXES = [
  "/search",
  "/compare",
  "/sign-in",
  "/login",
  "/signup",
  "/check-email",
  "/account",
  "/wishlist",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/admin",
  "/assistant",
  "/tracker",
  "/deals",
  "/api",
] as const;

export function staticSitemapPaths(): string[] {
  return [...STATIC_INDEXABLE];
}

export function categorySitemapPaths(): string[] {
  return [...CATEGORY_INDEXABLE];
}

export function isProductPath(pathname: string): boolean {
  return canonicalizePath(pathname).startsWith("/products/");
}

export function indexDecisionForPath(pathname: string): IndexDecision {
  const path = canonicalizePath(pathname);
  if (STATIC_INDEXABLE.has(path) || CATEGORY_INDEXABLE.has(path)) return "index";
  if (isProductPath(path)) return "index"; // eligibility enforced by PDP + sitemap feed
  for (const prefix of NOINDEX_PREFIXES) {
    if (path === prefix || path.startsWith(`${prefix}/`) || path.startsWith(`${prefix}?`)) {
      return "noindex";
    }
  }
  return "noindex";
}

export function shouldAppearInSitemap(pathname: string): boolean {
  const path = canonicalizePath(pathname);
  if (isProductPath(path)) return true; // only when selected by eligible feed
  return STATIC_INDEXABLE.has(path) || CATEGORY_INDEXABLE.has(path);
}
