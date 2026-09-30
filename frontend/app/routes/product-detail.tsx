import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, GitCompareArrows, Link2, ShieldCheck } from "lucide-react";
import { data, Link, redirect, useLoaderData } from "react-router";
import type { LoaderFunctionArgs, MetaFunction } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import { PdpHeroSkeleton, PriceHistorySkeleton } from "~/components/ui/skeleton";
import { ProductImageGallery } from "~/components/product/product-image-gallery";
import { ProductCard } from "~/components/product/product-card";
import { ProductSpecTable } from "~/components/product/product-spec-table";
import { OffersList } from "~/components/product/offers-list";
import { StoreCoverageDrawer } from "~/components/product/store-coverage-drawer";
import { PriceIntelligencePanel } from "~/components/product/price-intelligence-panel";
import { PriceEvidencePanel } from "~/components/product/price-evidence-panel";
import { VerificationPanel } from "~/components/verification/verification-panel";
import { useCompare } from "~/components/comparison/compare-provider";
import { WishlistToggleButton } from "~/components/product/wishlist-toggle-button";
import { WishlistStatusBootstrap } from "~/components/product/wishlist-status-bootstrap";
import { WatchPriceControl } from "~/components/product/watch-price-control";
import { ApiError } from "~/lib/api/errors";
import { getPriceHistory, getPriceIntelligence, getProduct } from "~/lib/api/products";
import type { PriceHistory, PriceIntelligence, ProductDetail } from "~/lib/api/schemas";
import { formatPrice } from "~/lib/formatting/price";
import { freshnessFrom } from "~/lib/formatting/freshness";
import { absoluteUrl, pageMeta } from "~/lib/seo/metadata";
import { productSlug } from "~/lib/seo/slug";
import { breadcrumbJsonLd, productJsonLd } from "~/lib/seo/structured-data";
import { productKeys } from "~/lib/query/keys";
import { buildBuyingInsight } from "~/lib/pricing/insight";
import { buildPriceEvidence } from "~/lib/product/price-evidence";
import { priceDisclaimer, sellerStatement } from "~/lib/content/trust";
import { routes } from "~/lib/navigation/routes";
import { categoryShortLabel, isPublicCategory } from "~/lib/search/categories";
import { platformDisplayName } from "~/lib/search/platforms";
import {
  bestOfferId,
  categoryBreadcrumbLabel,
  categorySearchHref,
  limitedCoverageHint,
  matchEvidenceRows,
  hardConflictWarning,
  productDetailSpecRows,
  similarVariantsBlurb,
  storeCoverageCopy,
  uniqueOffersByPlatform,
  variantIdentityLine,
} from "~/lib/product/detail-view";
import { recordProductActivity } from "~/lib/api/activity";
import { cn } from "~/components/ui/cn";

const PriceHistoryChart = lazy(() =>
  import("~/components/pricing/price-history-chart").then((module) => ({
    default: module.PriceHistoryChart,
  })),
);

interface ProductLoaderData {
  notFound: false;
  detail: ProductDetail;
  history: PriceHistory | null;
  intelligence: PriceIntelligence | null;
  historyError: boolean;
}

interface ProductNotFoundData {
  notFound: true;
}

type ProductRouteData = ProductLoaderData | ProductNotFoundData;

export function HydrateFallback() {
  return (
    <main id="main-content" className="bg-page">
      <PdpHeroSkeleton />
    </main>
  );
}

export async function loader({ params, request }: LoaderFunctionArgs) {
  const productId = params.productId;
  if (!productId) return data<ProductNotFoundData>({ notFound: true }, { status: 404 });
  let detail: ProductDetail;
  try {
    detail = await getProduct(productId, request.signal);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404)
      return data<ProductNotFoundData>({ notFound: true }, { status: 404 });
    throw new Response("Product service unavailable", { status: 503 });
  }
  const canonicalSlug = productSlug(detail.product.title);
  if (params.productSlug !== canonicalSlug) {
    throw redirect(`/products/${encodeURIComponent(productId)}/${canonicalSlug}`, 308);
  }
  try {
    const [historyResult, intelligenceResult] = await Promise.allSettled([
      getPriceHistory(productId, { window: "all" }, request.signal),
      getPriceIntelligence(productId, request.signal),
    ]);
    return data<ProductLoaderData>({
      notFound: false,
      detail,
      history: historyResult.status === "fulfilled" ? historyResult.value : null,
      intelligence: intelligenceResult.status === "fulfilled" ? intelligenceResult.value : null,
      historyError: historyResult.status === "rejected",
    });
  } catch {
    return data<ProductLoaderData>({
      notFound: false,
      detail,
      history: null,
      intelligence: null,
      historyError: true,
    });
  }
}

export const meta: MetaFunction<typeof loader> = ({ data: loaderData }) => {
  if (!loaderData || loaderData.notFound)
    return pageMeta({
      title: "Product Not Found | Mayabu",
      description: "The requested Mayabu product could not be found.",
      path: "/products/not-found",
      robots: "noindex, nofollow",
    });
  const product = loaderData.detail.product;
  const categoryLabel = categoryShortLabel(product.category) || "product";
  return [
    ...pageMeta({
      title: `${product.title} Price Comparison | Mayabu`,
      description: `Compare current prices and key specifications for ${product.title} on Mayabu. Review ${categoryLabel.toLowerCase()} details and observed price history across supported retailers.`,
      path: `/products/${product.id}/${productSlug(product.title)}`,
      image: product.image_url,
      ogType: "product",
    }),
  ];
};

function Insight({
  detail,
  history,
  intelligence,
}: {
  detail: ProductDetail;
  history: PriceHistory | null;
  intelligence: PriceIntelligence | null;
}) {
  if (intelligence) {
    return <PriceIntelligencePanel intelligence={intelligence} />;
  }
  const insight = buildBuyingInsight(
    detail.product.best_price,
    history?.history.map((point) => point.best_price) ?? [],
  );
  return (
    <div className="surface p-5">
      <div className="flex items-start gap-3">
        <ShieldCheck aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-title-sm text-ink">Mayabu buying insight</h2>
            <Badge tone="info">{insight.badge}</Badge>
          </div>
          <p className="mt-2 text-sm leading-6 text-ink-muted">{insight.message}</p>
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer font-semibold text-accent">
              Why Mayabu says this
            </summary>
            <p className="mt-2 leading-6 text-ink-muted">
              This summary uses only the current stored price and valid historical observations. It
              is not a prediction or guarantee.
            </p>
          </details>
        </div>
      </div>
    </div>
  );
}

function CopyLinkButton() {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(window.location.href);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 2000);
        } catch {
          setCopied(false);
        }
      }}
    >
      <Link2 aria-hidden="true" className="h-4 w-4" />
      {copied ? "Link copied" : "Copy link"}
    </Button>
  );
}

function CompareAction({ product }: { product: ProductDetail["product"] }) {
  const compare = useCompare();
  const inList = compare.has(product.id);
  const canAdd = compare.canCompare(product);
  const reason = compare.compareBlockReason(product);

  if (inList || canAdd) {
    return (
      <Button
        type="button"
        variant="outline"
        onClick={() => compare.add(product)}
        disabled={inList}
      >
        <GitCompareArrows aria-hidden="true" className="h-4 w-4" />
        {inList ? "In compare list" : "Add to compare"}
      </Button>
    );
  }

  const hint =
    reason === "unsupported_category"
      ? "Compare is available for Mayabu’s public product categories."
      : reason === "category_mismatch"
        ? "Compare only products from the same category."
        : reason === "full"
          ? "Compare list is full."
          : "Compare is unavailable for this product.";

  return (
    <div>
      <Button type="button" variant="outline" disabled aria-disabled="true" title={hint}>
        <GitCompareArrows aria-hidden="true" className="h-4 w-4" />
        Compare unavailable
      </Button>
      <p className="mt-2 max-w-xs text-xs leading-5 text-ink-muted">{hint}</p>
    </div>
  );
}

function ProductNotFoundPage() {
  return (
    <main id="main-content" className="page-container py-20">
      <div className="mx-auto max-w-2xl surface-elevated px-8 py-10 text-center">
        <p className="eyebrow">Error 404</p>
        <h1 className="mt-2 page-title text-3xl">Product not found</h1>
        <p className="mt-3 text-ink-muted">
          The product may have moved, or it may no longer be available in Mayabu&apos;s index.
        </p>
        <Link
          to={routes.search}
          className="mt-6 inline-flex min-h-11 items-center rounded-md bg-accent px-5 font-semibold text-white hover:bg-accent-strong"
        >
          Search products
        </Link>
      </div>
    </main>
  );
}

export default function ProductDetailRoute() {
  const loaderData: ProductRouteData = useLoaderData<typeof loader>();
  if (loaderData.notFound) return <ProductNotFoundPage />;
  return <ProductDetailPage loaderData={loaderData} />;
}

function ProductDetailPage({ loaderData }: { loaderData: ProductLoaderData }) {
  const { detail, history, intelligence, historyError } = loaderData;
  const queryClient = useQueryClient();
  const {
    product,
    offers,
    similar_variants: similarVariants,
    similar_products: similarProducts = [],
  } = detail;
  const offerFreshness = freshnessFrom(
    offers
      .map((offer) => offer.last_verified_at ?? offer.last_checked_at)
      .filter(Boolean)
      .sort()
      .at(-1) ?? product.last_seen_at,
  );
  const specRows = productDetailSpecRows(product);
  const categoryHref = categorySearchHref(product.category);
  const categoryLabel = categoryBreadcrumbLabel(product.category);
  const publicOffers = uniqueOffersByPlatform(offers);
  const bestId = bestOfferId(publicOffers);
  const bestRetailer = platformDisplayName(product.best_platform);
  const coverage = storeCoverageCopy(publicOffers.length);
  const coverageHint = limitedCoverageHint(publicOffers.length);
  const historyPoints = history?.history ?? [];
  const evidence = useMemo(() => {
    const base = buildPriceEvidence({ product, offers: publicOffers, history });
    if (!intelligence) return base;
    const extra: string[] = [];
    if (intelligence.timing_signal?.label) extra.push(intelligence.timing_signal.label);
    return { ...base, decisionFacts: [...extra, ...base.decisionFacts].slice(0, 4) };
  }, [product, publicOffers, history, intelligence]);
  const [priceFlash, setPriceFlash] = useState(false);
  const [flashFrom, setFlashFrom] = useState<number | null>(null);
  const lastBestRef = useRef<number | null>(product.best_price ?? null);

  useEffect(() => {
    queryClient.setQueryData(productKeys.detail(product.id), detail);
    if (history)
      queryClient.setQueryData(productKeys.priceHistory(product.id, history.days), history);
  }, [detail, history, product.id, queryClient]);

  useEffect(() => {
    void recordProductActivity(product.id, "product_view");
  }, [product.id]);

  useEffect(() => {
    const previous = lastBestRef.current;
    const next = product.best_price ?? null;
    if (previous != null && next != null && previous !== next) {
      setFlashFrom(previous);
      setPriceFlash(true);
      const timer = window.setTimeout(() => {
        setPriceFlash(false);
        setFlashFrom(null);
      }, 1800);
      lastBestRef.current = next;
      return () => window.clearTimeout(timer);
    }
    lastBestRef.current = next;
  }, [product.best_price]);

  const variantLine = variantIdentityLine(product);
  const matchRows = matchEvidenceRows(product);
  const conflictWarning = hardConflictWarning(product);
  const showMatchEvidence = matchRows.length > 0 || Boolean(conflictWarning);

  const structuredData = useMemo(
    () => [breadcrumbJsonLd(product), productJsonLd(detail)],
    [detail, product],
  );

  return (
    <main id="main-content" className="commerce-container min-w-0 py-6 sm:py-8 lg:py-10 pb-24 lg:pb-10">
      <WishlistStatusBootstrap productIds={[product.id]} />
      {structuredData.map((value, index) => (
        <script key={index} type="application/ld+json">
          {JSON.stringify(value)}
        </script>
      ))}

      <nav aria-label="Breadcrumb" className="text-sm text-ink-muted">
        <ol className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <li>
            <Link className="hover:text-accent" to="/">
              Home
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li>
            <Link className="hover:text-accent" to={categoryHref}>
              {categoryLabel}
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li aria-current="page" className="max-w-[min(100%,20rem)] truncate text-ink-soft">
            {product.title}
          </li>
        </ol>
      </nav>

      <section
        aria-labelledby="product-title"
        className="mt-5 grid min-w-0 gap-6 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] lg:items-start lg:gap-10"
      >
        <div className="order-2 min-w-0 max-w-full lg:order-1">
          <ProductImageGallery
            images={detail.images ?? []}
            title={product.title}
            category={product.category}
            fallbackSrc={product.image_url}
          />
        </div>

        <div className="order-1 min-w-0 space-y-4 lg:sticky lg:top-[calc(var(--mayabu-header-h)+0.75rem)] lg:order-2 lg:max-h-[calc(100vh-5.25rem)] lg:overflow-y-auto lg:pr-1">
          <div>
            <p className="eyebrow">{categoryShortLabel(product.category) || "Product"}</p>
            <p className="mt-1.5 text-sm font-semibold text-ink-soft">
              {product.brand || "Brand unavailable"}
            </p>
            <h1 id="product-title" className="mt-1 text-title-md leading-tight text-ink sm:text-title-lg lg:text-[1.85rem] lg:font-semibold">
              {product.title}
            </h1>
            {variantLine ? (
              <p className="mt-2 text-sm font-medium text-ink">
                <span className="text-ink-muted">This configuration</span>
                <span className="mx-1.5 text-ink-faint" aria-hidden="true">
                  ·
                </span>
                {variantLine}
              </p>
            ) : null}
            {isPublicCategory(product.category) ? (
              <p className="mt-2 text-xs leading-5 text-ink-muted">
                <span className="font-semibold text-ink-soft">Matched configuration. </span>
                Mayabu keeps storage, screen size, appliance capacity and camera kits separate when
                comparing retailer listings.{" "}
                <Link to={routes.howItWorks} className="font-medium text-accent hover:text-accent-strong">
                  How matching works
                </Link>
              </p>
            ) : null}
          </div>

          <div className="border-y border-line py-4">
            <p className="text-sm font-medium text-ink-muted">Best current listed price</p>
            <p
              className={cn(
                "price-numerals mt-1 text-4xl font-bold tracking-tight text-ink sm:text-5xl",
                "motion-safe:transition-colors motion-safe:duration-500",
                priceFlash && "text-positive",
              )}
            >
              {formatPrice(product.best_price)}
            </p>
            {priceFlash && flashFrom != null ? (
              <p className="mt-1 text-sm font-medium text-positive motion-reduce:transition-none">
                Updated from {formatPrice(flashFrom)}
              </p>
            ) : null}
            <p className="mt-2 text-sm text-ink-soft">
              {bestRetailer ? `Best price at ${bestRetailer}` : "No active platform price recorded"}
              {publicOffers.length > 0 ? ` · ${coverage}` : null}
            </p>
            <p
              className={`mt-1 text-sm ${
                offerFreshness.tone === "warning" ? "text-amber-800" : "text-ink-muted"
              }`}
              title="This store listing was last successfully checked at the time shown."
            >
              {offerFreshness.label}
            </p>
            {coverageHint ? (
              <p className="mt-1 text-xs leading-5 text-ink-muted">{coverageHint}</p>
            ) : null}
            {publicOffers.length > 0 ? <StoreCoverageDrawer offers={publicOffers} /> : null}
            <div className="mt-4 space-y-3">
              <PriceEvidencePanel evidence={evidence} />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <CompareAction product={product} />
            <WishlistToggleButton productId={product.id} productTitle={product.title} />
            <WatchPriceControl
              productId={product.id}
              productTitle={product.title}
              currentPrice={product.best_price}
            />
            <CopyLinkButton />
            <Link
              to={`/contact?topic=incorrect-match&product=${encodeURIComponent(absoluteUrl(`/products/${product.id}/${productSlug(product.title)}`))}`}
              className="inline-flex min-h-11 items-center rounded-md px-4 text-sm font-semibold text-ink-soft hover:bg-surface-muted"
            >
              Report wrong match
            </Link>
          </div>

          <VerificationPanel productId={product.id} offerCount={publicOffers.length} />

          {showMatchEvidence ? (
            <details className="surface p-4">
              <summary className="cursor-pointer text-sm font-semibold text-ink">
                Why these listings match
              </summary>
              <p className="mt-2 text-xs leading-5 text-ink-muted">
                Retailer listings are aligned to this configuration using normalized product identity.
                Only category fields present for this product are shown.
              </p>
              {conflictWarning ? (
                <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
                  {conflictWarning}
                </p>
              ) : null}
              {matchRows.length > 0 ? (
                <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  {matchRows.map((row) => (
                    <div key={row.key}>
                      <dt className="text-ink-muted">{row.label}</dt>
                      <dd className="font-medium text-ink">{row.value}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
              {publicOffers.length > 0 ? (
                <p className="mt-3 text-xs text-ink-muted">
                  Matched across:{" "}
                  {publicOffers
                    .map((offer) => platformDisplayName(offer.platform) || offer.platform)
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              ) : null}
            </details>
          ) : null}
        </div>

        {specRows.length > 0 ? (
          <div className="order-3 lg:hidden">
            <h2 className="section-title text-lg">Key specifications</h2>
            <ProductSpecTable rows={specRows.slice(0, 6)} compact className="mt-3" />
          </div>
        ) : null}
      </section>

      <section id="offers" className="mt-12 section-anchor" aria-labelledby="offers-heading">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
          <div>
            <h2 id="offers-heading" className="section-title">
              Compare prices across stores
            </h2>
            <p className="mt-2 text-sm leading-6 text-ink-muted">
              Offers below are matched to this exact Mayabu product variant. Prices come from
              retailer listings and include when each price was last checked.
            </p>
            <div className="mt-5">
              <OffersList offers={publicOffers} bestOfferId={bestId} productId={product.id} />
            </div>
          </div>
          <div className="space-y-5">
            <Insight detail={detail} history={history} intelligence={intelligence} />
            <div className="surface-muted p-5">
              <div className="flex gap-3">
                <AlertTriangle
                  aria-hidden="true"
                  className="mt-0.5 h-5 w-5 shrink-0 text-amber-600"
                />
                <p className="text-sm leading-6 text-ink-muted">
                  {sellerStatement} {priceDisclaimer}
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-12" aria-labelledby="specs-heading">
        <h2 id="specs-heading" className="section-title">
          Product specifications
        </h2>
        <p className="mt-2 text-sm text-ink-muted">
          Specs are taken from Mayabu&apos;s normalized product data. Empty fields are omitted.
        </p>
        {specRows.length > 0 ? (
          <div className="mt-5 surface p-4 sm:p-5">
            <ProductSpecTable rows={specRows} className="max-w-none border-0" />
          </div>
        ) : (
          <p className="mt-5 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
            Detailed specifications are not available for this product yet.
          </p>
        )}
      </section>

      <section className="mt-12" aria-labelledby="history-heading">
        <h2 id="history-heading" className="section-title">
          Price history
        </h2>
        <p className="mt-2 text-sm leading-6 text-ink-muted">
          Observed best prices over time. This is Mayabu&apos;s recorded history, not an all-time
          market history.
        </p>
        {evidence.priceMovement || evidence.lowestSinceTracking != null ? (
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-soft">
            {product.best_price != null ? <li>Current {formatPrice(product.best_price)}</li> : null}
            {evidence.previousTrackedPrice != null ? (
              <li>Previous tracked {formatPrice(evidence.previousTrackedPrice)}</li>
            ) : null}
            {evidence.lowestSinceTracking != null ? (
              <li>Tracked low {formatPrice(evidence.lowestSinceTracking)}</li>
            ) : null}
            {evidence.priceMovement ? <li>{evidence.priceMovement}</li> : null}
          </ul>
        ) : null}
        <div className="mt-5 surface-elevated p-5">
          {history && historyPoints.length > 0 ? (
            <Suspense fallback={<PriceHistorySkeleton />}>
              <PriceHistoryChart history={historyPoints} payload={history} />
            </Suspense>
          ) : (
            <div className="py-6 text-center">
              <h3 className="text-title-sm text-ink">
                {historyError ? "Price history unavailable" : "Not enough price history yet"}
              </h3>
              <p className="mt-2 text-sm text-ink-muted">
                {historyError
                  ? "This section could not be loaded. Try again later."
                  : "We need more tracked prices before showing a meaningful history."}
              </p>
            </div>
          )}
        </div>
      </section>

      <section className="mt-12" aria-labelledby="trust-heading">
        <h2 id="trust-heading" className="section-title">
          How Mayabu compares this product
        </h2>
        <details className="mt-4 surface open:pb-4">
          <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-ink">
            Matching, freshness, and retailer links
          </summary>
          <ul className="space-y-2 px-5 text-sm leading-6 text-ink-muted">
            <li>Prices are checked from retailer listings.</li>
            <li>Exact variant matching is used across stores.</li>
            <li>Timestamps show when each offer was last observed — not a live checkout quote.</li>
            <li>Mayabu does not process checkout; retailer pages remain the place of purchase.</li>
          </ul>
        </details>
      </section>

      {similarVariants.length > 0 ? (
        <section className="mt-12" aria-labelledby="similar-variants-heading">
          <h2 id="similar-variants-heading" className="section-title">
            Similar variants
          </h2>
          <p className="mt-2 text-sm text-ink-muted">{similarVariantsBlurb(product.category)}</p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {similarVariants.map((variant) => (
              <ProductCard key={variant.id} product={variant} relationship="similar_variant" />
            ))}
          </div>
        </section>
      ) : null}

      {similarProducts.length > 0 ? (
        <section className="mt-12" aria-labelledby="similar-products-heading">
          <h2 id="similar-products-heading" className="section-title">
            Similar products
          </h2>
          <p className="mt-2 text-sm text-ink-muted">
            Other public products in this category with a comparable price range.
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {similarProducts.map((item) => (
              <ProductCard key={item.id} product={item} relationship="related_product" />
            ))}
          </div>
        </section>
      ) : null}

      <div className="fixed inset-x-0 bottom-0 z-[45] border-t border-line bg-white/95 px-3 py-2.5 shadow-lift sm:px-4 lg:hidden pb-[max(0.5rem,env(safe-area-inset-bottom))]">
        <div className="mx-auto flex max-w-lg min-w-0 items-center gap-2 sm:gap-3">
          <div className="min-w-0 flex-1">
            <p className="price-numerals text-lg font-bold text-ink">{formatPrice(product.best_price)}</p>
            <p className="truncate text-xs text-ink-muted">{offerFreshness.label}</p>
          </div>
          <a
            href="#check-price"
            className="inline-flex min-h-11 shrink-0 items-center rounded-md bg-accent px-2.5 text-sm font-semibold text-white sm:px-3"
          >
            Check price
          </a>
          <a
            href="#offers"
            className="inline-flex min-h-11 shrink-0 items-center rounded-md border border-line px-2.5 text-sm font-semibold text-ink sm:px-3"
          >
            Offers
          </a>
        </div>
      </div>
    </main>
  );
}
