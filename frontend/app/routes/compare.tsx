import { Check, Copy, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { data, useLoaderData } from "react-router";
import type { LoaderFunctionArgs, MetaFunction } from "react-router";
import { CompareSearch } from "~/components/comparison/compare-search";
import { useCompare } from "~/components/comparison/compare-provider";
import { ProductImage } from "~/components/product/product-image";
import { Button } from "~/components/ui/button";
import { EmptyState } from "~/components/ui/empty-state";
import { getProduct } from "~/lib/api/products";
import type { Product } from "~/lib/api/schemas";
import { formatPrice } from "~/lib/formatting/price";
import { freshnessFrom } from "~/lib/formatting/freshness";
import { pageMeta } from "~/lib/seo/metadata";

export async function loader({ request }: LoaderFunctionArgs) {
  const raw = new URL(request.url).searchParams.get("products") ?? "";
  const ids = [
    ...new Set(
      raw
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean),
    ),
  ].slice(0, 4);
  const settled = await Promise.allSettled(ids.map((id) => getProduct(id, request.signal)));
  const products = settled.flatMap((result) =>
    result.status === "fulfilled" ? [result.value.product] : [],
  );
  return data({ products, requestedCount: ids.length });
}

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Compare Products | Mayabu",
    description:
      "Compare specifications, best known prices, retailer availability, price freshness, and recorded history for up to four products.",
    path: "/compare",
    robots: "noindex, follow",
  });

const specRows = [
  [
    "Processor",
    (product: Product) => product.specs.cpu_models?.join(", ") ?? product.specs.cpu_series,
  ],
  ["RAM", (product: Product) => (product.specs.ram_gb ? `${product.specs.ram_gb} GB` : undefined)],
  [
    "Storage",
    (product: Product) => (product.specs.storage_gb ? `${product.specs.storage_gb} GB` : undefined),
  ],
  ["Graphics", (product: Product) => product.specs.gpu],
  [
    "Screen",
    (product: Product) =>
      product.specs.screen_inch ? `${product.specs.screen_inch} inch` : undefined,
  ],
] as const;

export default function ComparePage() {
  const loaderData = useLoaderData<typeof loader>();
  const compare = useCompare();
  const [copied, setCopied] = useState(false);
  useEffect(() => loaderData.products.forEach(compare.add), [compare.add, loaderData.products]);
  const products = compare.products;
  const shareUrl = useMemo(() => {
    if (typeof window === "undefined") return "";
    const url = new URL(window.location.href);
    url.searchParams.set("products", products.map((product) => product.id).join(","));
    return url.toString();
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

  return (
    <main id="main-content" className="page-container py-10">
      <p className="eyebrow">Product comparison</p>
      <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
        Compare products side by side
      </h1>
      <p className="mt-3 max-w-3xl text-slate-600">
        Review specifications, best known prices, platform availability, price freshness, and
        important differences before choosing.
      </p>
      <div className="mt-8 grid gap-6 lg:grid-cols-[0.7fr_1.3fr]">
        <CompareSearch />
        <div>
          {products.length === 0 ? (
            <EmptyState
              title="Choose products to compare"
              description="Add two to four products from search results, product pages, or the search box on this page."
            />
          ) : (
            <>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm font-semibold text-slate-600">
                  {products.length} of 4 products selected
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => void copyLink()} disabled={!shareUrl}>
                    <Copy aria-hidden="true" className="h-4 w-4" />
                    {copied ? "Comparison link copied" : "Copy comparison link"}
                  </Button>
                  <Button variant="ghost" onClick={compare.clear}>
                    Clear comparison
                  </Button>
                </div>
              </div>
              <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-soft">
                <table className="w-full min-w-[48rem] border-collapse text-left">
                  <caption className="sr-only">Comparison of selected Mayabu products</caption>
                  <thead>
                    <tr>
                      <th
                        scope="col"
                        className="w-40 border-b border-r border-slate-200 bg-slate-50 p-4 text-sm"
                      >
                        Feature
                      </th>
                      {products.map((product) => (
                        <th
                          key={product.id}
                          scope="col"
                          className="min-w-52 border-b border-slate-200 p-4 align-top"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <span className="line-clamp-3 text-sm font-black">{product.title}</span>
                            <button
                              type="button"
                              onClick={() => compare.remove(product.id)}
                              className="grid h-11 w-11 shrink-0 place-items-center rounded-xl hover:bg-slate-100"
                              aria-label={`Remove ${product.title}`}
                            >
                              <X aria-hidden="true" className="h-4 w-4" />
                            </button>
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <th scope="row" className="border-r border-t border-slate-200 p-4 text-sm">
                        Product
                      </th>
                      {products.map((product) => (
                        <td key={product.id} className="border-t border-slate-200 p-4">
                          <ProductImage
                            src={product.image_url}
                            alt={product.title}
                            className="mx-auto h-36 w-36"
                          />
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <th scope="row" className="border-r border-t border-slate-200 p-4 text-sm">
                        Best known price
                      </th>
                      {products.map((product) => (
                        <td
                          key={product.id}
                          className="price-numerals border-t border-slate-200 p-4 text-xl font-black"
                        >
                          {formatPrice(product.best_price)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <th scope="row" className="border-r border-t border-slate-200 p-4 text-sm">
                        Best platform
                      </th>
                      {products.map((product) => (
                        <td key={product.id} className="border-t border-slate-200 p-4 text-sm">
                          {product.best_platform || "Unavailable"}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <th scope="row" className="border-r border-t border-slate-200 p-4 text-sm">
                        Freshness
                      </th>
                      {products.map((product) => (
                        <td key={product.id} className="border-t border-slate-200 p-4 text-sm">
                          {freshnessFrom(product.last_seen_at).label}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <th scope="row" className="border-r border-t border-slate-200 p-4 text-sm">
                        Platforms
                      </th>
                      {products.map((product) => (
                        <td key={product.id} className="border-t border-slate-200 p-4 text-sm">
                          {product.platform_count || "Unavailable"}
                        </td>
                      ))}
                    </tr>
                    {specRows.map(([label, value]) => (
                      <tr key={label}>
                        <th scope="row" className="border-r border-t border-slate-200 p-4 text-sm">
                          {label}
                        </th>
                        {products.map((product) => (
                          <td key={product.id} className="border-t border-slate-200 p-4 text-sm">
                            {value(product) ?? "Unavailable"}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {products.length < 2 ? (
                <p className="mt-4 flex items-center gap-2 text-sm text-amber-800">
                  <Check aria-hidden="true" className="h-4 w-4" />
                  Add at least one more product for a useful comparison.
                </p>
              ) : null}
            </>
          )}
        </div>
      </div>
    </main>
  );
}
