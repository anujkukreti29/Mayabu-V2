import type { HomepageProduct } from "~/lib/api/schemas";
import { categoryDisplayName } from "~/lib/search/categories";
import { homeCategories } from "~/lib/content/homepage";
import { CATEGORY_ROUTE_BY_SLUG } from "~/lib/category/landing-registry";
import { routes } from "~/lib/navigation/routes";

export type CategoryMosaicTile = {
  id: string;
  categorySlug: string;
  categoryLabel: string;
  href: string;
  product: HomepageProduct;
};

export type ProductGridTheme =
  | "recently_verified"
  | "biggest_discounts"
  | "lowest_since_tracking"
  | "popular"
  | "trending"
  | "price_drops";

export type HomeCarouselSlide =
  | {
      kind: "category_mosaic";
      id: string;
      title: string;
      description: string;
      tiles: CategoryMosaicTile[];
    }
  | {
      kind: "product_grid";
      id: string;
      title: string;
      description: string;
      theme: ProductGridTheme;
      badge: string;
      products: HomepageProduct[];
    }
  | {
      kind: "featured_product";
      id: string;
      title: string;
      description: string;
      product: HomepageProduct;
      badge: string;
      highlight?: string | null;
    };

/** Prefer visually distinct category shapes for the Explore mosaic. */
const MOSAIC_CATEGORY_PRIORITY = [
  "smartphone",
  "television",
  "laptop",
  "camera",
  "washing_machine",
  "tws",
  "refrigerator",
  "headphones",
] as const;

function categoryHref(slug: string): string {
  const fromHome = homeCategories.find((item) => item.slug === slug);
  if (fromHome) return fromHome.href;
  return (
    CATEGORY_ROUTE_BY_SLUG[slug as keyof typeof CATEGORY_ROUTE_BY_SLUG] ??
    `${routes.search}?category=${encodeURIComponent(slug)}`
  );
}

function takeUnique(
  products: readonly HomepageProduct[],
  used: Set<string>,
  count: number,
): HomepageProduct[] {
  const out: HomepageProduct[] = [];
  for (const product of products) {
    if (!product?.id || used.has(product.id)) continue;
    if (!product.image_url && out.length < count) {
      // Prefer imaged products but allow fill if inventory is thin.
    }
    used.add(product.id);
    out.push(product);
    if (out.length >= count) break;
  }
  return out;
}

function preferWithImages(products: readonly HomepageProduct[]): HomepageProduct[] {
  const withImage = products.filter((p) => Boolean(p.image_url));
  const without = products.filter((p) => !p.image_url);
  return [...withImage, ...without];
}

function buildCategoryMosaic(pool: readonly HomepageProduct[]): Extract<
  HomeCarouselSlide,
  { kind: "category_mosaic" }
> | null {
  const byCategory = new Map<string, HomepageProduct[]>();
  for (const product of preferWithImages(pool)) {
    const slug = (product.category || "").toLowerCase();
    if (!slug) continue;
    const bucket = byCategory.get(slug) ?? [];
    bucket.push(product);
    byCategory.set(slug, bucket);
  }

  const mosaicUsed = new Set<string>();
  const tiles: CategoryMosaicTile[] = [];

  const tryAdd = (slug: string) => {
    if (tiles.length >= 4) return;
    if (tiles.some((tile) => tile.categorySlug === slug)) return;
    const candidates = byCategory.get(slug) ?? [];
    const product =
      candidates.find((item) => !mosaicUsed.has(item.id) && item.image_url) ??
      candidates.find((item) => !mosaicUsed.has(item.id));
    if (!product) return;
    mosaicUsed.add(product.id);
    tiles.push({
      id: `cat-${slug}`,
      categorySlug: slug,
      categoryLabel: categoryDisplayName(slug) || slug,
      href: categoryHref(slug),
      product,
    });
  };

  for (const slug of MOSAIC_CATEGORY_PRIORITY) tryAdd(slug);
  if (tiles.length < 4) {
    for (const slug of byCategory.keys()) tryAdd(slug);
  }

  if (tiles.length < 4) return null;

  return {
    kind: "category_mosaic",
    id: "explore-mayabu",
    title: "Products worth comparing",
    description: "Four live Mayabu picks across categories — real prices, real listings.",
    tiles,
  };
}

function buildProductGrid(
  id: string,
  title: string,
  description: string,
  theme: ProductGridTheme,
  badge: string,
  source: readonly HomepageProduct[],
  used: Set<string>,
): HomeCarouselSlide | null {
  const products = takeUnique(preferWithImages(source), used, 4);
  if (products.length < 4) {
    for (const product of products) used.delete(product.id);
    return null;
  }
  return {
    kind: "product_grid",
    id,
    title,
    description,
    theme,
    badge,
    products,
  };
}

function buildFeatured(
  product: HomepageProduct | undefined,
  used: Set<string>,
  id: string,
  badge: string,
  description: string,
  highlight?: string | null,
): HomeCarouselSlide | null {
  if (!product || used.has(product.id)) return null;
  used.add(product.id);
  return {
    kind: "featured_product",
    id,
    title: product.title,
    description,
    product,
    badge,
    highlight: highlight ?? null,
  };
}

/**
 * Deterministic 5–6 slide homepage carousel from discovery payload.
 * No Math.random — SSR and client hydrate identically.
 */
export function buildHomeCarouselSlides(input: {
  featured: HomepageProduct[];
  trending: HomepageProduct[];
  popular: HomepageProduct[];
  priceDrops: HomepageProduct[];
  discounts: HomepageProduct[];
  lowest: HomepageProduct[];
  recentlyChecked: HomepageProduct[];
}): HomeCarouselSlide[] {
  const used = new Set<string>();
  const slides: HomeCarouselSlide[] = [];
  const pool = preferWithImages([
    ...input.featured,
    ...input.recentlyChecked,
    ...input.discounts,
    ...input.lowest,
    ...input.popular,
    ...input.trending,
    ...input.priceDrops,
  ]);

  const mosaic = buildCategoryMosaic(pool);
  if (mosaic) {
    slides.push(mosaic);
    for (const tile of mosaic.tiles) used.add(tile.product.id);
  }

  const recentSource =
    input.recentlyChecked.length >= 4
      ? input.recentlyChecked
      : [
          ...input.recentlyChecked,
          ...input.featured,
          ...input.popular,
          ...input.trending,
        ];
  const recentGrid = buildProductGrid(
    "grid-recent",
    "Freshly checked on Mayabu",
    "Products with the most recent verified price observations.",
    "recently_verified",
    "Recently verified",
    recentSource,
    used,
  );
  if (recentGrid) slides.push(recentGrid);

  const discountGrid = buildProductGrid(
    "grid-discounts",
    "Biggest discounts",
    "Validated MRP above the current public offer.",
    "biggest_discounts",
    "Discount",
    input.discounts,
    used,
  );
  if (discountGrid) slides.push(discountGrid);

  const lowestGrid = buildProductGrid(
    "grid-lowest",
    "Lowest since tracking",
    "At Mayabu’s lowest recorded price for each product.",
    "lowest_since_tracking",
    "Lowest since tracking",
    input.lowest,
    used,
  );
  if (lowestGrid) slides.push(lowestGrid);

  // Featured slide — prefer price drop / multi-store / popular / featured.
  const featuredCandidate =
    input.priceDrops.find((p) => !used.has(p.id)) ??
    input.featured.find((p) => !used.has(p.id) && (p.platform_count ?? 0) >= 2) ??
    input.popular.find((p) => !used.has(p.id)) ??
    input.featured.find((p) => !used.has(p.id)) ??
    input.recentlyChecked.find((p) => !used.has(p.id));

  const featured = buildFeatured(
    featuredCandidate,
    used,
    "featured-product",
    featuredCandidate?.drop_percent != null
      ? "Price dropped"
      : (featuredCandidate?.platform_count ?? 0) >= 2
        ? "Compare stores"
        : "Featured",
    featuredCandidate?.drop_percent != null
      ? "Current best price below a recent Mayabu observation."
      : "A live product from Mayabu’s catalog.",
    featuredCandidate?.drop_percent != null
      ? `Down ${featuredCandidate.drop_percent}% recently`
      : null,
  );
  if (featured) slides.push(featured);

  // Optional 6th: trending or popular grid if quality is high.
  if (slides.length < 6) {
    const activityGrid =
      buildProductGrid(
        "grid-trending",
        "Trending on Mayabu",
        "Rising engagement on Mayabu right now.",
        "trending",
        "Trending",
        input.trending,
        used,
      ) ??
      buildProductGrid(
        "grid-popular",
        "Popular on Mayabu",
        "Higher engagement over the last 7 days.",
        "popular",
        "Popular",
        input.popular,
        used,
      );
    if (activityGrid) slides.push(activityGrid);
  }

  // Ensure ≥5 slides using additional recent/featured grids or featured products.
  if (slides.length < 5) {
    const fillerGrid = buildProductGrid(
      "grid-fill-recent",
      "More live products",
      "Additional products from Mayabu’s catalog.",
      "recently_verified",
      "On Mayabu",
      [...input.featured, ...input.recentlyChecked, ...input.discounts],
      used,
    );
    if (fillerGrid) slides.push(fillerGrid);
  }

  while (slides.length < 5) {
    const next =
      input.featured.find((p) => !used.has(p.id)) ??
      input.recentlyChecked.find((p) => !used.has(p.id)) ??
      input.discounts.find((p) => !used.has(p.id)) ??
      input.lowest.find((p) => !used.has(p.id)) ??
      input.priceDrops.find((p) => !used.has(p.id)) ??
      input.popular.find((p) => !used.has(p.id)) ??
      input.trending.find((p) => !used.has(p.id)) ??
      pool.find((p) => !used.has(p.id));
    const slide = buildFeatured(
      next,
      used,
      `featured-fill-${slides.length}`,
      "On Mayabu",
      "A live product from Mayabu’s catalog.",
    );
    if (!slide) break;
    slides.push(slide);
  }

  return slides.slice(0, 6);
}

/** Product IDs used in carousel for cross-section rail dedupe. */
export function carouselProductIds(slides: readonly HomeCarouselSlide[]): Set<string> {
  const ids = new Set<string>();
  for (const slide of slides) {
    if (slide.kind === "category_mosaic") {
      for (const tile of slide.tiles) ids.add(tile.product.id);
    } else if (slide.kind === "product_grid") {
      for (const product of slide.products) ids.add(product.id);
    } else {
      ids.add(slide.product.id);
    }
  }
  return ids;
}

export function dedupeRailProducts(
  products: readonly HomepageProduct[],
  exclude: Set<string>,
  limit = 5,
): HomepageProduct[] {
  const primary = products.filter((p) => p.id && !exclude.has(p.id));
  if (primary.length >= Math.min(3, limit)) return primary.slice(0, limit);
  // Allow limited re-use when supply is thin.
  return products.filter((p) => Boolean(p.id)).slice(0, limit);
}
