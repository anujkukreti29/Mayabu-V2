import { Check, GitCompareArrows } from "lucide-react";
import { Link } from "react-router";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import { Card } from "~/components/ui/card";
import { ProductImage } from "~/components/product/product-image";
import { DisplaySpecs } from "~/components/product/display-specs";
import { WishlistToggleButton } from "~/components/product/wishlist-toggle-button";
import { useCompare } from "~/components/comparison/compare-provider";
import { formatPrice } from "~/lib/formatting/price";
import { platformDisplayName } from "~/lib/search/platforms";
import { categoryShortLabel } from "~/lib/search/categories";
import { productSlug } from "~/lib/seo/slug";
import { recordProductActivity } from "~/lib/api/activity";
import type { Product, Relationship } from "~/lib/api/schemas";
import { variantIdentityLine } from "~/lib/search/format-spec";
import { buildDisplayTitle } from "~/lib/product/display-title";
import { productCardIntelligence } from "~/lib/product/card-intelligence";
import { cn } from "~/components/ui/cn";

const relationshipLabel: Record<Relationship, string> = {
  exact_match: "Exact match",
  similar_variant: "Similar variant",
  related_product: "Related product",
};

function brandVisible(product: Product): string | null {
  const brand = (product.brand || "").trim();
  if (!brand) return null;
  const title = (product.title || "").toLowerCase();
  if (title.includes(brand.toLowerCase())) return null;
  return brand;
}

export function ProductCard({
  product,
  relationship,
  showCategoryBadge = false,
}: {
  product: Product;
  relationship?: Relationship;
  showCategoryBadge?: boolean;
}) {
  const compare = useCompare();
  const selected = compare.has(product.id);
  const relation = relationship ?? product.match_group;
  const href = `/products/${product.id}/${productSlug(product.title)}`;
  const blockReason = selected ? null : compare.compareBlockReason(product);
  const compareDisabled = !compare.storageReady || blockReason !== null;
  const platform = platformDisplayName(product.best_platform);
  const brand = brandVisible(product);
  const variantLine = variantIdentityLine(product);
  const categoryLabel = categoryShortLabel(product.category);
  const intelligence = productCardIntelligence(product);
  const display = buildDisplayTitle(product);

  const compareTitle = !compare.storageReady
    ? "Preparing comparison…"
    : blockReason === "unsupported_category"
      ? "Compare is available for Mayabu’s public product categories."
      : blockReason === "category_mismatch"
        ? "Compare only products from the same category."
        : blockReason === "full"
          ? `You can compare up to ${compare.maxProducts} products at once`
          : undefined;

  return (
    <Card
      interactive
      className="group flex h-full flex-col overflow-hidden p-3 sm:p-3.5"
    >
      <div className="relative">
        <Link
          to={href}
          onClick={() => {
            void recordProductActivity(product.id, "search_click");
          }}
          className="block overflow-hidden rounded-sm bg-surface-muted p-2.5 ring-1 ring-inset ring-line"
        >
          <ProductImage
            src={product.image_url}
            alt={product.title || "Product"}
            category={product.category}
            variant="card"
            frameClassName="max-h-[9rem] sm:max-h-[10rem]"
            className="transition duration-smooth motion-safe:group-hover:scale-[1.02]"
          />
        </Link>
        <WishlistToggleButton
          productId={product.id}
          productTitle={product.title}
          compact
          className="absolute right-2 top-2 shadow-soft"
        />
      </div>

      <div className="mt-3 flex min-h-[1.25rem] flex-wrap items-center gap-1.5">
        {showCategoryBadge && categoryLabel ? (
          <Badge tone="neutral" className="normal-case tracking-normal">
            {categoryLabel}
          </Badge>
        ) : null}
        {relation === "exact_match" || relation === "similar_variant" ? (
          <Badge
            tone={relation === "exact_match" ? "success" : "warning"}
            className="normal-case tracking-normal"
          >
            {relationshipLabel[relation]}
          </Badge>
        ) : null}
      </div>

      {brand ? (
        <p className="mt-2 text-[11px] font-medium uppercase tracking-wide text-ink-faint">
          {brand}
        </p>
      ) : (
        <span className="mt-2 block h-0" aria-hidden="true" />
      )}

      <Link
        to={href}
        className="mt-1 line-clamp-2 block min-h-[2.5rem] text-[15px] font-semibold leading-snug text-ink hover:text-accent-strong"
      >
        {display.title || product.title || "Untitled product"}
      </Link>
      {display.subtitle || variantLine ? (
        <p className="mt-1 min-h-[1.25rem] truncate text-sm text-ink-muted">
          {display.subtitle || variantLine}
        </p>
      ) : (
        <span className="mt-1 block min-h-[1.25rem]" aria-hidden="true" />
      )}

      <DisplaySpecs product={product} />

      <div className="mt-3 flex flex-1 flex-col justify-end">
        <p className="price-numerals text-xl font-bold leading-none tracking-tight text-ink">
          {formatPrice(product.best_price)}
        </p>
        <p className="mt-1.5 text-xs text-ink-muted">
          {platform ? `Best at ${platform}` : "No active store price"}
        </p>
        {intelligence ? (
          intelligence.kind === "stores" ? (
            <Link
              to={`${href}#offers`}
              className="mt-1 inline-block text-xs font-medium text-ink-soft underline-offset-2 hover:text-accent-strong hover:underline"
            >
              {intelligence.label}
            </Link>
          ) : (
            <p className="mt-1 text-xs font-medium text-ink-soft">{intelligence.label}</p>
          )
        ) : null}
      </div>

      <div className="mt-3.5 grid grid-cols-2 gap-2">
        <Link
          to={href}
          className="inline-flex min-h-10 items-center justify-center rounded-md bg-accent px-3 text-center text-sm font-semibold text-white transition hover:bg-accent-strong active:translate-y-px"
        >
          View details
        </Link>
        <Button
          variant="outline"
          className={cn(
            "min-h-10 px-2 text-sm",
            compareDisabled && "border-line text-ink-faint hover:bg-transparent",
          )}
          aria-pressed={selected}
          aria-label={
            selected
              ? `Remove ${product.title || "product"} from comparison`
              : blockReason === "category_mismatch"
                ? "Compare only products from the same category."
                : blockReason === "unsupported_category"
                  ? "Compare is available for Mayabu’s public product categories."
                  : blockReason === "full"
                    ? `You can compare up to ${compare.maxProducts} products at once`
                    : `Add ${product.title || "product"} to comparison`
          }
          disabled={compareDisabled}
          title={compareTitle}
          onClick={() => (selected ? compare.remove(product.id) : compare.add(product))}
        >
          {selected ? (
            <Check aria-hidden="true" className="h-4 w-4" />
          ) : (
            <GitCompareArrows aria-hidden="true" className="h-4 w-4" />
          )}
          {selected ? "Added" : "Compare"}
        </Button>
      </div>
    </Card>
  );
}
