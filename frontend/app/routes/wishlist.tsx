import { useEffect, useState } from "react";
import { Link, redirect } from "react-router";
import type { LoaderFunctionArgs, MetaFunction } from "react-router";
import { useAuth } from "~/components/auth/auth-provider";
import { ProductCard } from "~/components/product/product-card";
import { useCompare } from "~/components/comparison/compare-provider";
import { Button } from "~/components/ui/button";
import { EmptyState } from "~/components/ui/empty-state";
import { fetchWishlist, removeWishlistItem } from "~/lib/api/auth";
import type { Product } from "~/lib/api/schemas";
import { pageMeta } from "~/lib/seo/metadata";
import { routes } from "~/lib/navigation/routes";
import { productSchema } from "~/lib/api/schemas";
import { WatchPriceControl } from "~/components/product/watch-price-control";
import { formatPrice } from "~/lib/formatting/price";
import { watchDistanceLabel } from "~/lib/product/price-watch";

export function loader({ request }: LoaderFunctionArgs) {
  const cookie = request.headers.get("cookie") || "";
  if (!cookie.includes("mayabu_session=")) {
    throw redirect(`/sign-in?next=${encodeURIComponent("/wishlist")}`);
  }
  return null;
}

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Wishlist | Mayabu",
    description: "Products you saved on Mayabu.",
    path: "/wishlist",
    robots: "noindex, follow",
  });

export default function WishlistPage() {
  const auth = useAuth();
  const compare = useCompare();
  const [items, setItems] = useState<
    Array<{
      product: Product;
      target_price: number | null;
      notify_on_drop: boolean;
      watch_state?: string | null;
      latest_watch_event?: { event_type?: string; current_price?: number | null; previous_price?: number | null } | null;
    }>
  >([]);
  const [activity, setActivity] = useState<
    Array<{
      id: string;
      product_id: string;
      event_type: string;
      title?: string | null;
      current_price?: number | null;
      previous_price?: number | null;
      target_price?: number | null;
    }>
  >([]);
  const [filter, setFilter] = useState<"all" | "watching" | "dropped" | "target" | "oos">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!auth.user) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void fetchWishlist()
      .then((payload) => {
        if (cancelled) return;
        const next = payload.products.flatMap((item) => {
          const parsed = productSchema.safeParse(item);
          if (!parsed.success) return [];
          const target =
            typeof item.target_price === "number" && Number.isFinite(item.target_price)
              ? item.target_price
              : null;
          return [
            {
              product: parsed.data,
              target_price: target,
              notify_on_drop: Boolean(item.notify_on_drop),
              watch_state: typeof item.watch_state === "string" ? item.watch_state : null,
              latest_watch_event: (() => {
                const raw = item.latest_watch_event;
                if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
                const eventType = "event_type" in raw ? raw.event_type : undefined;
                const currentPrice = "current_price" in raw ? raw.current_price : undefined;
                const previousPrice = "previous_price" in raw ? raw.previous_price : undefined;
                return {
                  event_type: typeof eventType === "string" ? eventType : undefined,
                  current_price: typeof currentPrice === "number" ? currentPrice : null,
                  previous_price: typeof previousPrice === "number" ? previousPrice : null,
                };
              })(),
            },
          ];
        });
        setItems(next);
        setActivity(
          (payload.recent_watch_activity || []).flatMap((row) => {
            if (!row || typeof row !== "object" || Array.isArray(row)) return [];
            const idVal = "id" in row ? row.id : undefined;
            const productVal = "product_id" in row ? row.product_id : undefined;
            const typeVal = "event_type" in row ? row.event_type : undefined;
            const id = typeof idVal === "string" ? idVal : "";
            const product_id = typeof productVal === "string" ? productVal : "";
            const event_type = typeof typeVal === "string" ? typeVal : "";
            if (!id || !product_id || !event_type) return [];
            const titleVal = "title" in row ? row.title : undefined;
            const currentVal = "current_price" in row ? row.current_price : undefined;
            const previousVal = "previous_price" in row ? row.previous_price : undefined;
            const targetVal = "target_price" in row ? row.target_price : undefined;
            return [
              {
                id,
                product_id,
                event_type,
                title: typeof titleVal === "string" ? titleVal : null,
                current_price: typeof currentVal === "number" ? currentVal : null,
                previous_price: typeof previousVal === "number" ? previousVal : null,
                target_price: typeof targetVal === "number" ? targetVal : null,
              },
            ];
          }),
        );
        next.forEach((entry) => auth.markWishlisted(entry.product.id, true));
        setError(null);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load your wishlist.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // auth object identity changes; depend on stable user id + markWishlisted.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional
  }, [auth.user?.id, auth.markWishlisted]);

  if (!auth.user) {
    return (
      <main id="main-content" className="page-container py-16">
        <EmptyState
          title="Sign in to view your wishlist"
          description="Wishlist requires a Mayabu account so saved products follow you across devices."
          action={
            <Link
              to={`${routes.login}?next=/wishlist`}
              className="inline-flex min-h-11 items-center rounded-md bg-accent px-4 text-sm font-semibold text-white hover:bg-accent-strong"
            >
              Sign in
            </Link>
          }
        />
      </main>
    );
  }

  return (
    <main id="main-content" className="page-container py-10 sm:py-14">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
        <div>
          <p className="eyebrow">Price Watch</p>
          <h1 className="mt-2 text-display text-ink">Watchlist</h1>
          <p className="mt-2 max-w-xl text-sm text-ink-muted">
            Saved products and price-watch events. Mayabu tracks targets inside your account —
            email alerts stay deferred until the notification provider is operational.
            {!loading ? ` ${items.length} saved.` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {items.length >= 2 ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                const first = items[0]?.product;
                if (!first) return;
                const category = (first.category || "").toLowerCase();
                items
                  .map((entry) => entry.product)
                  .filter((item) => (item.category || "").toLowerCase() === category)
                  .slice(0, compare.maxProducts)
                  .forEach((item) => compare.add(item));
              }}
            >
              Add to compare
            </Button>
          ) : null}
          <Link
            to={routes.search}
            className="inline-flex min-h-11 items-center rounded-md border border-line bg-white px-4 text-sm font-semibold text-ink transition hover:bg-surface-muted"
          >
            Discover products
          </Link>
        </div>
      </div>

      {loading ? (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="surface h-72 animate-pulse bg-surface-muted" />
          ))}
        </div>
      ) : null}
      {error ? (
        <p className="mt-8 text-sm text-rose-600" role="alert">
          {error}
        </p>
      ) : null}

      {!loading && activity.length > 0 ? (
        <section className="mt-8 rounded-md border border-line bg-white p-4" aria-labelledby="watch-activity-title">
          <h2 id="watch-activity-title" className="text-base font-semibold text-ink">
            Recent watch activity
          </h2>
          <ul className="mt-3 space-y-2">
            {activity.slice(0, 8).map((entry) => {
              const label =
                entry.event_type === "price_drop" && entry.previous_price != null && entry.current_price != null
                  ? `${entry.title || "Product"} dropped ${formatPrice(entry.previous_price - entry.current_price)}`
                  : entry.event_type === "target_reached"
                    ? `${entry.title || "Product"} reached your ${entry.target_price != null ? formatPrice(entry.target_price) : "target"}`
                    : entry.event_type === "back_in_stock"
                      ? `${entry.title || "Product"} is back in stock`
                      : entry.event_type === "out_of_stock"
                        ? `${entry.title || "Product"} went out of stock`
                        : `${entry.title || "Product"} · ${entry.event_type.replace(/_/g, " ")}`;
              return (
                <li key={entry.id}>
                  <Link
                    to={`/products/${entry.product_id}`}
                    className="text-sm font-medium text-brand-800 hover:underline"
                  >
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {!loading && items.length > 0 ? (
        <div
          className="mt-6 flex flex-wrap gap-2"
          role="toolbar"
          aria-label="Watchlist filters"
        >
          {(
            [
              ["all", "All"],
              ["watching", "Watching"],
              ["dropped", "Price dropped"],
              ["target", "At target"],
              ["oos", "Out of stock"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              aria-pressed={filter === id}
              onClick={() => setFilter(id)}
              className={`inline-flex min-h-9 items-center rounded-md border px-3 text-sm font-medium transition ${
                filter === id
                  ? "border-brand-600 bg-brand-50 text-brand-800"
                  : "border-line bg-white text-ink-soft hover:bg-slate-50"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      ) : null}

      {!loading && !error && items.length === 0 ? (
        <div className="mt-10">
          <EmptyState
            title="Start watching products"
            description="Watch products to track meaningful price changes inside your Mayabu account."
            action={
              <Link
                to={routes.home}
                className="inline-flex min-h-11 items-center rounded-md bg-accent px-4 text-sm font-semibold text-white hover:bg-accent-strong"
              >
                Discover products
              </Link>
            }
          />
        </div>
      ) : null}

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {items
          .filter((entry) => {
            if (filter === "all") return true;
            if (filter === "watching") return entry.notify_on_drop || entry.target_price != null;
            if (filter === "dropped") return entry.watch_state === "PRICE_DROPPED";
            if (filter === "target") return entry.watch_state === "AT_TARGET";
            if (filter === "oos") return entry.watch_state === "OUT_OF_STOCK";
            return true;
          })
          .map(({ product, target_price: target, notify_on_drop: watchingDrop, watch_state, latest_watch_event }) => {
          const watchLabel =
            target != null && Number.isFinite(target)
              ? `Target ${formatPrice(target)}`
              : watchingDrop
                ? "Watching"
                : null;
          const purchasable =
            (product as Product & { available?: boolean }).available !== false &&
            String((product as Product & { stock_status?: string | null }).stock_status || "").toLowerCase() !==
              "out_of_stock";
          const distance = watchDistanceLabel({
            targetPrice: target,
            currentPrice: product.best_price,
            purchasable,
          });
          const eventHint =
            latest_watch_event?.event_type === "price_drop" &&
            latest_watch_event.previous_price != null &&
            latest_watch_event.current_price != null
              ? `Dropped ${formatPrice(latest_watch_event.previous_price - latest_watch_event.current_price)}`
              : watch_state === "AT_TARGET"
                ? "Target reached"
                : watch_state === "BACK_IN_STOCK"
                  ? "Back in stock"
                  : watch_state === "OUT_OF_STOCK"
                    ? "Current buyable price unavailable"
                    : null;
          return (
            <div key={product.id} className="relative">
              <ProductCard product={product} showCategoryBadge />
              {watchLabel ? (
                <p className="mt-2 text-xs font-medium text-brand-700">{watchLabel}</p>
              ) : null}
              {eventHint ? (
                <p className="mt-1 text-xs font-medium text-ink">{eventHint}</p>
              ) : null}
              {distance ? (
                <p className="mt-1 text-xs text-ink-muted">{distance}</p>
              ) : null}
              <WatchPriceControl
                productId={product.id}
                productTitle={product.title}
                currentPrice={product.best_price}
                initialTarget={target ?? null}
                initialNotifyOnDrop={watchingDrop}
                className="mt-2"
              />
              <Button
                type="button"
                variant="ghost"
                className="mt-2 w-full text-ink-muted"
                onClick={() => {
                  void removeWishlistItem(product.id).then((result) => {
                    setItems((current) => current.filter((item) => item.product.id !== product.id));
                    auth.markWishlisted(product.id, false);
                    auth.setSession(auth.user, result.count);
                  });
                }}
              >
                Remove
              </Button>
            </div>
          );
        })}
      </div>
    </main>
  );
}
