import { ExternalLink } from "lucide-react";
import { Badge } from "~/components/ui/badge";
import { formatPrice, validDiscount, validPrice } from "~/lib/formatting/price";
import { freshnessFrom } from "~/lib/formatting/freshness";
import {
  bestOfferIds,
  isStockStatusTrustworthy,
  uniqueOffersByPlatform,
} from "~/lib/product/detail-view";
import { platformDisplayName } from "~/lib/search/platforms";
import { safeRetailerUrl } from "~/lib/security/external-url";
import { recordProductActivity } from "~/lib/api/activity";
import type { Offer } from "~/lib/api/schemas";
import { cn } from "~/components/ui/cn";

function offerPrice(offer: Offer): number | null {
  const price = validPrice(offer.effective_price) ? offer.effective_price : offer.price;
  return validPrice(price) ? price : null;
}

function OfferRow({
  offer,
  isBest,
  productId,
}: {
  offer: Offer;
  isBest: boolean;
  productId?: string;
}) {
  const price = offerPrice(offer);
  const discount = validDiscount(price, offer.mrp, offer.discount_percent);
  const fresh = freshnessFrom(offer.last_verified_at ?? offer.last_checked_at);
  const url = safeRetailerUrl(offer.url);
  const retailer = platformDisplayName(offer.platform) || "Retailer";
  const stock = (offer.stock_status ?? "").toLowerCase();
  const showStock = isStockStatusTrustworthy(offer.stock_status);
  const outOfStock = stock === "out_of_stock" || stock === "unavailable";

  return (
    <li
      className={cn(
        "rounded-md border border-line bg-white px-3.5 py-3.5 sm:px-4",
        "transition duration-standard ease-mayabu",
        "motion-safe:hover:border-brand-200 motion-safe:hover:bg-brand-50/40",
        isBest && "border-brand-300 bg-brand-50/50",
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink sm:text-[0.95rem]">{retailer}</p>
            {isBest ? (
              <Badge tone="success" aria-label="Best current price">
                Best price
              </Badge>
            ) : null}
            {showStock ? (
              <Badge tone={outOfStock ? "danger" : "success"}>
                {outOfStock ? "Out of stock" : "In stock"}
              </Badge>
            ) : null}
          </div>
          <p
            className={cn(
              "mt-1 text-xs",
              fresh.tone === "warning" ? "text-amber-800" : "text-ink-muted",
            )}
          >
            {fresh.label}
          </p>
        </div>

        <div className="min-w-0 sm:text-right">
          <p className="price-numerals text-xl font-bold tracking-tight text-ink sm:text-[1.35rem]">
            {formatPrice(price)}
          </p>
          {validPrice(offer.mrp) && validPrice(price) && offer.mrp > price ? (
            <p className="mt-0.5 text-xs text-ink-muted">
              <span className="line-through">{formatPrice(offer.mrp)}</span>
              {discount ? ` · ${discount}% off` : ""}
            </p>
          ) : null}
        </div>

        <div className="sm:shrink-0">
          {url ? (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer sponsored"
              onClick={() => {
                if (productId) void recordProductActivity(productId, "retailer_click");
              }}
              className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-line-strong bg-white px-4 text-sm font-semibold text-ink transition duration-instant hover:border-ink/20 hover:bg-surface-muted active:translate-y-px sm:w-auto"
            >
              View at {retailer}
              <ExternalLink aria-hidden="true" className="h-4 w-4 shrink-0" />
            </a>
          ) : (
            <span className="text-xs text-ink-muted">Store link unavailable</span>
          )}
        </div>
      </div>
    </li>
  );
}

export function OffersList({
  offers,
  bestOfferId = null,
  productId,
}: {
  offers: Offer[];
  /** @deprecated Prefer computing ties via bestOfferIds; kept for callers. */
  bestOfferId?: string | null;
  productId?: string;
}) {
  const unique = uniqueOffersByPlatform(offers);
  if (unique.length === 0) {
    return (
      <div className="surface-muted px-5 py-6">
        <h3 className="text-title-sm text-ink">No matched offers available</h3>
        <p className="mt-2 text-sm leading-6 text-ink-muted">
          Mayabu has identified this product, but no active matched retailer listing is available
          yet.
        </p>
      </div>
    );
  }

  const bestIds = bestOfferIds(unique);
  if (bestOfferId) bestIds.add(bestOfferId);

  return (
    <ul className="space-y-2.5" aria-label="Retailer offers">
      {unique.map((offer) => (
        <OfferRow
          key={offer.id || `${offer.platform}-${offer.url}`}
          offer={offer}
          isBest={bestIds.has(offer.id)}
          productId={productId}
        />
      ))}
    </ul>
  );
}
