import { Link, useLocation } from "react-router";
import { X } from "lucide-react";
import { ProductImage } from "~/components/product/product-image";
import { useCompare } from "~/components/comparison/compare-provider";
import { comparePath } from "~/lib/api/compare";
import { categoryDisplayName } from "~/lib/search/categories";
import { cn } from "~/components/ui/cn";

function shortTitle(title: string | null | undefined, max = 28): string {
  const value = (title || "Product").trim();
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1).trimEnd()}…`;
}

/** Reserves scroll space so fixed compare tray does not cover bottom CTAs. */
export function CompareDockSpacer() {
  const compare = useCompare();
  const location = useLocation();
  if (compare.products.length === 0) return null;
  if (location.pathname === "/compare") return null;
  const onProductPage = location.pathname.startsWith("/products/");
  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none shrink-0",
        onProductPage ? "h-28 sm:h-20" : "h-20 sm:h-24",
      )}
    />
  );
}

export function CompareDock() {
  const compare = useCompare();
  const location = useLocation();
  if (compare.products.length === 0) return null;
  // Full compare page already has remove/clear/add controls. A second fixed
  // tray collides with sticky product headers on short desktop viewports.
  if (location.pathname === "/compare") return null;

  const href = comparePath(compare.products.map((product) => product.id));
  const categoryLabel = categoryDisplayName(compare.activeCategory);
  const canOpen = compare.products.length >= 2;
  const remaining = Math.max(0, compare.maxProducts - compare.products.length);
  const onProductPage = location.pathname.startsWith("/products/");
  const count = compare.products.length;

  return (
    <aside
      aria-label="Product comparison tray"
      className={cn(
        "fixed inset-x-3 z-dock mx-auto w-auto max-w-3xl",
        // Sit above the mobile PDP sticky action bar (same z-40) so CTAs stay usable.
        onProductPage
          ? "bottom-[calc(4.25rem+env(safe-area-inset-bottom))] sm:bottom-[max(0.75rem,env(safe-area-inset-bottom))]"
          : "bottom-[max(0.75rem,env(safe-area-inset-bottom))]",
        "rounded-md border border-line bg-white/95 shadow-lift backdrop-blur-sm",
        "sm:inset-x-auto sm:left-1/2 sm:w-[min(94vw,44rem)] sm:-translate-x-1/2",
      )}
    >
      {/* Mobile: compact tray — overlapping thumbs + count · Compare */}
      <div className="flex items-center gap-2.5 p-2 sm:hidden">
        <div className="flex shrink-0 items-center -space-x-2" aria-hidden="true">
          {compare.products.slice(0, 4).map((product) => (
            <div
              key={product.id}
              className="relative h-8 w-8 overflow-hidden rounded-md border border-white bg-slate-50 shadow-soft"
            >
              <ProductImage
                src={product.image_url}
                alt=""
                category={product.category}
                variant="thumb"
                frameClassName="h-full w-full rounded-none border-0 bg-slate-50 p-0.5"
              />
            </div>
          ))}
        </div>
        <p className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">
          {count} product{count === 1 ? "" : "s"} selected
          {categoryLabel ? (
            <span className="font-normal text-ink-muted"> · {categoryLabel}</span>
          ) : null}
        </p>
        <button
          type="button"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-md text-ink-muted transition hover:bg-slate-100 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          onClick={compare.clear}
          aria-label="Clear comparison"
        >
          <X aria-hidden="true" className="h-4 w-4" />
        </button>
        {canOpen ? (
          <Link
            to={href}
            className="inline-flex min-h-9 shrink-0 items-center rounded-md bg-brand-600 px-3 text-sm font-semibold text-white transition hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          >
            Compare now
          </Link>
        ) : (
          <span className="shrink-0 text-xs font-medium text-ink-muted">Add one more</span>
        )}
      </div>

      {/* Desktop: per-product chip with image, short title, remove + empty slots */}
      <div className="hidden p-3 sm:block">
        <div className="flex items-center gap-3">
          <div className="flex min-w-0 flex-1 items-stretch gap-2">
            {compare.products.map((product) => (
              <div
                key={product.id}
                className="flex min-w-0 max-w-[9.5rem] flex-1 items-center gap-2 rounded-md border border-line bg-slate-50/80 py-1.5 pl-1.5 pr-1"
              >
                <div className="relative h-9 w-9 shrink-0 overflow-hidden rounded-sm bg-white">
                  <ProductImage
                    src={product.image_url}
                    alt=""
                    category={product.category}
                    variant="thumb"
                    frameClassName="h-full w-full rounded-none border-0 bg-white p-0.5"
                  />
                </div>
                <p className="min-w-0 flex-1 truncate text-xs font-semibold leading-snug text-ink">
                  {shortTitle(product.title)}
                </p>
                <button
                  type="button"
                  className="grid h-7 w-7 shrink-0 place-items-center rounded-sm text-ink-muted transition hover:bg-white hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
                  onClick={() => compare.remove(product.id)}
                  aria-label={`Remove ${product.title || "product"} from comparison`}
                >
                  <X aria-hidden="true" className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
            {Array.from({ length: remaining }).map((_, index) => (
              <div
                key={`slot-${index}`}
                className="flex min-w-0 max-w-[9.5rem] flex-1 items-center justify-center rounded-md border border-dashed border-line px-2 py-2 text-[11px] font-medium text-ink-faint"
                aria-hidden="true"
              >
                Slot open
              </div>
            ))}
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              className="grid h-10 w-10 place-items-center rounded-md text-ink-muted transition hover:bg-slate-100 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              onClick={compare.clear}
              aria-label="Clear comparison"
            >
              <X aria-hidden="true" className="h-4 w-4" />
            </button>
            {canOpen ? (
              <Link
                to={href}
                className="inline-flex min-h-10 items-center rounded-md bg-brand-600 px-4 text-sm font-semibold text-white transition hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              >
                Compare now
              </Link>
            ) : (
              <span className="inline-flex min-h-10 items-center rounded-md border border-line px-3 text-xs font-medium text-ink-muted">
                Add one more
              </span>
            )}
          </div>
        </div>
        {categoryLabel ? (
          <p className="mt-2 text-[11px] text-ink-muted">
            {count} of {compare.maxProducts} · {categoryLabel}
          </p>
        ) : (
          <p className="mt-2 text-[11px] text-ink-muted">
            {count} of {compare.maxProducts} selected
          </p>
        )}
      </div>
    </aside>
  );
}
