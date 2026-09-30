import type { Product } from "~/lib/api/schemas";
import { formatDisplaySpecEntry, formatFacetValue, facetLabel } from "~/lib/search/facets";

/**
 * Build display chips from backend display_specs when present,
 * otherwise fall back to a small curated subset of specs.
 */
export function productDisplaySpecs(product: Product): string[] {
  const display = product.display_specs;
  if (display && typeof display === "object" && Object.keys(display).length > 0) {
    return Object.entries(display)
      .map(([key, value]) => formatDisplaySpecEntry(key, value))
      .filter((value): value is string => Boolean(value))
      .slice(0, 5);
  }

  const specs = product.specs ?? {};
  const chips: string[] = [];
  const model = product.model_codes?.[0] ?? specs.model_codes?.[0];
  if (model) chips.push(String(model));
  if (product.family) chips.push(String(product.family));

  for (const key of [
    "ram_gb",
    "storage_gb",
    "screen_inch",
    "screen_size_inch",
    "capacity_l",
    "capacity_kg",
    "load_type",
    "door_type",
    "panel_type",
    "network_generation",
    "form_factor",
    "connectivity",
    "anc",
    "cpu_series",
    "gpu",
  ] as const) {
    const value = (specs as Record<string, unknown>)[key];
    if (value === undefined || value === null || value === "") continue;
    const formatted = formatFacetValue(key, value);
    if (formatted) chips.push(formatted);
    if (chips.length >= 5) break;
  }
  return chips.slice(0, 5);
}

export function displaySpecPairs(
  product: Product,
): Array<{ key: string; label: string; value: string }> {
  const display = product.display_specs;
  if (display && typeof display === "object") {
    return Object.entries(display)
      .map(([key, value]) => {
        const formatted = formatFacetValue(key, value);
        return formatted ? { key, label: facetLabel(key), value: formatted } : null;
      })
      .filter((row): row is { key: string; label: string; value: string } => Boolean(row))
      .slice(0, 8);
  }
  return [];
}
