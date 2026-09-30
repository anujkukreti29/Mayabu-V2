import { useId, useState } from "react";
import { ChevronDown, Clock3, Store, TrendingDown } from "lucide-react";
import { formatPrice } from "~/lib/formatting/price";
import type { PriceEvidenceModel } from "~/lib/product/price-evidence";
import { cn } from "~/components/ui/cn";

export function PriceEvidencePanel({ evidence }: { evidence: PriceEvidenceModel }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  if (evidence.storeCount === 0 && evidence.bestPrice == null) return null;

  return (
    <div className="surface overflow-hidden">
      <button
        type="button"
        className="flex w-full items-start justify-between gap-3 px-4 py-3.5 text-left transition duration-instant hover:bg-surface-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-inset"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="min-w-0">
          <span className="eyebrow">Price evidence</span>
          {evidence.bestPrice != null ? (
            <span className="mt-1 block">
              <span className="price-numerals text-xl font-bold text-ink">
                {formatPrice(evidence.bestPrice)}
              </span>
              <span className="ml-2 text-sm text-ink-muted">Best current listed price</span>
            </span>
          ) : null}
          <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-soft">
            {evidence.storeCount > 0 ? (
              <span className="inline-flex items-center gap-1.5">
                <Store className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
                {evidence.storeCount} store{evidence.storeCount === 1 ? "" : "s"} compared
              </span>
            ) : null}
            <span className="inline-flex items-center gap-1.5">
              <Clock3 className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
              {evidence.checkedCount > 0
                ? `Checked ${evidence.checkedCount} of ${evidence.storeCount}`
                : evidence.freshnessLabel}
            </span>
            {evidence.lowestSinceTracking != null ? (
              <span className="inline-flex items-center gap-1.5">
                <TrendingDown className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
                Lowest since tracking {formatPrice(evidence.lowestSinceTracking)}
              </span>
            ) : null}
          </span>
        </span>
        <ChevronDown
          aria-hidden="true"
          className={cn(
            "mt-1 h-4 w-4 shrink-0 text-ink-muted transition duration-smooth",
            open && "rotate-180",
          )}
        />
      </button>
      {open ? (
        <div id={panelId} className="border-t border-line bg-surface-muted/40 px-4 py-4 text-sm">
          {evidence.priceMovement ? (
            <p className="mb-3 text-sm font-medium text-ink-soft">{evidence.priceMovement}</p>
          ) : null}

          {evidence.timeline.length > 0 ? (
            <div className="mb-4">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                Recent checks
              </p>
              <ol className="mt-2 space-y-2">
                {evidence.timeline.map((store) => (
                  <li
                    key={`${store.platform}-${store.checkedAt || "none"}`}
                    className="flex items-start justify-between gap-3 border-l-2 border-line pl-3"
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-ink">{store.label}</p>
                      <p className="text-ink-muted">{store.timelineNote}</p>
                    </div>
                    <p className="price-numerals shrink-0 font-semibold text-ink">
                      {store.price != null ? formatPrice(store.price) : "—"}
                    </p>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}

          {evidence.stores.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[20rem] text-left">
                <caption className="sr-only">Store price evidence</caption>
                <thead>
                  <tr className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                    <th className="pb-2 pr-3 font-semibold">Store</th>
                    <th className="pb-2 pr-3 font-semibold">Price</th>
                    <th className="pb-2 pr-3 font-semibold">Checked</th>
                    <th className="pb-2 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {evidence.stores.map((store) => (
                    <tr key={store.platform} className="border-t border-line">
                      <td className="py-2.5 pr-3 font-medium text-ink">{store.label}</td>
                      <td className="price-numerals py-2.5 pr-3 font-semibold text-ink">
                        {store.price != null ? formatPrice(store.price) : "—"}
                      </td>
                      <td className="py-2.5 pr-3 text-ink-muted">
                        {store.checkedAt ? store.freshnessLabel : "—"}
                      </td>
                      <td className="py-2.5 text-ink-muted">{store.statusLabel}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function DecisionSnapshot({ facts }: { facts: readonly string[] }) {
  if (facts.length === 0) return null;
  return (
    <div className="surface bg-white p-4">
      <p className="eyebrow">Decision snapshot</p>
      <ul className="mt-2.5 space-y-1.5 text-sm text-ink">
        {facts.map((fact) => (
          <li key={fact} className="flex gap-2">
            <span aria-hidden="true" className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent" />
            <span>{fact}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
