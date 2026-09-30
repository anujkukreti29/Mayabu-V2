import type { Product } from "~/lib/api/schemas";
import { productDisplaySpecs } from "~/lib/search/display-specs";

/**
 * @deprecated Use DisplaySpecs / productDisplaySpecs.
 * Kept so existing laptop-focused tests and imports keep working during migration.
 */
export function laptopSpecSummary(product: Product): string[] {
  return productDisplaySpecs(product);
}

export { DisplaySpecs as LaptopSpecSummary } from "~/components/product/display-specs";
