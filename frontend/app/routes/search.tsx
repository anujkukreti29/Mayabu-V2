import { AlertTriangle, ArrowLeft, ArrowRight } from "lucide-react";
import { data, Link, useLoaderData } from "react-router";
import type { LoaderFunctionArgs, MetaFunction } from "react-router";
import { ProductCard } from "~/components/product/product-card";
import { SearchForm } from "~/components/search/search-form";
import { EmptyState } from "~/components/ui/empty-state";
import { ApiError } from "~/lib/api/errors";
import { searchProducts } from "~/lib/api/search";
import type { Relationship, SearchResponse } from "~/lib/api/schemas";
import { pageMeta, sanitizeMetaText } from "~/lib/seo/metadata";

interface SearchLoaderData {
  query: string;
  result: SearchResponse | null;
  error: string | null;
  cursor: string | null;
}

export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const query = (url.searchParams.get("q") ?? "").trim().slice(0, 160);
  const cursor = url.searchParams.get("cursor");
  const offset = Math.max(0, Math.min(5000, Number(url.searchParams.get("offset") ?? 0) || 0));
  if (!query) return data<SearchLoaderData>({ query: "", result: null, error: null, cursor });
  if (query.length < 2)
    return data<SearchLoaderData>(
      { query, result: null, error: "Enter a more specific product search.", cursor },
      { status: 400 },
    );
  try {
    const result = await searchProducts({ q: query, cursor, offset, limit: 20 }, request.signal);
    return data<SearchLoaderData>({ query, result, error: null, cursor });
  } catch (error) {
    const message =
      error instanceof ApiError && error.status === 429
        ? "Search is temporarily rate limited. Please wait briefly and try again."
        : "Mayabu could not reach the product service. Please try again in a moment.";
    return data<SearchLoaderData>(
      { query, result: null, error: message, cursor },
      { status: error instanceof ApiError && error.status ? error.status : 503 },
    );
  }
}

export const meta: MetaFunction<typeof loader> = ({ data: loaderData }) => {
  const query = sanitizeMetaText(loaderData?.query ?? "", 80);
  return pageMeta({
    title: query ? `Search Results for “${query}” | Mayabu` : "Search Electronics | Mayabu",
    description: query
      ? `Search Mayabu for ${query} and review exact matches, similar variants, and related products.`
      : "Search laptops, mobile phones, model numbers, and specifications with Mayabu.",
    path: query ? `/search?q=${encodeURIComponent(query)}` : "/search",
    robots: "noindex, follow",
  });
};

function Section({
  title,
  description,
  products,
  relationship,
}: {
  title: string;
  description: string;
  products: SearchResponse["results"];
  relationship: Relationship;
}) {
  if (products.length === 0) return null;
  return (
    <section className="mt-10" aria-labelledby={`${relationship}-heading`}>
      <div className="max-w-3xl">
        <h2 id={`${relationship}-heading`} className="text-2xl font-black text-slate-950">
          {title}
        </h2>
        <p className="muted mt-2">{description}</p>
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} relationship={relationship} />
        ))}
      </div>
    </section>
  );
}

export default function SearchPage() {
  const { query, result, error, cursor } = useLoaderData<typeof loader>();
  const previousOffset = result ? Math.max(0, result.offset - result.limit) : 0;
  return (
    <main id="main-content" className="page-container py-10">
      <div className="max-w-4xl">
        <SearchForm defaultValue={query} />
      </div>
      {!query ? (
        <div className="mt-10">
          <EmptyState
            title="Search for an electronics product"
            description="Enter a model name, model number, brand, processor, RAM, storage, or the type of product you need."
          />
        </div>
      ) : null}
      {error ? (
        <div className="mt-8 rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800">
          <div className="flex items-center gap-2 font-black">
            <AlertTriangle aria-hidden="true" className="h-5 w-5" />
            Search is temporarily unavailable
          </div>
          <p className="mt-2 text-sm">{error}</p>
        </div>
      ) : null}
      {result ? (
        <>
          <header className="mt-9">
            <p className="eyebrow">Product search</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">
              Search results for “{query}”
            </h1>
            <p className="mt-2 text-sm text-slate-600">
              {result.result_count} product{result.result_count === 1 ? "" : "s"} shown on this page
            </p>
            {result.detected_category ? (
              <p className="mt-1 text-xs text-slate-500">
                Detected category: {result.detected_category}
              </p>
            ) : null}
          </header>
          {result.result_count === 0 ? (
            <div className="mt-8">
              <EmptyState
                title="No matching product found"
                description={
                  result.message ??
                  "Try a shorter model name, remove one specification, or search for the product family instead."
                }
              />
            </div>
          ) : null}
          <Section
            title="Exact matches"
            description="The same product identity and configuration based on Mayabu's matching data."
            products={result.sections.exact_matches}
            relationship="exact_match"
          />
          <Section
            title="Similar variants"
            description="Related configurations with important backend-confirmed differences such as RAM, storage, colour, generation, or model suffix."
            products={result.sections.similar_variants}
            relationship="similar_variant"
          />
          <Section
            title="Related products"
            description="Alternative products that may fit a similar requirement but are not the same model or variant."
            products={result.sections.related_products}
            relationship="related_product"
          />
          <nav
            aria-label="Search pagination"
            className="mt-10 flex items-center justify-between gap-3"
          >
            {cursor || result.offset > 0 ? (
              <Link
                to={`/search?q=${encodeURIComponent(query)}&offset=${previousOffset}`}
                className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 text-sm font-bold"
              >
                <ArrowLeft aria-hidden="true" className="h-4 w-4" />
                Previous page
              </Link>
            ) : (
              <span />
            )}
            {result.has_more && result.next_cursor ? (
              <Link
                to={`/search?q=${encodeURIComponent(query)}&cursor=${encodeURIComponent(result.next_cursor)}`}
                className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-brand-600 px-4 text-sm font-bold text-white"
              >
                Load more products
                <ArrowRight aria-hidden="true" className="h-4 w-4" />
              </Link>
            ) : result.result_count > 0 ? (
              <p className="text-sm text-slate-500">You have reached the end of these results.</p>
            ) : null}
          </nav>
        </>
      ) : null}
    </main>
  );
}
