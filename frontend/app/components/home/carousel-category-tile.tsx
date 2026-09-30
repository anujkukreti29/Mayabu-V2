import { Link } from "react-router";
import type { CategoryMosaicTile } from "~/components/home/carousel-types";
import { ProductImage } from "~/components/product/product-image";
import { formatPrice } from "~/lib/formatting/price";
import { buildDisplayTitle } from "~/lib/product/display-title";
import { productSlug } from "~/lib/seo/slug";
import { cn } from "~/components/ui/cn";

export function CarouselCategoryTile({
  tile,
  active,
  priority = false,
}: {
  tile: CategoryMosaicTile;
  active: boolean;
  priority?: boolean;
}) {
  const product = tile.product;
  const href = `/products/${product.id}/${productSlug(product.title)}`;
  const display = buildDisplayTitle(product);

  return (
    <Link
      to={href}
      tabIndex={active ? 0 : -1}
      aria-label={`${display.title} — ${formatPrice(product.best_price)}`}
      className={cn(
        "group relative flex min-h-0 flex-col overflow-hidden rounded-md border border-line bg-page/50 p-2 transition duration-snappy sm:p-2.5",
        "hover:border-brand-300 hover:bg-white hover:shadow-soft",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
        "active:scale-[0.99] motion-safe:hover:-translate-y-0.5",
      )}
    >
      <p className="shrink-0 text-[10px] font-semibold uppercase tracking-[0.12em] text-brand-700">
        {tile.categoryLabel}
      </p>
      <div className="relative mt-1.5 shrink-0">
        <ProductImage
          src={product.image_url}
          alt=""
          category={product.category}
          variant="thumb"
          priority={priority}
          frameClassName="max-h-[4.25rem] bg-white sm:max-h-[5.25rem] lg:max-h-[6rem]"
          className="motion-safe:transition motion-safe:duration-snappy motion-safe:group-hover:scale-[1.02]"
        />
      </div>
      <p
        data-testid="carousel-mosaic-title"
        className="mt-1.5 min-h-[2rem] shrink-0 line-clamp-2 text-xs font-semibold leading-4 text-ink"
      >
        {display.title}
      </p>
      {display.subtitle ? (
        <p className="mt-0.5 shrink-0 truncate text-[10px] text-ink-muted">{display.subtitle}</p>
      ) : null}
      <p className="price-numerals mt-auto pt-1.5 text-sm font-bold leading-none text-ink">
        {formatPrice(product.best_price)}
      </p>
      <span className="mt-1 text-[10px] font-semibold text-brand-700 opacity-0 transition group-hover:opacity-100 group-focus-visible:opacity-100">
        View product
      </span>
    </Link>
  );
}
