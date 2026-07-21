import { GitCompareArrows, X } from "lucide-react";
import { Link } from "react-router";
import { useCompare } from "~/components/comparison/compare-provider";

export function CompareDock() {
  const compare = useCompare();
  if (compare.products.length === 0) return null;
  const query = compare.products.map((product) => product.id).join(",");
  return (
    <aside
      aria-label="Product comparison"
      className="fixed bottom-4 left-1/2 z-40 w-[min(94vw,48rem)] -translate-x-1/2 rounded-2xl border border-slate-200 bg-white p-3 shadow-2xl"
    >
      <div className="flex items-center gap-3">
        <div className="hidden h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-700 sm:grid">
          <GitCompareArrows aria-hidden="true" className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold">{compare.products.length} of 4 products selected</p>
          <p className="truncate text-xs text-slate-500">
            {compare.products.map((product) => product.title).join(" · ")}
          </p>
        </div>
        <button
          type="button"
          className="grid h-11 w-11 place-items-center rounded-xl text-slate-600 hover:bg-slate-100"
          onClick={compare.clear}
          aria-label="Clear comparison"
        >
          <X aria-hidden="true" className="h-5 w-5" />
        </button>
        <Link
          to={`/compare?products=${encodeURIComponent(query)}`}
          className="inline-flex min-h-11 items-center rounded-xl bg-brand-600 px-4 text-sm font-bold text-white hover:bg-brand-700"
        >
          Compare
        </Link>
      </div>
    </aside>
  );
}
