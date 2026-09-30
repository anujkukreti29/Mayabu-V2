import { Link } from "react-router";
import { X } from "lucide-react";
import { ProductImage } from "~/components/product/product-image";
import { formatPrice } from "~/lib/formatting/price";
import { freshnessFrom } from "~/lib/formatting/freshness";
import { platformDisplayName } from "~/lib/search/platforms";
import { productSlug } from "~/lib/seo/slug";
import type { Product } from "~/lib/api/schemas";
import { variantIdentityLine } from "~/lib/search/format-spec";
import { cn } from "~/components/ui/cn";

export function CompareProductColumn({
  product,
  onRemove,
  priceDeltaLabel,
  sticky = false,
}: {
  product: Product;
  onRemove?: () => void;
  priceDeltaLabel?: string | null;
  sticky?: boolean;
}) {
  const href = `/products/${product.id}/${productSlug(product.title)}`;
  const platform = platformDisplayName(product.best_platform);
  const freshness = freshnessFrom(product.last_seen_at);
  const offerCount = product.platform_count ?? product.offer_count ?? 0;
  const model = product.model_codes?.[0];

  return (
    <div
      className={cn(
        "flex h-full min-w-[11.5rem] flex-col sm:min-w-[13rem]",
        sticky && "lg:sticky lg:top-[calc(var(--mayabu-header-h)+0.5rem)] lg:z-sticky lg:bg-white",
      )}
    >
      <div className="relative">
        <ProductImage
          src={product.image_url}
          alt={product.title}
          category={product.category}
          variant="card"
          frameClassName="border border-line bg-slate-50"
          className="max-h-[7.5rem] sm:max-h-[8.5rem]"
        />
        {onRemove ? (
          <button
            type="button"
            onClick={onRemove}
            className="absolute right-1.5 top-1.5 grid h-8 w-8 place-items-center rounded-md border border-line bg-white/95 text-ink-muted transition hover:bg-white hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            aria-label={`Remove ${product.title} from comparison`}
          >
            <X aria-hidden="true" className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </div>
      <div className="mt-2.5 flex min-h-[1.1rem] flex-wrap items-center gap-1.5 text-[11px] text-ink-muted">
        {product.brand ? (
          <span className="font-semibold uppercase tracking-wide">{product.brand}</span>
        ) : null}
        {model ? (
          <>
            <span aria-hidden="true">·</span>
            <span className="truncate font-medium">{model}</span>
          </>
        ) : null}
      </div>
      <h2 className="mt-1 line-clamp-3 min-h-[3.4rem] text-sm font-semibold leading-5 text-ink">
        {product.title}
      </h2>
      {variantIdentityLine(product) ? (
        <p className="mt-1 line-clamp-1 text-xs font-medium text-ink-muted">
          {variantIdentityLine(product)}
        </p>
      ) : (
        <p className="mt-1 min-h-[1rem] text-xs text-transparent">.</p>
      )}
      <p className="price-numerals mt-2 text-xl font-bold text-ink">
        {formatPrice(product.best_price)}
      </p>
      {priceDeltaLabel ? (
        <p className="mt-0.5 text-xs font-medium text-emerald-700">{priceDeltaLabel} cheaper</p>
      ) : (
        <p className="mt-0.5 min-h-[1rem] text-xs text-transparent">.</p>
      )}
      <p className="mt-1 truncate text-xs text-ink-muted">
        {platform ? `Best at ${platform}` : "Retailer unavailable"}
      </p>
      <p className="mt-0.5 text-xs text-ink-muted">
        {offerCount > 0
          ? `${offerCount} public offer${offerCount === 1 ? "" : "s"}`
          : "Offers unavailable"}
      </p>
      <p className="mt-0.5 text-xs text-ink-muted">{freshness.label}</p>
      <div className="mt-auto flex flex-col gap-1.5 pt-3">
        <Link
          to={href}
          className="inline-flex min-h-10 items-center justify-center rounded-md bg-brand-600 px-3 text-sm font-semibold text-white transition hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
        >
          View product
        </Link>
        {offerCount > 0 ? (
          <Link
            to={`${href}#offers`}
            className="inline-flex min-h-9 items-center justify-center rounded-md border border-line px-3 text-xs font-semibold text-brand-700 transition hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          >
            View {offerCount} offer{offerCount === 1 ? "" : "s"}
          </Link>
        ) : null}
      </div>
    </div>
  );
}
