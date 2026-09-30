import { Link } from "react-router";
import { ProductImage } from "~/components/product/product-image";
import { DisplaySpecs } from "~/components/product/display-specs";
import { formatPrice } from "~/lib/formatting/price";
import { platformDisplayName } from "~/lib/search/platforms";
import { categoryShortLabel } from "~/lib/search/categories";
import { productSlug } from "~/lib/seo/slug";
import { recordProductActivity } from "~/lib/api/activity";
import { buildDisplayTitle } from "~/lib/product/display-title";
import { productCardIntelligence } from "~/lib/product/card-intelligence";
import type { HomepageProduct } from "~/lib/api/schemas";
import { cn } from "~/components/ui/cn";

export type HomeCardAccent = "drop" | "discount" | "trending" | "popular" | "lowest" | null;

function accentBadge(product: HomepageProduct, accent?: HomeCardAccent): string | null {
  if (accent === "trending") return product.activity_badge || "Trending";
  if (accent === "popular") return product.activity_badge || "Popular";
  if (accent === "lowest") return "Lowest since tracking";
  if (accent === "drop" && product.drop_percent != null) return "Price dropped";
  if (accent === "discount" && product.discount_percent != null) {
    return `${product.discount_percent}% off`;
  }
  return null;
}

export function HomeProductCard({
  product,
  accent,
  priority = false,
  rank,
}: {
  product: HomepageProduct;
  accent?: HomeCardAccent;
  priority?: boolean;
  rank?: number;
}) {
  const href = `/products/${product.id}/${productSlug(product.title)}`;
  const platform = platformDisplayName(product.best_platform);
  const category = categoryShortLabel(product.category);
  const badge = accentBadge(product, accent);
  const display = buildDisplayTitle(product);
  // Accent rails already carry a primary cue; only surface card intelligence when none.
  const intelligence = !accent ? productCardIntelligence(product) : null;

  return (
    <Link
      to={href}
      onClick={() => {
        void recordProductActivity(product.id, "search_click");
      }}
      className={cn(
        "group flex h-full flex-col border border-line bg-white p-2.5 transition duration-snappy sm:p-3",
        "hover:border-brand-300 hover:shadow-soft",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
        "active:translate-y-px motion-safe:hover:-translate-y-0.5",
        "motion-reduce:hover:translate-y-0 motion-reduce:active:translate-y-0",
      )}
    >
      <div className="relative shrink-0">
        <ProductImage
          src={product.image_url}
          alt={product.title || "Product"}
          category={product.category}
          variant="card"
          priority={priority}
          frameClassName="max-h-[8.5rem] sm:max-h-[9.5rem]"
          className="transition duration-snappy motion-safe:group-hover:scale-[1.02]"
        />
        {badge ? (
          <span className="absolute left-2 top-2 rounded-sm bg-white/95 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand-800 shadow-soft">
            {badge}
          </span>
        ) : null}
        {accent === "popular" && rank != null ? (
          <span className="absolute right-2 top-2 grid h-6 w-6 place-items-center rounded-sm bg-ink text-[11px] font-bold text-white">
            {rank}
          </span>
        ) : null}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-ink-muted">
        {category ? <span className="font-medium">{category}</span> : null}
        {product.brand ? (
          <>
            <span aria-hidden="true">·</span>
            <span className="truncate font-medium uppercase tracking-wide">{product.brand}</span>
          </>
        ) : null}
      </div>
      <h3 className="mt-1 min-h-[2.5rem] line-clamp-2 text-sm font-semibold leading-5 text-ink">
        {display.title}
      </h3>
      {display.subtitle ? (
        <p className="mt-0.5 truncate text-[11px] text-ink-muted">{display.subtitle}</p>
      ) : (
        <div className="mt-1 min-h-[1.25rem]">
          <DisplaySpecs product={product} />
        </div>
      )}
      <p className="price-numerals mt-auto pt-1.5 text-base font-bold text-ink sm:text-lg">
        {formatPrice(product.best_price)}
      </p>
      {platform ? <p className="mt-0.5 truncate text-xs text-ink-muted">{platform}</p> : null}
      {intelligence ? (
        <p className="mt-1 text-xs font-medium text-ink-soft">{intelligence.label}</p>
      ) : null}
      {accent === "drop" && product.previous_price != null ? (
        <p className="mt-1 text-xs font-medium text-emerald-700">
          ↓{" "}
          {product.drop_amount != null
            ? formatPrice(product.drop_amount)
            : product.drop_percent != null
              ? `${product.drop_percent}%`
              : formatPrice(product.previous_price - (product.best_price ?? 0))}
          <span className="ml-1 font-normal text-ink-muted line-through">
            {formatPrice(product.previous_price)}
          </span>
        </p>
      ) : null}
      {accent === "discount" && product.discount_percent != null && product.mrp != null ? (
        <p className="mt-1 text-xs font-medium text-emerald-700">
          {product.discount_percent}% off MRP {formatPrice(product.mrp)}
        </p>
      ) : null}
      {accent === "lowest" ? (
        <p
          className="mt-1 text-xs font-medium text-brand-700"
          title="Based on Mayabu tracked daily best prices, not full market history."
        >
          Lowest since Mayabu started tracking
        </p>
      ) : null}
      <span className="mt-2 text-xs font-semibold text-brand-700 group-hover:text-brand-800">
        View details
      </span>
    </Link>
  );
}
