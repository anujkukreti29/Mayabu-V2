import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { Button } from "~/components/ui/button";
import { ProductImage } from "~/components/product/product-image";
import { useCompare } from "~/components/comparison/compare-provider";
import { searchProducts } from "~/lib/api/search";
import { searchKeys } from "~/lib/query/keys";
import { formatPrice } from "~/lib/formatting/price";

export function CompareSearch() {
  const compare = useCompare();
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const results = useQuery({
    queryKey: searchKeys.results({ q: query, limit: 6 }),
    queryFn: ({ signal }) => searchProducts({ q: query, limit: 6 }, signal),
    enabled: query.length >= 2,
    staleTime: 60_000,
  });

  return (
    <div className="surface p-5">
      <h2 className="font-black">Add a product</h2>
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
            className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400"
          />
          <input
            id="compare-search"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            minLength={2}
            maxLength={160}
            className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3"
            placeholder="Search model or product name"
          />
        </div>
        <Button type="submit">Search</Button>
      </form>
      {results.isFetching ? <p className="mt-4 text-sm text-slate-500">Searching Mayabu…</p> : null}
      {results.isError ? (
        <p className="mt-4 text-sm text-red-700">Search is temporarily unavailable.</p>
      ) : null}
      {results.data ? (
        <div className="mt-4 grid gap-2">
          {results.data.results.slice(0, 6).map((product) => {
            const selected = compare.has(product.id);
            return (
              <div
                key={product.id}
                className="flex items-center gap-3 rounded-xl border border-slate-200 p-3"
              >
                <ProductImage src={product.image_url} alt="" className="h-14 w-14 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold">{product.title}</p>
                  <p className="text-xs text-slate-500">{formatPrice(product.best_price)}</p>
                </div>
                <Button
                  size="sm"
                  variant={selected ? "outline" : "primary"}
                  disabled={selected || compare.products.length >= 4}
                  onClick={() => compare.add(product)}
                >
                  {selected ? "Added" : "Add"}
                </Button>
              </div>
            );
          })}
          {results.data.result_count === 0 ? (
            <p className="text-sm text-slate-500">No matching product found.</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
