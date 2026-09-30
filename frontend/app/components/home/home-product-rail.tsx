import { HomeProductCard, type HomeCardAccent } from "~/components/home/home-product-card";
import type { HomepageProduct } from "~/lib/api/schemas";

/**
 * Shared Homepage commerce rail — always horizontal scroll.
 * Never switches to a wrapping CSS grid (avoids 4+orphan / stretched last cards).
 */
export function HomeProductRail({
  products,
  accent,
  minProducts = 1,
}: {
  products: readonly HomepageProduct[];
  accent?: HomeCardAccent;
  /** Hide sparse rails that look unfinished (e.g. multi-store needs ≥2). */
  minProducts?: number;
}) {
  if (products.length < minProducts) return null;

  const visible = products.slice(0, 8);
  if (visible.length === 0) return null;

  return (
    <div className="-mx-1 mt-4 min-w-0 max-w-full">
      <div
        className="home-product-rail flex min-w-0 max-w-full snap-x snap-mandatory gap-2.5 overflow-x-auto px-1 pb-1"
        data-testid="home-product-rail"
        data-count={visible.length}
      >
        {visible.map((product, index) => (
          <div
            key={product.id}
            data-testid="home-product-rail-item"
            className="w-[68%] max-w-[14.5rem] shrink-0 snap-start min-[390px]:w-[58%] sm:w-[42%] sm:max-w-[15rem] md:w-[30%] md:max-w-[15.5rem] lg:w-[23%] lg:max-w-[15.5rem] xl:w-[18.5%] xl:max-w-[15.5rem]"
          >
            <HomeProductCard
              product={product}
              accent={accent}
              priority={index < 2}
              rank={accent === "popular" ? index + 1 : undefined}
            />
          </div>
        ))}
        {visible.length > 1 ? <div className="w-3 shrink-0" aria-hidden="true" /> : null}
      </div>
    </div>
  );
}
