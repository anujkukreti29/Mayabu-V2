import { data, Link, useLoaderData } from "react-router";
import type { LoaderFunctionArgs, MetaFunction } from "react-router";
import {
  buildHomeCarouselSlides,
  carouselProductIds,
  dedupeRailProducts,
} from "~/components/home/carousel-types";
import type { HomeCarouselSlide } from "~/components/home/carousel-types";
import { ExploreCategoriesGrid } from "~/components/home/explore-categories-grid";
import { HomeProductRail } from "~/components/home/home-product-rail";
import { PromoCarousel } from "~/components/home/promo-carousel";
import { SectionHeader, SectionShell } from "~/components/home/section-header";
import { SearchForm } from "~/components/search/search-form";
import { HomepageOpeningSkeleton } from "~/components/ui/skeleton";
import { getHomepageDiscovery } from "~/lib/api/homepage";
import type { HomepageDiscovery, HomepageProduct } from "~/lib/api/schemas";
import { homeCategories, homeHero } from "~/lib/content/homepage";
import { pageMeta } from "~/lib/seo/metadata";
import { jsonLdScript, organizationJsonLd, websiteJsonLd } from "~/lib/seo/site-jsonld";

export function HydrateFallback() {
  return <HomepageOpeningSkeleton />;
}

interface CategorySpotlight {
  slug: string;
  title: string;
  description?: string;
  products: HomepageProduct[];
}

interface HomeLoaderData {
  discovery: HomepageDiscovery;
  slides: HomeCarouselSlide[];
  recentlyVerified: HomepageProduct[];
  trending: HomepageProduct[];
  discounts: HomepageProduct[];
  lowest: HomepageProduct[];
  nearLow: HomepageProduct[];
  multiStore: HomepageProduct[];
  popular: HomepageProduct[];
  drops: HomepageProduct[];
  spotlights: CategorySpotlight[];
  categoryCounts: Record<string, number>;
}

const EMPTY_DISCOVERY: HomepageDiscovery = {
  trending: [],
  popular: [],
  biggest_discounts: [],
  lowest_since_tracking: [],
  near_tracked_low: [],
  price_drops: [],
  recently_checked: [],
  multi_store: [],
  explore_by_category: [],
  category_spotlights: [],
  featured: [],
  categories: [],
  stores: [],
  semantics: {},
};

export async function loader({ request }: LoaderFunctionArgs) {
  let discovery = EMPTY_DISCOVERY;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8_000);
    const onAbort = () => controller.abort();
    request.signal.addEventListener("abort", onAbort);
    try {
      discovery = await getHomepageDiscovery(8, controller.signal);
    } finally {
      clearTimeout(timer);
      request.signal.removeEventListener("abort", onAbort);
    }
  } catch (error) {
    console.error("[mayabu:homepage]", {
      message: error instanceof Error ? error.message : "discovery_failed",
    });
    discovery = EMPTY_DISCOVERY;
  }

  const slides = buildHomeCarouselSlides({
    featured: discovery.featured,
    trending: discovery.trending,
    popular: discovery.popular,
    priceDrops: discovery.price_drops,
    discounts: discovery.biggest_discounts,
    lowest: discovery.lowest_since_tracking,
    recentlyChecked: discovery.recently_checked,
  });

  const exclude = carouselProductIds(slides);
  const featuredIds = new Set(
    slides
      .filter((slide) => slide.kind === "featured_product")
      .map((slide) => (slide.kind === "featured_product" ? slide.product.id : "")),
  );
  const railExclude = new Set([...exclude, ...featuredIds]);

  const categoryCounts: Record<string, number> = {};
  for (const group of discovery.explore_by_category ?? []) {
    categoryCounts[group.slug] =
      typeof group.product_count === "number" && group.product_count > 0
        ? group.product_count
        : (group.products?.length ?? 0);
  }

  return data<HomeLoaderData>({
    discovery,
    slides,
    recentlyVerified: dedupeRailProducts(
      discovery.recently_checked.length > 0 ? discovery.recently_checked : discovery.featured,
      railExclude,
      8,
    ),
    trending: dedupeRailProducts(discovery.trending, railExclude, 6),
    lowest: dedupeRailProducts(discovery.lowest_since_tracking, railExclude, 6),
    nearLow: dedupeRailProducts(discovery.near_tracked_low ?? [], railExclude, 6),
    discounts: dedupeRailProducts(discovery.biggest_discounts, railExclude, 6),
    multiStore: dedupeRailProducts(discovery.multi_store ?? [], railExclude, 6),
    popular: dedupeRailProducts(discovery.popular, railExclude, 6),
    drops: dedupeRailProducts(discovery.price_drops, railExclude, 6),
    spotlights: discovery.category_spotlights ?? [],
    categoryCounts,
  });
}

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Mayabu — Compare Prices Across Stores & Platforms",
    description:
      "Search once and compare products, variants, and retailer offers across supported Indian stores. Mayabu helps you decide with clearer prices, specs, and freshness.",
    path: "/",
  });

function SpotlightSection({
  spotlight,
  tone,
}: {
  spotlight: CategorySpotlight;
  tone?: "band";
}) {
  const href = homeCategories.find((c) => c.slug === spotlight.slug)?.href;
  return (
    <SectionShell
      id={`spotlight-${spotlight.slug}`}
      labelledBy={`spotlight-${spotlight.slug}-title`}
      tone={tone}
    >
      <div className="page-container py-5 sm:py-6">
        <SectionHeader
          id={`spotlight-${spotlight.slug}`}
          title={spotlight.title}
          description={spotlight.description}
          action={
            href ? (
              <Link to={href} className="text-sm font-semibold text-brand-700 hover:underline">
                View all
              </Link>
            ) : null
          }
        />
        <HomeProductRail products={spotlight.products} accent={null} />
      </div>
    </SectionShell>
  );
}

export default function Home() {
  const {
    discovery,
    slides,
    recentlyVerified,
    trending,
    discounts,
    lowest,
    nearLow,
    multiStore,
    popular,
    drops,
    spotlights,
    categoryCounts,
  } = useLoaderData<typeof loader>();

  return (
    <main id="main-content" className="content-reveal">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: jsonLdScript(organizationJsonLd()) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: jsonLdScript(websiteJsonLd()) }}
      />

      <SectionShell
        id="hero"
        labelledBy="hero-title"
        className="overflow-hidden border-b border-line hero-atmosphere"
      >
        <div className="page-container py-6 sm:py-8 lg:py-10">
          <div className="grid items-center gap-7 md:grid-cols-[0.95fr_1.05fr] md:gap-8 lg:grid-cols-[0.92fr_1.08fr] lg:gap-10">
            <div className="order-1 min-w-0">
              <p className="eyebrow">{homeHero.eyebrow}</p>
              <h1 id="hero-title" className="mt-2 max-w-xl text-display text-ink">
                {homeHero.title}
              </h1>
              <p className="mt-3 max-w-lg text-body-lg text-ink-muted">{homeHero.description}</p>
              <div className="mt-5">
                <SearchForm placeholder={homeHero.searchPlaceholder} />
              </div>
              <ul className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs text-ink-muted sm:text-sm">
                {homeHero.searchAvailability.split(" · ").map((item) => (
                  <li key={item} className="inline-flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div className="order-2 min-w-0">
              {slides.length > 0 ? (
                <div className="overflow-hidden rounded-lg border border-line bg-surface-muted/40 shadow-soft ring-1 ring-black/[0.02]">
                  <PromoCarousel slides={slides} />
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </SectionShell>

      <div id="discover" className="section-anchor" />
      <div id="recently-verified" className="section-anchor" />

      <SectionShell id="explore-categories" labelledBy="explore-categories-title">
        <div className="page-container py-5 sm:py-6">
          <SectionHeader
            id="explore-categories"
            title="Explore categories"
            description="Browse every Mayabu public category—phones, TVs, appliances, audio, cameras, and more."
          />
          <ExploreCategoriesGrid counts={categoryCounts} />
        </div>
      </SectionShell>

      {recentlyVerified.length > 0 ? (
        <SectionShell labelledBy="recently-verified-title" tone="band">
          <div className="page-container py-5 sm:py-6">
            <SectionHeader
              id="recently-verified"
              title="Freshly Checked"
              description="Products with the most recent verified price observations."
            />
            <HomeProductRail products={recentlyVerified} accent={null} />
          </div>
        </SectionShell>
      ) : null}

      {discounts.length > 0 ? (
        <SectionShell id="discounts" labelledBy="discounts-title">
          <div className="page-container py-5 sm:py-6">
            <SectionHeader
              id="discounts"
              title="Top Deals Across Stores"
              description="Public offers where MRP is meaningfully above the current selling price."
            />
            <HomeProductRail products={discounts} accent="discount" />
          </div>
        </SectionShell>
      ) : null}

      {multiStore.length > 0 ? (
        <SectionShell id="multi-store" labelledBy="multi-store-title" tone="band">
          <div className="page-container py-5 sm:py-6">
            <SectionHeader
              id="multi-store"
              title="Best Multi-Store Comparisons"
              description={
                discovery.semantics.multi_store ??
                "Products currently available from multiple supported stores."
              }
            />
            <HomeProductRail products={multiStore} accent={null} minProducts={2} />
          </div>
        </SectionShell>
      ) : null}

      {trending.length > 0 ? (
        <SectionShell id="trending" labelledBy="trending-title">
          <div className="page-container py-5 sm:py-6">
            <SectionHeader
              id="trending"
              title="Trending on Mayabu"
              description={
                discovery.semantics.trending ?? "Rising engagement on Mayabu in the last 48 hours."
              }
            />
            <HomeProductRail products={trending} accent="trending" />
          </div>
        </SectionShell>
      ) : null}

      {drops.length > 0 ? (
        <SectionShell id="price-drops" labelledBy="price-drops-title" tone="band">
          <div className="page-container py-5 sm:py-6">
            <SectionHeader
              id="price-drops"
              title="Recent Price Drops"
              description="Current best price lower than a prior daily observation within 30 days."
            />
            <HomeProductRail products={drops} accent="drop" />
          </div>
        </SectionShell>
      ) : null}

      {nearLow.length > 0 ? (
        <SectionShell id="near-low" labelledBy="near-low-title">
          <div className="page-container py-5 sm:py-6">
            <SectionHeader
              id="near-low"
              title="Near Tracked Low"
              description={
                discovery.semantics.near_tracked_low ??
                "Current best price close to Mayabu’s tracked minimum for each product."
              }
            />
            <HomeProductRail products={nearLow} accent="lowest" />
          </div>
        </SectionShell>
      ) : null}

      {lowest.length > 0 ? (
        <SectionShell id="lowest" labelledBy="lowest-title" tone="band">
          <div className="page-container py-5 sm:py-6">
            <SectionHeader
              id="lowest"
              title="Lowest Since Tracking"
              description="Products currently at the lowest price Mayabu has recorded for them."
            />
            <HomeProductRail products={lowest} accent="lowest" />
          </div>
        </SectionShell>
      ) : null}

      {spotlights.map((spotlight, index) => (
        <SpotlightSection
          key={spotlight.slug}
          spotlight={spotlight}
          tone={index % 2 === 0 ? undefined : "band"}
        />
      ))}

      {popular.length > 0 ? (
        <SectionShell id="popular" labelledBy="popular-title" tone="band">
          <div className="page-container py-5 sm:py-6">
            <SectionHeader
              id="popular"
              title={
                popular[0]?.activity_badge === "Recently popular"
                  ? "Recently Popular on Mayabu"
                  : "Popular on Mayabu"
              }
              description={
                discovery.semantics.popular ??
                "Higher aggregate engagement on Mayabu over the last 7 days."
              }
            />
            <HomeProductRail products={popular} accent="popular" />
          </div>
        </SectionShell>
      ) : null}
    </main>
  );
}
