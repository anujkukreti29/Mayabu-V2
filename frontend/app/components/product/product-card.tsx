import { Check, GitCompareArrows } from "lucide-react";
import { Link } from "react-router";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import { Card } from "~/components/ui/card";
import { ProductImage } from "~/components/product/product-image";
import { useCompare } from "~/components/comparison/compare-provider";
import { formatPrice } from "~/lib/formatting/price";
import { freshnessFrom } from "~/lib/formatting/freshness";
import { productSlug } from "~/lib/seo/slug";
import type { Product, Relationship } from "~/lib/api/schemas";

const relationshipLabel: Record<Relationship, string> = {
  exact_match: "Exact match",
  similar_variant: "Similar variant",
  related_product: "Related product",
};

function keySpecs(product: Product): string[] {
  const specs = product.specs;
  return [
    specs.cpu_models?.[0] ?? specs.cpu_series,
    specs.ram_gb ? `${specs.ram_gb} GB RAM` : undefined,
    specs.storage_gb ? `${specs.storage_gb} GB storage` : undefined,
    specs.screen_inch ? `${specs.screen_inch} inch display` : undefined,
  ]
    .filter((value): value is string => Boolean(value))
    .slice(0, 3);
}

export function ProductCard({
  product,
  relationship,
}: {
  product: Product;
  relationship?: Relationship;
}) {
  const compare = useCompare();
  const selected = compare.has(product.id);
  const fresh = freshnessFrom(product.last_seen_at);
  const relation = relationship ?? product.match_group;
  const href = `/products/${product.id}/${productSlug(product.title)}`;

  return (
    <Card className="hover:border-brand-200 group overflow-hidden p-4 transition hover:-translate-y-0.5 hover:shadow-lg">
      <Link to={href} className="block rounded-xl">
        <ProductImage src={product.image_url} alt={product.title} className="mx-auto max-h-56" />
      </Link>
      <div className="mt-4 flex flex-wrap gap-2">
        <Badge
          tone={
            relation === "exact_match"
              ? "success"
              : relation === "similar_variant"
                ? "warning"
                : "neutral"
          }
        >
          {relationshipLabel[relation]}
        </Badge>
        <Badge tone={fresh.tone}>{fresh.label}</Badge>
      </div>
      <Link
        to={href}
        className="mt-3 line-clamp-2 block min-h-12 text-base font-black leading-6 text-slate-950 hover:text-brand-700"
      >
        {product.title || "Untitled product"}
      </Link>
      <p className="mt-1 text-xs font-bold uppercase tracking-wide text-slate-500">
        {product.brand || "Brand unavailable"}
      </p>
      {keySpecs(product).length > 0 ? (
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {keySpecs(product).map((spec) => (
            <li key={spec} className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700">
              {spec}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="mt-4">
        <p className="price-numerals text-2xl font-black text-slate-950">
          {formatPrice(product.best_price)}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          {product.best_platform
            ? `Best known on ${product.best_platform}`
            : "No active platform price"}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Available on {product.platform_count} platform{product.platform_count === 1 ? "" : "s"}
        </p>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <Link
          to={href}
          className="inline-flex min-h-11 items-center justify-center rounded-xl bg-brand-600 px-3 text-center text-sm font-bold text-white hover:bg-brand-700"
        >
          View details
        </Link>
        <Button
          variant="outline"
          className="px-2"
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
