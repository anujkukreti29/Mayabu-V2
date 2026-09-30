import * as Dialog from "@radix-ui/react-dialog";
import { SlidersHorizontal, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { SearchFiltersPanel } from "~/components/search/search-filters";
import { buildSearchHref, type SearchUrlState } from "~/lib/search/url";

type FacetMap = Record<string, Array<{ value: string; count: number }>>;

export function SearchFiltersDrawer({
  state,
  facets,
}: {
  state: SearchUrlState;
  facets: FacetMap;
}) {
  const [open, setOpen] = useState(false);
  const activeCount =
    Object.keys(state.filters ?? {}).length +
    (state.minPrice != null ? 1 : 0) +
    (state.maxPrice != null ? 1 : 0);

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-medium text-ink hover:border-brand-300"
        >
          <SlidersHorizontal aria-hidden="true" className="h-4 w-4" />
          Filters
          {activeCount > 0 ? (
            <span className="rounded-full bg-brand-600 px-1.5 text-[11px] font-semibold text-white">
              {activeCount}
            </span>
          ) : null}
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="motion-safe:animate-in data-[state=closed]:motion-safe:animate-out fixed inset-0 z-[70] bg-slate-950/45" />
        <Dialog.Content className="fixed inset-y-0 right-0 z-[80] flex w-[min(100vw,24rem)] flex-col bg-white shadow-lift focus:outline-none">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <Dialog.Title className="text-base font-semibold text-ink">Filters</Dialog.Title>
            <Dialog.Description className="sr-only">
              Refine search results by price and product attributes
            </Dialog.Description>
            <Dialog.Close
              className="grid h-10 w-10 place-items-center rounded-lg text-slate-600 hover:bg-slate-100"
              aria-label="Close filters"
            >
              <X aria-hidden="true" className="h-5 w-5" />
            </Dialog.Close>
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-2">
            <SearchFiltersPanel state={state} facets={facets} showHeading={false} />
          </div>
          <div className="flex gap-2 border-t border-slate-100 p-4">
            <Link
              to={buildSearchHref(state, {
                filters: {},
                minPrice: null,
                maxPrice: null,
                resetOffset: true,
              })}
              className="inline-flex min-h-11 flex-1 items-center justify-center rounded-lg border border-slate-200 text-sm font-semibold text-slate-700"
              onClick={() => setOpen(false)}
            >
              Clear all
            </Link>
            <Dialog.Close asChild>
              <button
                type="button"
                className="inline-flex min-h-11 flex-1 items-center justify-center rounded-lg bg-brand-600 text-sm font-semibold text-white hover:bg-brand-700"
              >
                Show results
              </button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
