import { Check, Copy, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { data, Link, useLoaderData, useNavigate } from "react-router";
import type { LoaderFunctionArgs, MetaFunction } from "react-router";
import { CompareProductColumn } from "~/components/comparison/compare-product-column";
import { CompareSearch } from "~/components/comparison/compare-search";
import { CompareSpecTable } from "~/components/comparison/compare-spec-table";
import { useCompare } from "~/components/comparison/compare-provider";
import { Button } from "~/components/ui/button";
import { EmptyState } from "~/components/ui/empty-state";
import { comparePath, getCompareProducts, parseCompareIdsFromSearch } from "~/lib/api/compare";
import type { Product } from "~/lib/api/schemas";
import {
  filterCompareRows,
  keyDifferenceRows,
  payingExtraLine,
  presentCompareGroups,
  priceDifferenceLabel,
  resolveCompareRows,
  type CompareNavFilter,
} from "~/lib/comparison/spec-registry";
import { formatPrice } from "~/lib/formatting/price";
import { categoryDisplayName } from "~/lib/search/categories";
import { pageMeta, sanitizeMetaText } from "~/lib/seo/metadata";
import { cn } from "~/components/ui/cn";

interface CompareLoaderData {
  products: Product[];
  category: string | null;
  missingIds: string[];
  skipped: Array<{ id: string; reason: string; category?: string | null }>;
  warnings: string[];
  requestedCount: number;
}

export async function loader({ request }: LoaderFunctionArgs) {
  const ids = parseCompareIdsFromSearch(new URL(request.url).search);
  if (ids.length === 0) {
    return data<CompareLoaderData>({
      products: [],
      category: null,
      missingIds: [],
      skipped: [],
      warnings: [],
      requestedCount: 0,
    });
  }

  try {
    const payload = await getCompareProducts(ids, request.signal);
    return data<CompareLoaderData>({
      products: payload.products,
      category: payload.category ?? null,
      missingIds: payload.missing_ids,
      skipped: payload.skipped,
      warnings: payload.warnings,
      requestedCount: ids.length,
    });
  } catch (error) {
    console.error("[mayabu:compare]", {
      message: error instanceof Error ? error.message : "compare_failed",
    });
    return data<CompareLoaderData>({
      products: [],
      category: null,
      missingIds: ids,
      skipped: [],
      warnings: ["fetch_failed"],
      requestedCount: ids.length,
    });
  }
}

export const meta: MetaFunction<typeof loader> = ({ data: loaderData }) => {
  const products = loaderData?.products ?? [];
  let title = "Compare Products | Mayabu";
  if (products.length === 2) {
    const a = sanitizeMetaText(products[0]?.title || "Product A", 28);
    const b = sanitizeMetaText(products[1]?.title || "Product B", 28);
    title = `Compare ${a} vs ${b} | Mayabu`;
  }
  return pageMeta({
    title,
    description:
      "Compare specifications, best known prices, retailer coverage, and freshness for products in the same category.",
    path: "/compare",
    robots: "noindex, follow",
  });
};

export default function ComparePage() {
  const loaderData = useLoaderData<typeof loader>();
  const compare = useCompare();
  const { add, remove, clear, activeCategory, products: trayProducts } = compare;
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);
  const [navFilter, setNavFilter] = useState<CompareNavFilter>("key_differences");

  useEffect(() => {
    loaderData.products.forEach((product) => add(product));
  }, [add, loaderData.products]);

  const products =
    loaderData.products.length > 0
      ? loaderData.products
      : trayProducts.filter((product) =>
          loaderData.category
            ? (product.category || "").toLowerCase() === loaderData.category
            : true,
        );

  function removeProduct(productId: string) {
    remove(productId);
    const next = products
      .filter((product) => product.id !== productId)
      .map((product) => product.id);
    void navigate(comparePath(next), { replace: true });
  }

  function selectNav(next: CompareNavFilter) {
    setNavFilter(next);
    if (next === "price") {
      document.getElementById("compare-price-heading")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      return;
    }
    document.getElementById("compare-specs")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  const category = loaderData.category || products[0]?.category || activeCategory;
  const categoryLabel = categoryDisplayName(category);
  const allRows = useMemo(() => resolveCompareRows(category, products), [category, products]);
  const keyRows = useMemo(() => keyDifferenceRows(allRows, 6), [allRows]);
  const specGroups = useMemo(() => presentCompareGroups(allRows), [allRows]);
  const tableRows = useMemo(() => {
    if (navFilter === "key_differences") return keyRows;
    if (navFilter === "price") return allRows;
    return filterCompareRows(allRows, navFilter);
  }, [allRows, keyRows, navFilter]);
  const extraLine = useMemo(() => payingExtraLine(products, keyRows), [products, keyRows]);

  const cheapest =
    products.length >= 2
      ? Math.min(
          ...products
            .map((product) => product.best_price)
            .filter((price): price is number => typeof price === "number" && price > 0),
        )
      : null;
  const spread = priceDifferenceLabel(products);

  const shareUrl = useMemo(() => {
    if (typeof window === "undefined") return "";
    return new URL(
      comparePath(products.map((product) => product.id)),
      window.location.origin,
    ).toString();
  }, [products]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  const addAnotherHref = category ? `/search?category=${encodeURIComponent(category)}` : "/search";
  const navItems: Array<{ id: CompareNavFilter; label: string }> = [
    { id: "key_differences", label: "Key differences" },
    { id: "price", label: "Price" },
    { id: "all", label: "All specs" },
    ...specGroups.map((group) => ({ id: group, label: group })),
  ];

  return (
    <main id="main-content" className="pb-28 sm:pb-24">
      <div className="border-b border-line bg-white">
        <div className="page-container py-6 sm:py-8">
          <nav aria-label="Breadcrumb" className="text-xs text-ink-muted">
            <Link to="/" className="hover:text-ink">
              Home
            </Link>
            <span aria-hidden="true"> / </span>
            <span className="text-ink">Compare</span>
            {categoryLabel ? (
              <>
                <span aria-hidden="true"> / </span>
                <span className="text-ink">{categoryLabel}</span>
              </>
            ) : null}
          </nav>
          <p className="eyebrow mt-3">Side-by-side comparison</p>
          <h1 className="mt-2 max-w-3xl text-display text-ink">Compare products side by side</h1>
          <p className="mt-2 max-w-2xl text-body-lg text-ink-muted">
            Review meaningful spec differences, current best prices, and retailer coverage for
            products in the same category.
          </p>
        </div>
      </div>

      <div className="page-container py-6 sm:py-8">
        {loaderData.missingIds.length > 0 || loaderData.skipped.length > 0 ? (
          <div
            role="status"
            className="mb-5 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950"
          >
            {loaderData.missingIds.length > 0
              ? `${loaderData.missingIds.length} product${loaderData.missingIds.length === 1 ? "" : "s"} could not be loaded. `
              : null}
            {loaderData.skipped.some((item) => item.reason === "category_mismatch")
              ? "Some products were skipped because comparison is same-category only."
              : null}
          </div>
        ) : null}

        {products.length === 0 ? (
          <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
            <EmptyState
              title="Compare products side by side"
              description="Choose products from the same category using Search, product pages, or the search box here."
            />
            <CompareSearch lockedCategory={activeCategory} />
          </div>
        ) : null}

        {products.length === 1 ? (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,18rem)_1fr]">
            <CompareProductColumn
              product={products[0]!}
              onRemove={() => removeProduct(products[0]!.id)}
            />
            <div className="rounded-md border border-dashed border-line bg-page/60 p-5">
              <h2 className="text-lg font-semibold text-ink">Add another product</h2>
              <p className="mt-1 text-sm text-ink-muted">
                Comparison needs at least two products from the same category to show differences.
              </p>
              <Link
                to={addAnotherHref}
                className="mt-4 inline-flex min-h-10 items-center gap-1.5 rounded-md bg-brand-600 px-3.5 text-sm font-semibold text-white hover:bg-brand-700"
              >
                <Plus aria-hidden="true" className="h-4 w-4" />
                Add another {categoryLabel || "product"}
              </Link>
              <div className="mt-6">
                <CompareSearch lockedCategory={category} />
              </div>
            </div>
          </div>
        ) : null}

        {products.length >= 2 ? (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-ink">
                  {products.length} {categoryLabel || "products"} selected
                  {spread ? ` · up to ${spread} apart` : ""}
                </p>
                <p className="mt-0.5 text-xs text-ink-muted">
                  Same-category comparison · public offers only
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => void copyLink()} disabled={!shareUrl}>
                  <Copy aria-hidden="true" className="h-4 w-4" />
                  {copied ? "Link copied" : "Copy comparison link"}
                </Button>
                <Link
                  to={addAnotherHref}
                  className="inline-flex min-h-10 items-center gap-1.5 rounded-md border border-line px-3 text-sm font-semibold text-ink transition hover:bg-slate-50"
                >
                  <Plus aria-hidden="true" className="h-4 w-4" />
                  Add another
                </Link>
                <Button
                  variant="ghost"
                  onClick={() => {
                    clear();
                    void navigate("/compare", { replace: true });
                  }}
                >
                  Clear
                </Button>
              </div>
            </div>

            <section aria-labelledby="compare-products-heading">
              <h2 id="compare-products-heading" className="sr-only">
                Compared products
              </h2>
              <div
                className={cn(
                  "relative -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0",
                  "sm:grid sm:gap-4",
                  products.length === 2 && "sm:grid-cols-2 lg:max-w-4xl",
                  products.length === 3 && "sm:grid-cols-3",
                  products.length >= 4 && "sm:grid-cols-2 lg:grid-cols-4",
                )}
              >
                <div
                  className="pointer-events-none absolute inset-y-0 right-0 hidden w-8 bg-gradient-to-l from-page to-transparent max-sm:block"
                  aria-hidden="true"
                />
                <div className="flex min-w-max gap-4 sm:contents">
                  {products.map((product) => {
                    const delta =
                      cheapest != null &&
                      product.best_price != null &&
                      product.best_price === cheapest &&
                      spread
                        ? spread
                        : null;
                    return (
                      <CompareProductColumn
                        key={product.id}
                        product={product}
                        onRemove={() => removeProduct(product.id)}
                        priceDeltaLabel={delta}
                        sticky
                      />
                    );
                  })}
                </div>
              </div>
            </section>

            <section
              id="compare-price"
              aria-labelledby="compare-price-heading"
              className="rounded-md border border-line bg-white p-4"
            >
              <h2 id="compare-price-heading" className="text-base font-semibold text-ink">
                Price & offers
              </h2>
              {extraLine ? <p className="mt-2 text-sm text-ink-soft">{extraLine}</p> : null}
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[28rem] text-left text-sm">
                  <caption className="sr-only">Price and offer summary</caption>
                  <thead>
                    <tr className="border-b border-line text-xs uppercase tracking-wide text-ink-muted">
                      <th className="py-2 pr-3 font-semibold">Metric</th>
                      {products.map((product) => (
                        <th key={product.id} className="px-2 py-2 font-semibold text-ink">
                          <span className="line-clamp-1">{product.brand || product.title}</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-t border-line">
                      <th scope="row" className="py-2.5 pr-3 font-medium">
                        Best price
                      </th>
                      {products.map((product) => (
                        <td key={product.id} className="price-numerals px-2 py-2.5 font-bold">
                          {formatPrice(product.best_price)}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-t border-line">
                      <th scope="row" className="py-2.5 pr-3 font-medium">
                        Public offers
                      </th>
                      {products.map((product) => (
                        <td key={product.id} className="px-2 py-2.5">
                          {product.platform_count ?? product.offer_count ?? "—"}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <section id="compare-specs" aria-labelledby="compare-specs-heading" className="space-y-3">
              <div>
                <h2 id="compare-specs-heading" className="text-base font-semibold text-ink">
                  Specifications
                </h2>
                <p className="mt-1 text-sm text-ink-muted">
                  Jump to key differences, price, or category groups. Differing rows use neutral
                  emphasis only.
                </p>
              </div>

              <div
                role="toolbar"
                aria-label="Compare specification filters"
                className="flex flex-wrap gap-2"
              >
                {navItems.map((item) => {
                  const active = navFilter === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      aria-pressed={active}
                      onClick={() => selectNav(item.id)}
                      className={cn(
                        "inline-flex min-h-9 items-center rounded-md border px-3 text-sm font-medium transition",
                        active
                          ? "border-brand-600 bg-brand-50 text-brand-800"
                          : "border-line bg-white text-ink-soft hover:bg-slate-50",
                      )}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>

              {navFilter === "price" ? (
                <p className="rounded-md border border-line bg-white px-3 py-4 text-sm text-ink-muted">
                  See Price &amp; offers above for current listed prices and offer counts.
                </p>
              ) : tableRows.length > 0 ? (
                <CompareSpecTable
                  products={products}
                  rows={tableRows}
                  caption={
                    navFilter === "key_differences"
                      ? "Key specification differences"
                      : navFilter === "all"
                        ? "Full specification comparison"
                        : `${navFilter} specifications`
                  }
                  tableId="compare-spec-table"
                />
              ) : (
                <p className="rounded-md border border-line bg-white px-3 py-4 text-sm text-ink-muted">
                  {navFilter === "key_differences"
                    ? "No differing specification rows for these products."
                    : "No comparable specifications available yet."}
                </p>
              )}
            </section>

            <p className="flex items-start gap-2 text-xs text-ink-muted">
              <Check aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Mayabu highlights differences so you can judge trade-offs. It does not declare a
              universal winner.
            </p>
          </div>
        ) : null}
      </div>
    </main>
  );
}
