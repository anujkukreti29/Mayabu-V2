/** Shared category landing route factory — one architecture for all 8 public categories. */

import { data, Link, useLoaderData } from "react-router";
import type { LoaderFunctionArgs, MetaFunction } from "react-router";
import { HomeProductRail } from "~/components/home/home-product-rail";
import { ProductCard } from "~/components/product/product-card";
import { WishlistStatusBootstrap } from "~/components/product/wishlist-status-bootstrap";
import { SearchForm } from "~/components/search/search-form";
import { EmptyState } from "~/components/ui/empty-state";
import { CategoryPageSkeleton } from "~/components/ui/skeleton";
import { ApiError } from "~/lib/api/errors";
import { getCategoryLanding } from "~/lib/api/category";
import type { CategoryLandingPayload, HomepageProduct } from "~/lib/api/schemas";
import {
  getCategoryLandingConfig,
  categoryLandingPath,
  type CategoryLandingConfig,
} from "~/lib/category/landing-registry";
import { isPublicCategory, type PublicCategorySlug } from "~/lib/search/categories";
import { facetLabel, formatFacetValue } from "~/lib/search/facets";
import { buildSearchHref } from "~/lib/search/url";
import { pageMeta } from "~/lib/seo/metadata";
import { absoluteUrl } from "~/lib/seo/metadata";
import { jsonLdScript } from "~/lib/seo/site-jsonld";
import { cn } from "~/components/ui/cn";

export interface CategoryLandingLoaderData {
  config: CategoryLandingConfig;
  landing: CategoryLandingPayload | null;
  error: string | null;
  errorKind: "none" | "empty" | "service";
}

function breadcrumbJsonLd(config: CategoryLandingConfig) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: absoluteUrl("/") },
      {
        "@type": "ListItem",
        position: 2,
        name: config.displayName,
        item: absoluteUrl(config.route),
      },
    ],
  };
}

function viewAllHref(config: CategoryLandingConfig, filters?: Record<string, unknown>) {
  return buildSearchHref({
    q: config.browseQuery,
    category: config.slug,
    filters: filters ?? null,
  });
}

function OpportunitySection({
  title,
  products,
  accent,
  viewAll,
}: {
  title: string;
  products: HomepageProduct[];
  accent: "drop" | "discount" | "lowest" | "trending" | "popular";
  viewAll: string;
}) {
  if (products.length === 0) return null;
  return (
    <section className="mt-12">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-lg font-bold tracking-tight text-slate-950 sm:text-xl">{title}</h2>
        <Link
          to={viewAll}
          className="text-sm font-semibold text-brand-700 hover:text-brand-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
        >
          View all
        </Link>
      </div>
      <HomeProductRail products={products} accent={accent} />
    </section>
  );
}

export function createCategoryLanding(slug: PublicCategorySlug) {
  const config = getCategoryLandingConfig(slug);

  const meta: MetaFunction = () =>
    pageMeta({
      title: config.title,
      description: config.metaDescription,
      path: config.route,
      robots: "index, follow",
    });

  async function loader({ request }: LoaderFunctionArgs) {
    try {
      const landing = await getCategoryLanding(slug, request.signal);
      const empty = !landing.products.length && !landing.featured.length;
      return data<CategoryLandingLoaderData>({
        config,
        landing,
        error: empty ? "We're still expanding verified products in this category." : null,
        errorKind: empty ? "empty" : "none",
      });
    } catch (error) {
      const isNetwork =
        error instanceof ApiError &&
        (error.category === "network" || error.category === "timeout" || error.status === 0);
      const isServer =
        error instanceof ApiError && (error.category === "server" || (error.status ?? 0) >= 500);
      console.error("[mayabu:category-landing]", {
        slug,
        status: error instanceof ApiError ? error.status : null,
        category: error instanceof ApiError ? error.category : "unknown",
      });
      return data<CategoryLandingLoaderData>(
        {
          config,
          landing: null,
          error:
            isNetwork || isServer || !(error instanceof ApiError)
              ? "Mayabu could not load this category right now. Please try again shortly."
              : "This category is temporarily unavailable.",
          errorKind: "service",
        },
        { status: isNetwork || isServer ? 503 : 502 },
      );
    }
  }

  function Component() {
    const { config: cfg, landing, error, errorKind } = useLoaderData<typeof loader>();
    const products = landing?.products ?? [];
    const featured = landing?.featured ?? [];
    const discoveryIds = [
      ...new Set([
        ...featured.map((p) => p.id),
        ...products.map((p) => p.id),
        ...(landing?.price_drops ?? []).map((p) => p.id),
        ...(landing?.biggest_discounts ?? []).map((p) => p.id),
        ...(landing?.lowest_since_tracking ?? []).map((p) => p.id),
        ...(landing?.trending ?? []).map((p) => p.id),
        ...(landing?.popular ?? []).map((p) => p.id),
      ]),
    ];

    const primaryFacetKeys = cfg.primaryFacets;
    const facetEntries = Object.entries(landing?.facets ?? {}).filter(([key, values]) => {
      if (!values.length) return false;
      if (primaryFacetKeys.length && !primaryFacetKeys.includes(key)) return false;
      return true;
    });

    const related = (
      landing?.related_categories?.length ? landing.related_categories : [...cfg.relatedSlugs]
    )
      .filter((relatedSlug): relatedSlug is PublicCategorySlug => isPublicCategory(relatedSlug))
      .map((relatedSlug) => ({
        slug: relatedSlug,
        path: categoryLandingPath(relatedSlug)!,
        label: getCategoryLandingConfig(relatedSlug).displayName,
      }));

    return (
      <main id="main-content" className="bg-page">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLdScript(breadcrumbJsonLd(cfg)) }}
        />
        <WishlistStatusBootstrap productIds={discoveryIds} />

        <section className="border-b border-line hero-atmosphere">
          <div className="page-container py-7 sm:py-9">
            <nav aria-label="Breadcrumb" className="text-sm text-ink-muted">
              <ol className="flex flex-wrap items-center gap-1.5">
                <li>
                  <Link to="/" className="font-medium transition hover:text-accent">
                    Home
                  </Link>
                </li>
                <li aria-hidden="true">›</li>
                <li className="font-semibold text-ink">{cfg.displayName}</li>
              </ol>
            </nav>

            <div className="mt-4 max-w-3xl">
              <h1 className="text-display text-ink">{cfg.heading}</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted sm:text-base sm:leading-7">
                {cfg.description}
              </p>
              {typeof landing?.product_count === "number" && landing.product_count > 0 ? (
                <p className="mt-2 text-sm font-semibold text-ink-soft">
                  {landing.product_count.toLocaleString("en-IN")} products with live prices
                </p>
              ) : null}
            </div>

            <div className="mt-5 max-w-2xl">
              <SearchForm
                placeholder={cfg.searchPlaceholder}
                submitLabel="Search"
                hiddenFields={{ category: cfg.slug }}
              />
            </div>
          </div>
        </section>

        <div className="page-container py-8 sm:py-10">
          {errorKind === "service" ? (
            <EmptyState
              title="Category temporarily unavailable"
              description={error || "Please try again shortly."}
            />
          ) : null}

          {errorKind === "empty" ? (
            <EmptyState
              title="We're still expanding verified products in this category."
              description="Try searching, or explore another live Mayabu category."
              action={
                <Link
                  to="/"
                  className="inline-flex min-h-10 items-center rounded-lg bg-brand-600 px-4 text-sm font-bold text-white hover:bg-brand-700"
                >
                  Discover products
                </Link>
              }
            />
          ) : null}

          {featured.length > 0 ? (
            <section>
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold tracking-tight text-slate-950 sm:text-xl">
                    Featured in {cfg.displayName}
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    Recently verified products with strong offer coverage.
                  </p>
                </div>
                <Link
                  to={viewAllHref(cfg)}
                  className="text-sm font-semibold text-brand-700 hover:text-brand-800"
                >
                  View all {cfg.displayName.toLowerCase()}
                </Link>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {featured.slice(0, 4).map((product) => (
                  <ProductCard key={`feat-${product.id}`} product={product} />
                ))}
              </div>
            </section>
          ) : null}

          {products.length > 0 ? (
            <section className={cn(featured.length > 0 && "mt-12")}>
              <div className="lg:grid lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-8">
                <aside className="mb-6 lg:mb-0">
                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <h2 className="text-sm font-bold text-slate-900">Browse by</h2>
                    <p className="mt-1 text-xs text-slate-500">
                      Filters open Search with this category locked.
                    </p>
                    {facetEntries.length === 0 ? (
                      <p className="mt-3 text-sm text-slate-500">No discovery filters yet.</p>
                    ) : (
                      <div className="mt-3 space-y-4">
                        {facetEntries.slice(0, 5).map(([key, values]) => (
                          <div key={key}>
                            <p className="text-[12px] font-semibold uppercase tracking-wide text-slate-500">
                              {facetLabel(key)}
                            </p>
                            <ul className="mt-1.5 flex flex-wrap gap-1.5">
                              {values.slice(0, 6).map((item) => (
                                <li key={`${key}-${item.value}`}>
                                  <Link
                                    to={viewAllHref(cfg, { [key]: item.value })}
                                    className="inline-flex min-h-8 items-center rounded-md border border-slate-200 bg-slate-50 px-2 text-xs font-medium text-slate-700 hover:border-brand-300 hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
                                  >
                                    {formatFacetValue(key, item.value)}
                                  </Link>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="mt-4 border-t border-slate-100 pt-3">
                      <p className="text-[12px] font-semibold uppercase tracking-wide text-slate-500">
                        Sort in search
                      </p>
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {(
                          [
                            ["relevance", "Relevance"],
                            ["price_asc", "Price low → high"],
                            ["price_desc", "Price high → low"],
                            ["recently_checked", "Recently checked"],
                          ] as const
                        ).map(([sort, label]) => (
                          <Link
                            key={sort}
                            to={buildSearchHref({
                              q: cfg.browseQuery,
                              category: cfg.slug,
                              sort,
                            })}
                            className="inline-flex min-h-8 items-center rounded-md border border-slate-200 px-2 text-xs font-medium text-slate-700 hover:border-brand-300 hover:bg-brand-50"
                          >
                            {label}
                          </Link>
                        ))}
                      </div>
                    </div>
                    <Link
                      to={viewAllHref(cfg)}
                      className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-lg bg-brand-600 px-3 text-sm font-bold text-white hover:bg-brand-700"
                    >
                      View results
                    </Link>
                  </div>
                </aside>

                <div>
                  <div className="flex flex-wrap items-end justify-between gap-3">
                    <h2 className="text-lg font-bold tracking-tight text-slate-950 sm:text-xl">
                      Shop {cfg.displayName}
                    </h2>
                    <Link
                      to={viewAllHref(cfg)}
                      className="text-sm font-semibold text-brand-700 hover:text-brand-800"
                    >
                      View all
                    </Link>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {products.map((product) => (
                      <ProductCard key={product.id} product={product} />
                    ))}
                  </div>
                </div>
              </div>
            </section>
          ) : null}

          {landing ? (
            <>
              <OpportunitySection
                title={`Biggest discounts in ${cfg.displayName}`}
                products={landing.biggest_discounts}
                accent="discount"
                viewAll={viewAllHref(cfg)}
              />
              <OpportunitySection
                title="Recent price drops"
                products={landing.price_drops}
                accent="drop"
                viewAll={viewAllHref(cfg)}
              />
              <OpportunitySection
                title="Lowest since tracking"
                products={landing.lowest_since_tracking}
                accent="lowest"
                viewAll={viewAllHref(cfg)}
              />
              <OpportunitySection
                title={`Trending in ${cfg.displayName}`}
                products={landing.trending}
                accent="trending"
                viewAll={viewAllHref(cfg)}
              />
              <OpportunitySection
                title={`Popular ${cfg.displayName}`}
                products={landing.popular}
                accent="popular"
                viewAll={viewAllHref(cfg)}
              />
            </>
          ) : null}

          {related.length > 0 ? (
            <section className="mt-14 border-t border-slate-200 pt-8">
              <h2 className="text-lg font-bold tracking-tight text-slate-950">
                Explore more categories
              </h2>
              <ul className="mt-4 flex flex-wrap gap-2">
                {related.map((item) => (
                  <li key={item.slug}>
                    <Link
                      to={item.path}
                      className="inline-flex min-h-10 items-center rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-800 hover:border-brand-300 hover:bg-brand-50"
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      </main>
    );
  }

  function HydrateFallback() {
    return <CategoryPageSkeleton />;
  }

  return { meta, loader, Component, HydrateFallback, config };
}
