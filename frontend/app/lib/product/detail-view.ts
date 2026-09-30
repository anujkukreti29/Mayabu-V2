/** Product Detail view helpers — category-aware, offer-neutral. */

import type { Offer, Product, ProductDetail } from "~/lib/api/schemas";
import { validPrice } from "~/lib/formatting/price";
import { categoryDisplayName, isPublicCategory } from "~/lib/search/categories";
import { displaySpecPairs } from "~/lib/search/display-specs";
import { variantIdentityLine, matchEvidenceRows, hardConflictWarning } from "~/lib/search/format-spec";
import { facetLabel, formatFacetValue } from "~/lib/search/facets";
import { routes } from "~/lib/navigation/routes";
import { categoryLandingPath } from "~/lib/category/landing-registry";

function offerSortPrice(offer: Offer): number {
  const price = validPrice(offer.effective_price) ? offer.effective_price : offer.price;
  return validPrice(price) ? Number(price) : Number.POSITIVE_INFINITY;
}

function offerStockRank(offer: Offer): number {
  const stock = (offer.stock_status ?? "").toLowerCase();
  if (stock === "out_of_stock" || stock === "unavailable") return 1;
  return 0;
}

/** Public offers sorted by in-stock first, then ascending valid price. */
export function sortOffersByPrice(offers: Offer[]): Offer[] {
  return [...offers].sort((left, right) => {
    const stockDelta = offerStockRank(left) - offerStockRank(right);
    if (stockDelta !== 0) return stockDelta;
    const priceDelta = offerSortPrice(left) - offerSortPrice(right);
    if (priceDelta !== 0) return priceDelta;
    return String(left.platform ?? "").localeCompare(String(right.platform ?? ""));
  });
}

export function bestOfferId(offers: Offer[]): string | null {
  const sorted = sortOffersByPrice(offers);
  const first = sorted.find((offer) => Number.isFinite(offerSortPrice(offer)));
  return first?.id ?? null;
}

/** All offers tied for the eligible lowest in-stock (else overall) price. */
export function bestOfferIds(offers: Offer[]): Set<string> {
  const sorted = sortOffersByPrice(offers).filter((offer) => Number.isFinite(offerSortPrice(offer)));
  if (sorted.length === 0) return new Set();
  const bestPrice = offerSortPrice(sorted[0]!);
  const bestStock = offerStockRank(sorted[0]!);
  return new Set(
    sorted
      .filter(
        (offer) =>
          offerStockRank(offer) === bestStock && offerSortPrice(offer) === bestPrice,
      )
      .map((offer) => offer.id)
      .filter(Boolean),
  );
}

/** Defensive unique-by-platform collapse if API ever returns duplicates. */
export function uniqueOffersByPlatform(offers: Offer[]): Offer[] {
  const seen = new Set<string>();
  const out: Offer[] = [];
  for (const offer of sortOffersByPrice(offers)) {
    const platform = String(offer.platform || "").toLowerCase();
    if (!platform || seen.has(platform)) continue;
    seen.add(platform);
    out.push(offer);
  }
  return out;
}

export function categorySearchHref(category: string | null | undefined): string {
  if (!category || !isPublicCategory(category)) return routes.search;
  return (
    categoryLandingPath(category) ?? `${routes.search}?category=${encodeURIComponent(category)}`
  );
}

export function categoryBreadcrumbLabel(category: string | null | undefined): string {
  return categoryDisplayName(category) || "Products";
}

/** Spec rows for the detail page — prefers backend display_specs, then curated keys. */
export function productDetailSpecRows(
  product: Product,
): Array<{ key: string; label: string; value: string }> {
  const fromDisplay = displaySpecPairs(product);
  if (fromDisplay.length > 0) {
    // Include model codes when present and not already shown.
    const specs = product.specs ?? {};
    const model =
      product.model_codes?.[0] ??
      (Array.isArray(specs.model_codes) ? specs.model_codes[0] : undefined);
    const rows = [...fromDisplay];
    if (model && !rows.some((row) => row.key === "model_codes")) {
      rows.unshift({ key: "model_codes", label: "Model", value: String(model) });
    }
    return rows.slice(0, 10);
  }

  const specs = product.specs as Record<string, unknown>;
  const preferred = [
    "model_codes",
    "cpu_series",
    "cpu_models",
    "ram_gb",
    "storage_gb",
    "gpu",
    "screen_inch",
    "screen_size_inch",
    "chipset",
    "network_generation",
    "panel_type",
    "resolution",
    "refresh_rate_hz",
    "capacity_l",
    "capacity_kg",
    "door_type",
    "frost_type",
    "star_rating",
    "load_type",
    "automation_type",
    "rpm",
    "form_factor",
    "connectivity",
    "anc",
    "codec",
    "generation",
    "camera_type",
    "sensor_format",
    "megapixels",
    "mount",
    "body_only",
    "kit_lens",
  ];
  const rows: Array<{ key: string; label: string; value: string }> = [];
  for (const key of preferred) {
    let raw: unknown = specs[key];
    if (key === "model_codes") {
      raw = product.model_codes?.[0] ?? (Array.isArray(raw) ? raw[0] : raw);
    }
    if (Array.isArray(raw)) raw = raw[0];
    const formatted = formatFacetValue(key, raw);
    if (!formatted) continue;
    rows.push({ key, label: key === "model_codes" ? "Model" : facetLabel(key), value: formatted });
    if (rows.length >= 10) break;
  }
  return rows;
}

export function storeCoverageCopy(offerCount: number): string {
  if (offerCount <= 0) return "No public store offers yet.";
  if (offerCount === 1) return "Available from 1 store";
  return `Compare prices at ${offerCount} stores`;
}

export function limitedCoverageHint(offerCount: number): string | null {
  if (offerCount === 1) {
    return "More store coverage may be added as Mayabu checks additional retailers.";
  }
  return null;
}

export function isStockStatusTrustworthy(status: string | null | undefined): boolean {
  const value = (status ?? "").toLowerCase();
  return value === "in_stock" || value === "out_of_stock" || value === "unavailable";
}

export function similarVariantsBlurb(category: string | null | undefined): string {
  if (category === "camera") {
    return "These products may differ in body-only vs kit, lens, sensor, or another specification.";
  }
  if (category === "smartphone") {
    return "These products may differ in storage, RAM, colour, or model suffix.";
  }
  if (category === "laptop") {
    return "These products may differ in RAM, storage, processor, graphics, or screen.";
  }
  return "These products may differ in capacity, configuration, or another important specification.";
}

export function productPath(detail: ProductDetail): string {
  return `/products/${detail.product.id}`;
}

export { variantIdentityLine, matchEvidenceRows, hardConflictWarning };
