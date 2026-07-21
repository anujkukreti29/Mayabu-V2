import { ExternalLink } from "lucide-react";
import { Badge } from "~/components/ui/badge";
import { Card } from "~/components/ui/card";
import { formatPrice, validDiscount, validPrice } from "~/lib/formatting/price";
import { freshnessFrom } from "~/lib/formatting/freshness";
import { safeRetailerUrl } from "~/lib/security/external-url";
import type { Offer } from "~/lib/api/schemas";

function OfferContent({ offer }: { offer: Offer }) {
  const price = validPrice(offer.effective_price) ? offer.effective_price : offer.price;
  const discount = validDiscount(price, offer.mrp, offer.discount_percent);
  const fresh = freshnessFrom(offer.last_verified_at ?? offer.last_checked_at);
  const url = safeRetailerUrl(offer.url);
  const stock = offer.stock_status?.toLowerCase();
  const outOfStock = stock === "out_of_stock" || stock === "unavailable";

  return (
    <>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-black text-slate-950">{offer.platform || "Retailer"}</p>
          <p className="mt-1 line-clamp-2 text-xs text-slate-500">
            {offer.title || "Matched retailer listing"}
          </p>
        </div>
        <Badge tone={outOfStock ? "danger" : "success"}>
          {outOfStock ? "Out of stock" : offer.stock_status || "Availability unknown"}
        </Badge>
      </div>
      <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="price-numerals text-2xl font-black">{formatPrice(price)}</p>
          {validPrice(offer.mrp) && validPrice(price) && offer.mrp > price ? (
            <p className="text-xs text-slate-500">
              <span className="line-through">{formatPrice(offer.mrp)}</span>
              {discount ? ` · ${discount}% off` : ""}
            </p>
          ) : null}
          <p className="mt-1 text-xs text-slate-500">{fresh.label}</p>
        </div>
        {url ? (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer sponsored"
            className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 text-sm font-bold hover:bg-slate-50"
          >
            View on {offer.platform || "store"}
            <ExternalLink aria-hidden="true" className="h-4 w-4" />
          </a>
        ) : (
          <span className="text-xs text-slate-500">Store link unavailable</span>
        )}
      </div>
    </>
  );
}

export function OffersList({ offers }: { offers: Offer[] }) {
  if (offers.length === 0) {
    return (
      <Card className="p-6">
        <h3 className="font-black">No matched offers available</h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Mayabu has identified this product, but no active matched retailer listing is available
          yet.
        </p>
      </Card>
    );
  }
  return (
    <div className="grid gap-4">
      {offers.map((offer) => (
        <Card key={offer.id} className="p-5">
          <OfferContent offer={offer} />
        </Card>
      ))}
    </div>
  );
}
