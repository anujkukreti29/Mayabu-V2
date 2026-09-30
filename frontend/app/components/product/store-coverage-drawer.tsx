import { useEffect, useId, useState } from "react";
import { Badge } from "~/components/ui/badge";
import { formatPrice, validPrice } from "~/lib/formatting/price";
import { freshnessFrom } from "~/lib/formatting/freshness";
import { isStockStatusTrustworthy, uniqueOffersByPlatform } from "~/lib/product/detail-view";
import { platformDisplayName } from "~/lib/search/platforms";
import type { Offer } from "~/lib/api/schemas";
import { cn } from "~/components/ui/cn";

function offerPrice(offer: Offer): number | null {
  const price = validPrice(offer.effective_price) ? offer.effective_price : offer.price;
  return validPrice(price) ? price : null;
}

/**
 * Compact interactive summary for “N stores compared” on PDP.
 * Does not duplicate the full Offers list — links into #offers instead.
 */
export function StoreCoverageDrawer({
  offers,
  className,
}: {
  offers: Offer[];
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (offers.length === 0) return null;

  const unique = uniqueOffersByPlatform(offers);
  if (unique.length === 0) return null;

  const label = `${unique.length} store${unique.length === 1 ? "" : "s"} compared`;

  return (
    <div className={cn("relative mt-3 text-sm", className)}>
      <button
        type="button"
        className="font-medium text-ink-soft underline-offset-2 hover:text-ink hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        {label}
      </button>
      {open ? (
        <div
          id={panelId}
          role="region"
          aria-label="Store coverage summary"
          className="absolute left-0 right-0 z-dropdown mt-2 max-h-64 overflow-y-auto rounded-md border border-line bg-white p-3 shadow-lift sm:right-auto sm:w-[22rem]"
        >
          <ul className="space-y-2.5">
            {unique.map((offer) => {
              const retailer = platformDisplayName(offer.platform) || "Retailer";
              const price = offerPrice(offer);
              const lastSuccess = offer.last_verified_at || null;
              const lastAttempt = offer.last_checked_at || null;
              const failures = offer.verification_failures || 0;
              const attemptFailed =
                failures > 0 &&
                Boolean(lastAttempt) &&
                (!lastSuccess || Date.parse(lastAttempt!) > Date.parse(lastSuccess) + 1000);
              const fresh = freshnessFrom(lastSuccess);
              const stock = (offer.stock_status ?? "").toLowerCase();
              const showStock = isStockStatusTrustworthy(offer.stock_status);
              const outOfStock = stock === "out_of_stock" || stock === "unavailable";
              const statusLine = attemptFailed
                ? lastSuccess
                  ? `Latest refresh unavailable · last successful check ${fresh.label.replace(/^Checked\s+/i, "")}`
                  : "Latest refresh unavailable"
                : fresh.label;
              return (
                <li key={offer.id} className="flex items-start justify-between gap-3 text-sm">
                  <div className="min-w-0">
                    <p className="font-semibold text-ink">{retailer}</p>
                    <p
                      className={cn(
                        "mt-0.5 text-xs",
                        attemptFailed || fresh.tone === "warning" ? "text-amber-800" : "text-ink-muted",
                      )}
                    >
                      {statusLine}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="price-numerals font-bold text-ink">
                      {outOfStock && price != null ? (
                        <span className="text-ink-muted">Last known {formatPrice(price)}</span>
                      ) : (
                        formatPrice(price)
                      )}
                    </p>
                    {showStock ? (
                      <Badge
                        tone={outOfStock ? "danger" : "success"}
                        className="mt-1 normal-case tracking-normal"
                      >
                        {outOfStock ? "Out of stock" : "In stock"}
                      </Badge>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
          <a
            href="#offers"
            className="mt-3 inline-flex min-h-9 items-center text-sm font-semibold text-brand-700 hover:text-brand-800"
            onClick={() => setOpen(false)}
          >
            View all offers
          </a>
        </div>
      ) : null}
    </div>
  );
}
