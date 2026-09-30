import { ArrowRight } from "lucide-react";
import { Link } from "react-router";
import type { HomeCarouselSlide } from "~/components/home/carousel-types";
import { CarouselCategoryTile } from "~/components/home/carousel-category-tile";
import { CarouselProductTile } from "~/components/home/carousel-product-tile";
import { ProductImage } from "~/components/product/product-image";
import { DisplaySpecs } from "~/components/product/display-specs";
import { cn } from "~/components/ui/cn";
import { formatPrice } from "~/lib/formatting/price";
import { productSlug } from "~/lib/seo/slug";
import { platformDisplayName } from "~/lib/search/platforms";
import { categoryShortLabel } from "~/lib/search/categories";

function slideShell({
  active,
  labelledBy,
  title,
  children,
}: {
  active: boolean;
  labelledBy: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <article
      id={labelledBy}
      role="group"
      aria-roledescription="slide"
      aria-label={title}
      aria-hidden={!active}
      className={cn(
        "absolute inset-0 overflow-hidden bg-white transition-[opacity,transform] duration-[350ms] ease-out motion-reduce:transition-none",
        active
          ? "pointer-events-auto translate-x-0 opacity-100"
          : "pointer-events-none invisible translate-x-3 opacity-0 motion-reduce:translate-x-0",
      )}
    >
      {children}
    </article>
  );
}

export function CarouselSlideView({
  slide,
  active,
  labelledBy,
}: {
  slide: HomeCarouselSlide;
  active: boolean;
  labelledBy: string;
}) {
  if (slide.kind === "category_mosaic") {
    return slideShell({
      active,
      labelledBy,
      title: slide.title,
      children: (
        <div className="flex h-full flex-col p-3 sm:p-4">
          <div className="mb-2.5 shrink-0 sm:mb-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
              Featured picks
            </p>
            <h3 className="mt-0.5 text-base font-semibold text-ink sm:text-lg">{slide.title}</h3>
            <p className="mt-0.5 text-xs text-ink-muted">{slide.description}</p>
          </div>
          <div className="grid min-h-0 flex-1 grid-cols-2 grid-rows-2 gap-2 sm:gap-2.5">
            {slide.tiles.map((tile, index) => (
              <CarouselCategoryTile
                key={tile.id}
                tile={tile}
                active={active}
                priority={active && index === 0}
              />
            ))}
          </div>
        </div>
      ),
    });
  }

  if (slide.kind === "product_grid") {
    return slideShell({
      active,
      labelledBy,
      title: slide.title,
      children: (
        <div className="flex h-full flex-col p-3 sm:p-4">
          <div className="mb-2.5 shrink-0 sm:mb-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
              {slide.badge}
            </p>
            <h3 className="mt-0.5 text-base font-semibold text-ink sm:text-lg">{slide.title}</h3>
            <p className="mt-0.5 text-xs text-ink-muted">{slide.description}</p>
          </div>
          <div className="grid min-h-0 flex-1 grid-cols-2 grid-rows-2 gap-2 sm:gap-2.5">
            {slide.products.map((product, index) => (
              <CarouselProductTile
                key={product.id}
                product={product}
                theme={slide.theme}
                badge={slide.badge}
                active={active}
                priority={active && index === 0}
              />
            ))}
          </div>
        </div>
      ),
    });
  }

  const href = `/products/${slide.product.id}/${productSlug(slide.product.title)}`;
  const category = categoryShortLabel(slide.product.category);
  const platform = platformDisplayName(slide.product.best_platform);
  const offerCount = slide.product.platform_count ?? slide.product.offer_count ?? 0;

  return slideShell({
    active,
    labelledBy,
    title: slide.title,
    children: (
      <div className="grid h-full grid-rows-[minmax(0,1.05fr)_minmax(0,0.95fr)] gap-3 p-3 sm:grid-cols-[1.05fr_0.95fr] sm:grid-rows-1 sm:gap-5 sm:p-4 lg:p-5">
        <ProductImage
          src={slide.product.image_url}
          alt={slide.product.title}
          category={slide.product.category}
          variant="card"
          priority={active}
          frameClassName="border border-line bg-slate-50"
          className="max-h-[9.5rem] sm:max-h-[13rem] lg:max-h-[14.5rem]"
        />
        <div className="flex min-w-0 flex-col">
          <p className="w-fit rounded-sm bg-brand-50 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-brand-800">
            {slide.badge}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-ink-muted">
            {category ? <span className="font-medium">{category}</span> : null}
            {slide.product.brand ? (
              <>
                <span aria-hidden="true">·</span>
                <span className="truncate font-medium uppercase tracking-wide">
                  {slide.product.brand}
                </span>
              </>
            ) : null}
          </div>
          <h3 className="mt-1 line-clamp-2 min-h-[2.5rem] text-base font-semibold leading-snug text-ink sm:text-lg">
            {slide.title}
          </h3>
          <div className="mt-1 min-h-[1.25rem]">
            <DisplaySpecs product={slide.product} />
          </div>
          <p className="price-numerals mt-3 text-2xl font-bold text-ink">
            {formatPrice(slide.product.best_price)}
          </p>
          {offerCount > 0 ? (
            <p className="mt-0.5 text-xs text-ink-muted">
              {offerCount === 1 ? "1 store" : `Compare ${offerCount} stores`}
              {platform ? ` · best at ${platform}` : ""}
            </p>
          ) : platform ? (
            <p className="mt-0.5 text-xs text-ink-muted">Best known at {platform}</p>
          ) : null}
          {slide.highlight ? (
            <p className="mt-1 text-sm font-medium text-emerald-700">{slide.highlight}</p>
          ) : (
            <p className="mt-1 text-xs text-ink-muted sm:text-sm">{slide.description}</p>
          )}
          <Link
            to={href}
            tabIndex={active ? 0 : -1}
            className="mt-auto inline-flex min-h-10 items-center gap-1 pt-3 text-sm font-semibold text-brand-700 transition hover:text-brand-800 active:translate-x-px"
          >
            View product <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </div>
      </div>
    ),
  });
}
