import { productDisplaySpecs } from "~/lib/search/display-specs";
import type { Product } from "~/lib/api/schemas";

/** Generic display-spec chips for any category. */
export function DisplaySpecs({ product }: { product: Product }) {
  const chips = productDisplaySpecs(product);
  if (chips.length === 0) return null;
  return (
    <ul className="mt-2.5 flex min-h-[1.75rem] flex-wrap gap-1.5">
      {chips.map((spec) => (
        <li
          key={spec}
          className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium leading-4 text-slate-600"
        >
          {spec}
        </li>
      ))}
    </ul>
  );
}

/** @deprecated Prefer DisplaySpecs — kept as alias for gradual migration. */
export function ProductSpecSummary({ product }: { product: Product }) {
  return <DisplaySpecs product={product} />;
}
