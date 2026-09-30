import { AlertTriangle } from "lucide-react";
import { data, Link, useLoaderData, useNavigation } from "react-router";
import type { LoaderFunctionArgs, MetaFunction } from "react-router";
import { ProductCard } from "~/components/product/product-card";
import { WishlistStatusBootstrap } from "~/components/product/wishlist-status-bootstrap";
import { SearchActiveFilters } from "~/components/search/search-active-filters";
import { SearchCategorySelect } from "~/components/search/search-category-select";
import { SearchNoQueryState, SearchNoResultsState } from "~/components/search/search-empty-state";
import { SearchFiltersDrawer } from "~/components/search/search-filters-drawer";
import { SearchFiltersPanel } from "~/components/search/search-filters";
import { SearchPendingBar } from "~/components/search/search-pending-bar";
import { SearchPagination } from "~/components/search/search-pagination";
import { SearchResultsHeader } from "~/components/search/search-results-header";
import { SearchSortSelect } from "~/components/search/search-sort-select";
import { SearchForm } from "~/components/search/search-form";
import { SearchResultsSkeleton, Skeleton } from "~/components/ui/skeleton";
import { ApiError } from "~/lib/api/errors";
import { searchProducts } from "~/lib/api/search";
import type { Relationship, SearchResponse } from "~/lib/api/schemas";
import { pageMeta, sanitizeMetaText } from "~/lib/seo/metadata";
import {
  buildSearchHref,
  parseSearchUrl,
  serializeFiltersParam,
  type SearchUrlState,
} from "~/lib/search/url";
import { cn } from "~/components/ui/cn";

interface SearchLoaderData {
  state: SearchUrlState;
  result: SearchResponse | null;
  error: string | null;
  errorKind: "none" | "validation" | "filters" | "service";
}

export function HydrateFallback() {
  return (
    <div className="commerce-container py-6 sm:py-8" aria-busy="true" aria-label="Loading search">
      <Skeleton className="h-12 w-full max-w-2xl rounded-lg lg:hidden" />
      <div className="mt-6">
        <SearchResultsSkeleton count={8} />
      </div>
    </div>
  );
}

export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const state = parseSearchUrl(url);
  if (!state.q) {
    return data<SearchLoaderData>({
      state,
      result: null,
      error: null,
      errorKind: "none",
    });
  }
  if (state.q.length < 2) {
    return data<SearchLoaderData>(
      {
        state,
        result: null,
        error: "Enter a more specific product search.",
        errorKind: "validation",
      },
      { status: 400 },
    );
  }
  try {
    const result = await searchProducts(
      {
        q: state.q,
        cursor: state.cursor,
        offset: state.offset ?? 0,
        limit: 20,
        category: state.category,
        sort: state.sort,
        minPrice: state.minPrice,
        maxPrice: state.maxPrice,
        filters: state.filters,
      },
      request.signal,
    );
    return data<SearchLoaderData>({ state, result, error: null, errorKind: "none" });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 400 || error.status === 422)) {
      return data<SearchLoaderData>(
        {
          state,
          result: null,
          error: "Those filters are not valid for this search. Clear them and try again.",
          errorKind: "filters",
        },
        { status: 400 },
      );
    }
    const isRateLimited = error instanceof ApiError && error.status === 429;
    const isNetwork =
      error instanceof ApiError &&
      (error.category === "network" || error.category === "timeout" || error.status === 0);
    const isServer =
      error instanceof ApiError && (error.category === "server" || (error.status ?? 0) >= 500);
    console.error("[mayabu:search]", {
      status: error instanceof ApiError ? error.status : null,
      category: error instanceof ApiError ? error.category : "unknown",
      requestId: error instanceof ApiError ? error.requestId : null,
      queryLength: state.q.length,
    });
    const message = isRateLimited
      ? "Search is temporarily rate limited. Please wait briefly and try again."
      : isNetwork || isServer || !(error instanceof ApiError)
        ? "Mayabu could not reach the product service. Please try again in a moment."
        : "Mayabu could not complete this search. Please adjust your query and try again.";
    return data<SearchLoaderData>(
      {
        state,
        result: null,
        error: message,
        errorKind: "service",
      },
      {
        status: error instanceof ApiError && error.status ? error.status : isNetwork ? 503 : 503,
      },
    );
  }
}

export const meta: MetaFunction<typeof loader> = ({ data: loaderData }) => {
  const query = sanitizeMetaText(loaderData?.state.q ?? "", 80);
  return pageMeta({
    title: query ? `Search Results for “${query}” | Mayabu` : "Search Products | Mayabu",
    description: query
      ? `Search Mayabu for ${query} and compare products, specs, and store prices.`
      : "Search products, models, brands, and categories across Mayabu’s comparison catalog.",
    path: query ? `/search?q=${encodeURIComponent(query)}` : "/search",
    robots: "noindex, follow",
  });
};

function Section({
  title,
  description,
  products,
  relationship,
  showCategoryBadge,
}: {
  title: string;
  description: string;
  products: SearchResponse["results"];
  relationship: Relationship;
  showCategoryBadge: boolean;
}) {
  if (products.length === 0) return null;
  return (
    <section className="mt-8" aria-labelledby={`${relationship}-heading`}>
      <div className="max-w-3xl">
        <h2 id={`${relationship}-heading`} className="text-title-sm text-ink">
          {title}
        </h2>
        <p className="mt-1 text-sm text-ink-muted">{description}</p>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {products.map((product) => (
          <ProductCard
            key={product.id}
            product={product}
            relationship={relationship}
            showCategoryBadge={showCategoryBadge}
          />
        ))}
      </div>
    </section>
  );
}

export default function SearchPage() {
  const { state, result, error, errorKind } = useLoaderData<typeof loader>();
  const navigation = useNavigation();
  const pending = navigation.state === "loading" && navigation.location?.pathname === "/search";
  const query = state.q;
  const mixed =
    Boolean(result) &&
    !state.category &&
    (result?.search_mode === "cross_category" ||
      Object.keys(result?.category_counts ?? {}).length > 1);

  const hiddenFields = {
    category: state.category ?? undefined,
    sort: state.sort && state.sort !== "relevance" ? String(state.sort) : undefined,
    min_price: state.minPrice != null ? String(state.minPrice) : undefined,
    max_price: state.maxPrice != null ? String(state.maxPrice) : undefined,
    filters: serializeFiltersParam(state.filters) ?? undefined,
  };

  const clearFiltersHref = buildSearchHref(state, {
    filters: {},
    minPrice: null,
    maxPrice: null,
    category: null,
    resetOffset: true,
  });

  const wishlistIds = result?.results.map((product) => product.id) ?? [];

  return (
    <main id="main-content" className="commerce-container py-6 sm:py-8">
      <WishlistStatusBootstrap productIds={wishlistIds} />
      <div className="lg:hidden" data-testid="search-page-query">
        <SearchForm defaultValue={query} hiddenFields={hiddenFields} inputId="search-page-query" />
      </div>

      {query ? (
        <div className="mt-4 flex flex-wrap items-end gap-2 lg:mt-0">
          <div className="lg:hidden">
            <SearchFiltersDrawer state={state} facets={result?.facets ?? {}} />
          </div>
          <div className="min-w-[9.5rem] flex-1 sm:max-w-[13rem] lg:max-w-[11rem]">
            <SearchCategorySelect state={state} publicCategories={result?.public_categories} />
          </div>
          <div className="min-w-[9.5rem] flex-1 sm:max-w-[13rem] lg:max-w-[12rem]">
            <SearchSortSelect state={state} />
          </div>
        </div>
      ) : null}

      <SearchPendingBar />

      <div
        className={cn(
          pending && "opacity-70 transition-opacity duration-snappy ease-mayabu motion-reduce:transition-none",
        )}
        aria-busy={pending || undefined}
      >
        {pending && query && !result ? <SearchResultsSkeleton /> : null}

        {!query ? <SearchNoQueryState /> : null}

        {error ? (
          <div
            className="mt-8 rounded-xl border border-red-200 bg-red-50 p-5 text-red-800"
            role="alert"
          >
            <div className="flex items-center gap-2 text-sm font-semibold">
              <AlertTriangle aria-hidden="true" className="h-5 w-5" />
              {errorKind === "filters" ? "Invalid filters" : "Search is temporarily unavailable"}
            </div>
            <p className="mt-2 text-sm">{error}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {errorKind === "filters" ? (
                <Link
                  to={clearFiltersHref}
                  className="inline-flex min-h-11 items-center rounded-lg border border-red-300 bg-white px-4 text-sm font-semibold text-red-800"
                >
                  Clear invalid filters
                </Link>
              ) : null}
              <Link
                to={buildSearchHref(state)}
                className="inline-flex min-h-11 items-center rounded-lg border border-red-300 bg-white px-4 text-sm font-semibold text-red-800"
              >
                Try again
              </Link>
            </div>
          </div>
        ) : null}

        {result ? (
          <div className="mt-6 lg:mt-8 lg:grid lg:grid-cols-[15.5rem_minmax(0,1fr)] lg:gap-8 xl:grid-cols-[16.5rem_minmax(0,1fr)]">
            <aside className="hidden lg:block">
              <div className="sticky top-20 max-h-[calc(100vh-6rem)] overflow-y-auto pr-1">
                <SearchFiltersPanel state={state} facets={result.facets ?? {}} />
              </div>
            </aside>

            <div className="min-w-0">
              <div className="border-b border-line pb-4">
                <SearchResultsHeader query={query} result={result} state={state} />
              </div>

              <div className="mt-3">
                <SearchActiveFilters state={state} />
              </div>

              {result.result_count === 0 ? (
                <SearchNoResultsState query={query} message={result.message} state={state} />
              ) : null}

              <Section
                title="Exact matches"
                description="Same product identity and configuration."
                products={result.sections.exact_matches}
                relationship="exact_match"
                showCategoryBadge={Boolean(mixed)}
              />
              <Section
                title="Similar variants"
                description="Related configurations with meaningful differences."
                products={result.sections.similar_variants}
                relationship="similar_variant"
                showCategoryBadge={Boolean(mixed)}
              />
              <Section
                title="Related products"
                description="Alternatives that may fit a similar need."
                products={result.sections.related_products}
                relationship="related_product"
                showCategoryBadge={Boolean(mixed)}
              />

              <SearchPagination
                state={state}
                offset={result.offset}
                limit={result.limit}
                hasMore={result.has_more}
                hasResults={result.result_count > 0}
              />
            </div>
          </div>
        ) : null}
      </div>
    </main>
  );
}
