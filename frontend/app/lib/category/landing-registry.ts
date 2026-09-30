/** Frontend category landing registry — routes, copy, discovery facets. */

import {
  categoryDisplayName,
  categoryShortLabel,
  isPublicCategory,
  PUBLIC_CATEGORY_SLUGS,
  type PublicCategorySlug,
} from "~/lib/search/categories";

/** Canonical public plural paths → backend category slug. */
export const CATEGORY_ROUTE_BY_SLUG: Record<PublicCategorySlug, string> = {
  laptop: "/laptops",
  smartphone: "/smartphones",
  television: "/televisions",
  refrigerator: "/refrigerators",
  washing_machine: "/washing-machines",
  tws: "/tws",
  headphones: "/headphones",
  camera: "/cameras",
};

const SLUG_BY_ROUTE: Record<string, PublicCategorySlug> = Object.fromEntries(
  (PUBLIC_CATEGORY_SLUGS as readonly PublicCategorySlug[]).map((slug) => [
    CATEGORY_ROUTE_BY_SLUG[slug],
    slug,
  ]),
);

/** Legacy path kept as redirect target only. */
export const LEGACY_CATEGORY_REDIRECTS: Record<string, string> = {
  "/mobile-phones": "/smartphones",
};

export function categoryLandingPath(slug: string | null | undefined): string | null {
  if (!slug || !isPublicCategory(slug)) return null;
  return CATEGORY_ROUTE_BY_SLUG[slug];
}

export function categorySlugFromPath(pathname: string): PublicCategorySlug | null {
  const normalized =
    pathname.endsWith("/") && pathname.length > 1 ? pathname.slice(0, -1) : pathname;
  return SLUG_BY_ROUTE[normalized] ?? null;
}

export interface CategoryLandingConfig {
  slug: PublicCategorySlug;
  route: string;
  displayName: string;
  shortName: string;
  heading: string;
  description: string;
  searchPlaceholder: string;
  browseQuery: string;
  primaryFacets: readonly string[];
  relatedSlugs: readonly PublicCategorySlug[];
  title: string;
  metaDescription: string;
}

const LANDING: Record<
  PublicCategorySlug,
  Omit<CategoryLandingConfig, "slug" | "route" | "displayName" | "shortName">
> = {
  laptop: {
    heading: "Laptops",
    description:
      "Compare processors, RAM, storage, graphics and current store prices across supported retailers.",
    searchPlaceholder: "Search laptops, processors, models…",
    browseQuery: "laptop",
    primaryFacets: ["brand", "ram_gb", "storage_gb", "cpu_series", "gpu"],
    relatedSlugs: ["smartphone", "headphones", "tws"],
    title: "Compare Laptop Prices & Specifications | Mayabu",
    metaDescription:
      "Compare laptop prices, processors, RAM, storage and current retailer offers on Mayabu.",
  },
  smartphone: {
    heading: "Smartphones",
    description:
      "Compare storage, RAM, chipsets and retailer prices for the exact phone variants that matter.",
    searchPlaceholder: "Search phones, brands, storage variants…",
    browseQuery: "smartphone",
    primaryFacets: ["brand", "ram_gb", "storage_gb", "network_generation"],
    relatedSlugs: ["laptop", "headphones", "tws"],
    title: "Compare Smartphone Prices & Specifications | Mayabu",
    metaDescription:
      "Compare smartphone prices, storage variants and current retailer offers on Mayabu.",
  },
  television: {
    heading: "TVs",
    description:
      "Compare screen sizes, panel types, refresh rates and retailer prices before you buy.",
    searchPlaceholder: "Search TVs, sizes, models…",
    browseQuery: "television",
    primaryFacets: ["brand", "screen_size_inch", "panel_type", "resolution", "refresh_rate_hz"],
    relatedSlugs: ["headphones", "tws", "laptop"],
    title: "Compare TV Prices & Specifications | Mayabu",
    metaDescription:
      "Compare TV prices, screen sizes, panel types and current retailer offers on Mayabu.",
  },
  refrigerator: {
    heading: "Refrigerators",
    description: "Compare capacity, door type, frost systems and current store prices.",
    searchPlaceholder: "Search refrigerators, capacity, brands…",
    browseQuery: "refrigerator",
    primaryFacets: ["brand", "capacity_l", "door_type", "frost_type", "star_rating"],
    relatedSlugs: ["washing_machine", "television", "laptop"],
    title: "Compare Refrigerator Prices & Specifications | Mayabu",
    metaDescription:
      "Compare refrigerator prices, capacity and features across supported retailers on Mayabu.",
  },
  washing_machine: {
    heading: "Washing Machines",
    description: "Compare capacity, load type, automation and current retailer prices.",
    searchPlaceholder: "Search washing machines, capacity, brands…",
    browseQuery: "washing machine",
    primaryFacets: ["brand", "capacity_kg", "load_type", "automation_type", "star_rating"],
    relatedSlugs: ["refrigerator", "television", "headphones"],
    title: "Compare Washing Machine Prices & Specifications | Mayabu",
    metaDescription:
      "Compare washing machine prices, capacity and load types across supported retailers on Mayabu.",
  },
  tws: {
    heading: "TWS & Earbuds",
    description: "Compare ANC, connectivity and current store prices for true wireless earbuds.",
    searchPlaceholder: "Search earbuds, brands, ANC…",
    browseQuery: "tws earbuds",
    primaryFacets: ["brand", "anc", "connectivity", "codec"],
    relatedSlugs: ["headphones", "smartphone", "laptop"],
    title: "Compare TWS & Earbuds Prices & Specifications | Mayabu",
    metaDescription:
      "Compare TWS and earbud prices, ANC and connectivity across supported retailers on Mayabu.",
  },
  headphones: {
    heading: "Headphones",
    description: "Compare form factor, connectivity, ANC and current retailer prices.",
    searchPlaceholder: "Search headphones, brands, form factor…",
    browseQuery: "headphones",
    primaryFacets: ["brand", "form_factor", "connectivity", "anc"],
    relatedSlugs: ["tws", "smartphone", "laptop"],
    title: "Compare Headphones Prices & Specifications | Mayabu",
    metaDescription:
      "Compare headphone prices, form factors and connectivity across supported retailers on Mayabu.",
  },
  camera: {
    heading: "Cameras",
    description: "Compare body and kit variants, sensors and current store prices.",
    searchPlaceholder: "Search cameras, models, body or kit…",
    browseQuery: "camera",
    primaryFacets: ["brand", "camera_type", "sensor_format", "mount", "body_only"],
    relatedSlugs: ["laptop", "smartphone", "headphones"],
    title: "Compare Camera Prices & Specifications | Mayabu",
    metaDescription:
      "Compare camera prices, body and kit variants across supported retailers on Mayabu.",
  },
};

export function getCategoryLandingConfig(slug: PublicCategorySlug): CategoryLandingConfig {
  const base = LANDING[slug];
  return {
    slug,
    route: CATEGORY_ROUTE_BY_SLUG[slug],
    displayName: categoryDisplayName(slug),
    shortName: categoryShortLabel(slug),
    ...base,
  };
}

export function allCategoryLandingConfigs(): CategoryLandingConfig[] {
  return PUBLIC_CATEGORY_SLUGS.map((slug) => getCategoryLandingConfig(slug));
}
