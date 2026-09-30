import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { Button } from "~/components/ui/button";
import { ProductImage } from "~/components/product/product-image";
import { compareBlockMessage, useCompare } from "~/components/comparison/compare-provider";
import { searchProducts } from "~/lib/api/search";
import { searchKeys } from "~/lib/query/keys";
import { formatPrice } from "~/lib/formatting/price";

export function CompareSearch({ lockedCategory }: { lockedCategory?: string | null }) {
  const compare = useCompare();
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const category = lockedCategory || compare.activeCategory || undefined;
  const results = useQuery({
    queryKey: searchKeys.results({ q: query, limit: 6, category: category ?? null }),
    queryFn: ({ signal }) =>
      searchProducts({ q: query, limit: 6, category: category || undefined }, signal),
    enabled: query.length >= 2,
    staleTime: 60_000,
  });

  return (
    <div className="rounded-md border border-line bg-white p-4 sm:p-5">
      <h2 className="text-base font-semibold text-ink">Add a product</h2>
      {category ? (
        <p className="mt-1 text-xs text-ink-muted">
          Searching within the current comparison category.
        </p>
      ) : null}
      <form
        className="mt-3 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(input.trim());
        }}
      >
        <label htmlFor="compare-search" className="sr-only">
          Search products to compare
        </label>
        <div className="relative min-w-0 flex-1">
          <Search
            aria-hidden="true"
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
          />
          <input
            id="compare-search"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            minLength={2}
            maxLength={160}
            className="min-h-10 w-full rounded-md border border-line pl-9 pr-3 text-sm"
            placeholder="Search model or product name"
          />
        </div>
        <Button type="submit">Search</Button>
      </form>
      {results.isFetching ? <p className="mt-4 text-sm text-ink-muted">Searching Mayabu…</p> : null}
      {results.isError ? (
        <p className="mt-4 text-sm text-red-700">Search is temporarily unavailable.</p>
      ) : null}
      {results.data ? (
        <div className="mt-4 grid gap-2">
          {results.data.results.slice(0, 6).map((product) => {
            const selected = compare.has(product.id);
            const reason = selected ? null : compare.compareBlockReason(product);
            const disabled = reason !== null;
            const title = compareBlockMessage(reason, compare.maxProducts) || undefined;
            return (
              <div
                key={product.id}
                className="flex items-center gap-3 rounded-md border border-line p-2.5"
              >
                <ProductImage
                  src={product.image_url}
                  alt=""
                  category={product.category}
                  variant="thumb"
                  frameClassName="h-14 w-14 shrink-0"
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink">{product.title}</p>
                  <p className="text-xs text-ink-muted">{formatPrice(product.best_price)}</p>
                </div>
                <Button
                  size="sm"
                  variant={selected ? "outline" : "primary"}
                  disabled={selected || disabled}
                  title={title}
                  onClick={() => compare.add(product)}
                >
                  {selected ? "Added" : disabled ? "Unavailable" : "Add"}
                </Button>
              </div>
            );
          })}
          {results.data.result_count === 0 ? (
            <p className="text-sm text-ink-muted">No matching product found.</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
