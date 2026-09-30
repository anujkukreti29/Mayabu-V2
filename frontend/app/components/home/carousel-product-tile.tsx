import { Link } from "react-router";
import { ProductImage } from "~/components/product/product-image";
import { formatPrice } from "~/lib/formatting/price";
import { platformDisplayName } from "~/lib/search/platforms";
import { categoryShortLabel } from "~/lib/search/categories";
import { productSlug } from "~/lib/seo/slug";
import { buildDisplayTitle } from "~/lib/product/display-title";
import type { HomepageProduct } from "~/lib/api/schemas";
import type { ProductGridTheme } from "~/components/home/carousel-types";
import { cn } from "~/components/ui/cn";

function tileBadge(product: HomepageProduct, theme: ProductGridTheme, fallback: string): string {
  if (theme === "biggest_discounts" && product.discount_percent != null) {
    return `${product.discount_percent}% off`;
  }
  if (theme === "lowest_since_tracking") return "Lowest since tracking";
  if (theme === "price_drops") return "Price dropped";
  if (theme === "trending") return "Trending";
  if (theme === "popular") return product.activity_badge || "Popular";
  if (theme === "recently_verified") return "Recently verified";
  return fallback;
}

export function CarouselProductTile({
  product,
  theme,
  badge,
  active,
  priority = false,
}: {
  product: HomepageProduct;
  theme: ProductGridTheme;
  badge: string;
  active: boolean;
  priority?: boolean;
}) {
  const href = `/products/${product.id}/${productSlug(product.title)}`;
  const label = tileBadge(product, theme, badge);
  const category = categoryShortLabel(product.category);
  const platform = platformDisplayName(product.best_platform);
  const display = buildDisplayTitle(product);

  return (
    <Link
      to={href}
      tabIndex={active ? 0 : -1}
      aria-label={`${display.title} — ${formatPrice(product.best_price)}`}
      className={cn(
        "group flex min-h-0 flex-col overflow-hidden rounded-md border border-line bg-page/50 p-2 transition duration-snappy",
        "hover:border-brand-300 hover:bg-white hover:shadow-soft",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
        "active:scale-[0.99] motion-safe:hover:-translate-y-0.5",
      )}
    >
      <div className="relative shrink-0">
        <ProductImage
          src={product.image_url}
          alt=""
          category={product.category}
          variant="thumb"
          priority={priority}
          frameClassName="max-h-[3.75rem] bg-white sm:max-h-[4.5rem] lg:max-h-[5.25rem]"
          className="motion-safe:transition motion-safe:duration-snappy motion-safe:group-hover:scale-[1.02]"
        />
        <span className="absolute left-1.5 top-1.5 max-w-[calc(100%-0.75rem)] truncate rounded-sm bg-white/95 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand-800 shadow-soft">
          {label}
        </span>
      </div>
      <div className="mt-1.5 flex min-h-[0.875rem] shrink-0 flex-wrap items-center gap-1 text-[10px] text-ink-muted">
        {category ? <span className="font-medium">{category}</span> : null}
        {product.brand ? (
          <>
            <span aria-hidden="true">·</span>
            <span className="truncate font-medium uppercase tracking-wide">{product.brand}</span>
          </>
        ) : null}
      </div>
      <p
        data-testid="carousel-product-title"
        className="mt-0.5 min-h-[2rem] shrink-0 line-clamp-2 text-xs font-semibold leading-4 text-ink"
      >
        {display.title}
      </p>
      {display.subtitle ? (
        <p className="mt-0.5 shrink-0 truncate text-[10px] text-ink-muted">{display.subtitle}</p>
      ) : null}
      <p className="price-numerals mt-auto pt-1 text-sm font-bold leading-none text-ink">
        {formatPrice(product.best_price)}
      </p>
      {theme === "biggest_discounts" && product.mrp != null ? (
        <p className="mt-0.5 shrink-0 text-[10px] text-ink-muted line-through">
          {formatPrice(product.mrp)}
        </p>
      ) : null}
      {theme === "price_drops" && product.drop_percent != null ? (
        <p className="mt-0.5 shrink-0 text-[10px] font-medium text-emerald-700">
          Down {product.drop_percent}%
        </p>
      ) : platform ? (
        <p className="mt-0.5 shrink-0 truncate text-[10px] text-ink-muted">{platform}</p>
      ) : null}
    </Link>
  );
}
