import { lazy, Suspense, useEffect, useMemo } from "react";
import { AlertTriangle, GitCompareArrows, ShieldCheck } from "lucide-react";
import { data, Link, redirect, useLoaderData } from "react-router";
import type { LoaderFunctionArgs, MetaFunction } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import { Card } from "~/components/ui/card";
import { Skeleton } from "~/components/ui/skeleton";
import { ProductImage } from "~/components/product/product-image";
import { ProductCard } from "~/components/product/product-card";
import { OffersList } from "~/components/product/offers-list";
import { VerificationPanel } from "~/components/verification/verification-panel";
import { useCompare } from "~/components/comparison/compare-provider";
import { ApiError } from "~/lib/api/errors";
import { getPriceHistory, getProduct } from "~/lib/api/products";
import type { PriceHistory, ProductDetail } from "~/lib/api/schemas";
import { formatPrice } from "~/lib/formatting/price";
import { freshnessFrom } from "~/lib/formatting/freshness";
import { absoluteUrl, pageMeta } from "~/lib/seo/metadata";
import { productSlug } from "~/lib/seo/slug";
import { breadcrumbJsonLd, productJsonLd } from "~/lib/seo/structured-data";
import { productKeys } from "~/lib/query/keys";
import { buildBuyingInsight } from "~/lib/pricing/insight";
import { priceDisclaimer, sellerStatement } from "~/lib/content/trust";
import { routes } from "~/lib/navigation/routes";

const PriceHistoryChart = lazy(() =>
  import("~/components/pricing/price-history-chart").then((module) => ({
    default: module.PriceHistoryChart,
  })),
);

interface ProductLoaderData {
  notFound: false;
  detail: ProductDetail;
  history: PriceHistory | null;
  historyError: boolean;
}

interface ProductNotFoundData {
  notFound: true;
}

type ProductRouteData = ProductLoaderData | ProductNotFoundData;

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
    const history = await getPriceHistory(productId, 180, request.signal);
    return data<ProductLoaderData>({ notFound: false, detail, history, historyError: false });
  } catch {
    return data<ProductLoaderData>({ notFound: false, detail, history: null, historyError: true });
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
  return [
    ...pageMeta({
      title: `${product.title}: Price Comparison and History | Mayabu`,
      description: `Compare ${product.title} across supported Indian retailers, review specifications, the best known price, price history, availability, and verification freshness.`,
      path: `/products/${product.id}/${productSlug(product.title)}`,
      image: product.image_url ?? "/og-default.svg",
      ogType: "product",
    }),
  ];
};

function specificationRows(detail: ProductDetail) {
  const specs = detail.product.specs;
  return [
    ["Model", specs.model_codes?.join(", ")],
    ["Processor", specs.cpu_models?.join(", ") ?? specs.cpu_series],
    ["RAM", specs.ram_gb ? `${specs.ram_gb} GB` : undefined],
    ["Storage", specs.storage_gb ? `${specs.storage_gb} GB` : undefined],
    ["Graphics", specs.gpu],
    ["Screen", specs.screen_inch ? `${specs.screen_inch} inch` : undefined],
    ["Generation", specs.generation],
  ].filter((row): row is [string, string] => Boolean(row[1]));
}

function Insight({ detail, history }: { detail: ProductDetail; history: PriceHistory | null }) {
  const insight = buildBuyingInsight(
    detail.product.best_price,
    history?.history.map((point) => point.best_price) ?? [],
  );
  return (
    <Card className="p-5">
      <div className="flex items-start gap-3">
        <ShieldCheck aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" />
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-black">Mayabu buying insight</h2>
            <Badge tone="info">{insight.badge}</Badge>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">{insight.message}</p>
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer font-bold text-brand-700">
              Why Mayabu says this
            </summary>
            <p className="mt-2 leading-6 text-slate-600">
              This summary uses only the current stored price and valid historical observations. It
              is not a prediction or guarantee.
            </p>
          </details>
        </div>
      </div>
    </Card>
  );
}

function ProductNotFoundPage() {
  return (
    <main id="main-content" className="page-container py-20">
      <Card className="mx-auto max-w-2xl p-8 text-center">
        <p className="text-sm font-bold text-brand-700">Error 404</p>
        <h1 className="mt-2 text-3xl font-black">Page not found</h1>
        <p className="mt-3 text-slate-600">
          The product may have moved, or it may no longer be available in Mayabu's index.
        </p>
        <Link
          to={routes.search}
          className="mt-6 inline-flex min-h-11 items-center rounded-xl bg-brand-600 px-5 font-bold text-white"
        >
          Search products
        </Link>
      </Card>
    </main>
  );
}

export default function ProductDetailRoute() {
  const loaderData: ProductRouteData = useLoaderData<typeof loader>();
  if (loaderData.notFound) return <ProductNotFoundPage />;
  return <ProductDetailPage loaderData={loaderData} />;
}

function ProductDetailPage({ loaderData }: { loaderData: ProductLoaderData }) {
  const { detail, history, historyError } = loaderData;
  const queryClient = useQueryClient();
  const compare = useCompare();
  const { product, offers, similar_variants: similarVariants } = detail;
  const fresh = freshnessFrom(product.last_seen_at);
  const rows = specificationRows(detail);
  const categoryPath = product.category?.toLowerCase().includes("mobile")
    ? routes.mobilePhones
    : routes.laptops;
  const categoryLabel = categoryPath === routes.laptops ? "Laptops" : "Mobile Phones";

  useEffect(() => {
    queryClient.setQueryData(productKeys.detail(product.id), detail);
    if (history)
      queryClient.setQueryData(productKeys.priceHistory(product.id, history.days), history);
  }, [detail, history, product.id, queryClient]);

  const structuredData = useMemo(
    () => [breadcrumbJsonLd(product), productJsonLd(detail)],
    [detail, product],
  );

  return (
    <main id="main-content" className="page-container py-8 sm:py-10">
      {structuredData.map((value, index) => (
        <script key={index} type="application/ld+json">
          {JSON.stringify(value)}
        </script>
      ))}
      <nav aria-label="Breadcrumb" className="text-sm text-slate-500">
        <ol className="flex flex-wrap items-center gap-2">
          <li>
            <Link className="hover:text-brand-700" to="/">
              Home
            </Link>
          </li>
          <li aria-hidden="true">/</li>
          <li>
            <Link className="hover:text-brand-700" to={categoryPath}>
              {categoryLabel}
            </Link>
          </li>
          <li aria-hidden="true">/</li>
          <li aria-current="page" className="max-w-[18rem] truncate text-slate-700">
            {product.title}
          </li>
        </ol>
      </nav>

      <section className="mt-6 grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
        <Card className="p-5">
          <ProductImage
            src={product.image_url}
            alt={product.title}
            priority
            className="mx-auto max-w-xl"
          />
        </Card>
        <div>
          <div className="flex flex-wrap gap-2">
            <Badge tone="primary">{product.category || "Electronics"}</Badge>
            <Badge tone={fresh.tone}>{fresh.label}</Badge>
          </div>
          <h1 className="mt-4 text-3xl font-black leading-tight tracking-tight text-slate-950 sm:text-4xl">
            {product.title}
          </h1>
          <p className="mt-2 text-sm font-bold uppercase tracking-wider text-slate-500">
            {product.brand || "Brand unavailable"}
          </p>
          <Card className="mt-6 p-5">
            <p className="text-sm font-semibold text-slate-500">Best known price</p>
            <div className="price-numerals mt-1 text-4xl font-black text-slate-950">
              {formatPrice(product.best_price)}
            </div>
            <p className="mt-2 text-sm text-slate-600">
              {product.best_platform
                ? `Currently best known on ${product.best_platform}`
                : "No active platform price"}{" "}
              · {product.platform_count} platform{product.platform_count === 1 ? "" : "s"}
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => compare.add(product)}>
                <GitCompareArrows aria-hidden="true" className="h-4 w-4" />
                Add to compare
              </Button>
              <Link
                to={`/contact?topic=incorrect-match&product=${encodeURIComponent(absoluteUrl(`/products/${product.id}/${productSlug(product.title)}`))}`}
                className="inline-flex min-h-11 items-center rounded-xl px-4 text-sm font-bold text-slate-700 hover:bg-slate-100"
              >
                Report wrong product match
              </Link>
            </div>
          </Card>
          {rows.length > 0 ? (
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {rows.map(([label, value]) => (
                <div key={label} className="rounded-xl bg-slate-100 p-3">
                  <div className="text-xs font-bold uppercase tracking-wide text-slate-500">
                    {label}
                  </div>
                  <div className="mt-1 text-sm font-bold text-slate-950">{value}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-5 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
              Detailed specifications are not available for this product yet.
            </p>
          )}
        </div>
      </section>

      <section className="mt-12 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div>
          <h2 className="text-2xl font-black">Compare platform offers</h2>
          <p className="muted mt-2">
            Review current or last known prices and when each listing was last checked.
          </p>
          <div className="mt-5">
            <OffersList offers={offers} />
          </div>
        </div>
        <div className="space-y-5">
          <VerificationPanel productId={product.id} offerCount={offers.length} />
          <Insight detail={detail} history={history} />
          <Card className="p-5">
            <div className="flex gap-3">
              <AlertTriangle
                aria-hidden="true"
                className="mt-0.5 h-5 w-5 shrink-0 text-amber-600"
              />
              <p className="text-sm leading-6 text-slate-600">
                {sellerStatement} {priceDisclaimer}
              </p>
            </div>
          </Card>
        </div>
      </section>

      <section className="mt-12">
        <h2 className="text-2xl font-black">Price history</h2>
        <p className="muted mt-2">
          Recorded prices help you understand movement. Historical data does not guarantee a future
          price.
        </p>
        <Card className="mt-5 p-5">
          {history ? (
            <Suspense fallback={<Skeleton className="h-72" />}>
              <PriceHistoryChart history={history.history} />
            </Suspense>
          ) : (
            <div className="p-5 text-center">
              <h3 className="font-black">Price history unavailable</h3>
              <p className="mt-2 text-sm text-slate-600">
                {historyError
                  ? "This section could not be loaded."
                  : "No historical observations are available for this product yet."}
              </p>
            </div>
          )}
        </Card>
      </section>

      {similarVariants.length > 0 ? (
        <section className="mt-12">
          <h2 className="text-2xl font-black">Similar variants</h2>
          <p className="muted mt-2">
            These products may differ in RAM, storage, processor generation, colour, model suffix,
            screen, or another important specification.
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {similarVariants.map((variant) => (
              <ProductCard key={variant.id} product={variant} relationship="similar_variant" />
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}
